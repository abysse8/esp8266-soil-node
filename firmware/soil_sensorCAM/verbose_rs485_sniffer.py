import argparse
import time
from collections import Counter, deque

import serial
import serial.tools.list_ports


def list_ports():
    for p in serial.tools.list_ports.comports():
        print(f"{p.device:8s} {p.description}")
        if p.hwid:
            print(f"         {p.hwid}")


def printable(b):
    return chr(b) if 32 <= b <= 126 else "."


def hex_line(data, max_len=96):
    shown = data[:max_len]
    s = " ".join(f"{b:02X}" for b in shown)
    if len(data) > max_len:
        s += f" ... +{len(data) - max_len} bytes"
    return s


def classify_byte_context(value, gap_ms):
    if gap_ms is None:
        return "first_byte"

    if gap_ms > 1000:
        return "after_very_long_idle"

    if gap_ms > 20:
        return "after_long_idle"

    if gap_ms > 3:
        return "new_burst_candidate"

    if value in (0x00, 0x80, 0xF8, 0xFE, 0xF0, 0xE0, 0xC0):
        return "known_repeated_symbol"

    return "ordinary"


def print_stats(total_counter, recent_counter):
    print()
    print("=== byte frequency, total ===")
    for b, c in total_counter.most_common(16):
        print(f"{b:02X}: {c}")

    print()
    print("=== byte frequency, recent ===")
    for b, c in recent_counter.most_common(16):
        print(f"{b:02X}: {c}")

    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--port", default="COM4")
    parser.add_argument("--baud", type=int, default=38400)
    parser.add_argument("--timeout", type=float, default=0.001)

    parser.add_argument("--burst-gap-ms", type=float, default=3.0)
    parser.add_argument("--print-every-byte", action="store_true")
    parser.add_argument("--stats-every-s", type=float, default=2.0)
    parser.add_argument("--max-burst-print", type=int, default=128)

    parser.add_argument("--rts", choices=["on", "off", "none"], default="none")
    parser.add_argument("--dtr", choices=["on", "off", "none"], default="none")

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    ser = serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=args.timeout,
        write_timeout=0,
    )

    if args.rts != "none":
        ser.rts = args.rts == "on"

    if args.dtr != "none":
        ser.dtr = args.dtr == "on"

    ser.reset_input_buffer()

    print(f"listening on {args.port} at {args.baud} baud")
    print(f"timeout={args.timeout}s")
    print(f"burst_gap_ms={args.burst_gap_ms}")
    print(f"RTS={ser.rts} DTR={ser.dtr}")
    print("press Ctrl+C to stop")
    print()

    t0 = time.perf_counter()
    last_byte_t = None
    last_stats_t = time.perf_counter()

    total_counter = Counter()
    recent_bytes = deque(maxlen=512)

    current_burst = []
    burst_id = 0
    total_bytes = 0

    try:
        while True:
            chunk = ser.read(256)
            now = time.perf_counter()

            if not chunk:
                if current_burst and last_byte_t is not None:
                    idle_ms = (now - last_byte_t) * 1000.0

                    if idle_ms > args.burst_gap_ms:
                        data = bytes(b for _, b, _ in current_burst)
                        burst_start = current_burst[0][0]
                        burst_end = current_burst[-1][0]
                        burst_id += 1

                        print()
                        print(
                            f"[BURST END {burst_id:04d}] "
                            f"bytes={len(data)} "
                            f"start={burst_start:.6f}s "
                            f"end={burst_end:.6f}s "
                            f"duration={(burst_end - burst_start) * 1000:.3f} ms "
                            f"idle_after={idle_ms:.3f} ms "
                            f"first={data[0]:02X} "
                            f"last={data[-1]:02X}"
                        )
                        print(f"  {hex_line(data, args.max_burst_print)}")
                        current_burst = []

                if now - last_stats_t >= args.stats_every_s:
                    recent_counter = Counter(recent_bytes)
                    print_stats(total_counter, recent_counter)
                    last_stats_t = now

                continue

            for byte_value in chunk:
                t = time.perf_counter()
                rel_t = t - t0
                total_bytes += 1

                if last_byte_t is None:
                    gap_ms = None
                else:
                    gap_ms = (t - last_byte_t) * 1000.0

                context = classify_byte_context(byte_value, gap_ms)

                if gap_ms is not None and gap_ms > args.burst_gap_ms and current_burst:
                    data = bytes(b for _, b, _ in current_burst)
                    burst_start = current_burst[0][0]
                    burst_end = current_burst[-1][0]
                    burst_id += 1

                    print()
                    print(
                        f"[BURST END {burst_id:04d}] "
                        f"bytes={len(data)} "
                        f"start={burst_start:.6f}s "
                        f"end={burst_end:.6f}s "
                        f"duration={(burst_end - burst_start) * 1000:.3f} ms "
                        f"gap_before_next={gap_ms:.3f} ms "
                        f"first={data[0]:02X} "
                        f"last={data[-1]:02X}"
                    )
                    print(f"  {hex_line(data, args.max_burst_print)}")
                    current_burst = []

                total_counter[byte_value] += 1
                recent_bytes.append(byte_value)
                current_burst.append((rel_t, byte_value, gap_ms))

                if args.print_every_byte:
                    gap_text = "n/a" if gap_ms is None else f"{gap_ms:.3f} ms"

                    print(
                        f"{rel_t:12.6f}s  "
                        f"gap={gap_text:>10s}  "
                        f"{byte_value:02X}  "
                        f"{byte_value:3d}  "
                        f"{printable(byte_value)}  "
                        f"{context}"
                    )

                else:
                    if context in ("after_very_long_idle", "after_long_idle", "new_burst_candidate", "first_byte"):
                        gap_text = "n/a" if gap_ms is None else f"{gap_ms:.3f} ms"
                        print(
                            f"{rel_t:12.6f}s  "
                            f"gap={gap_text:>10s}  "
                            f"{byte_value:02X}  "
                            f"{context}"
                        )

                last_byte_t = t

    except KeyboardInterrupt:
        print()
        print("stopped")
        print(f"total bytes={total_bytes}")

        if current_burst:
            data = bytes(b for _, b, _ in current_burst)
            print()
            print("[LAST INCOMPLETE BURST]")
            print(f"bytes={len(data)} first={data[0]:02X} last={data[-1]:02X}")
            print(hex_line(data, args.max_burst_print))

        recent_counter = Counter(recent_bytes)
        print_stats(total_counter, recent_counter)

    finally:
        ser.close()


if __name__ == "__main__":
    main()