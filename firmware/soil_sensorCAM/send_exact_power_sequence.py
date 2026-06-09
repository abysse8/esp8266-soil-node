import argparse
import re
import time
from pathlib import Path

import serial


LINE_RE = re.compile(r"^\s*([0-9]+\.[0-9]+)s\s+([0-9A-Fa-f]{2})\s+")


def parse_dump(path: Path):
    events = []

    text = path.read_text(encoding="utf-8", errors="replace")

    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue

        timestamp_s = float(m.group(1))
        byte_value = int(m.group(2), 16)
        events.append((timestamp_s, byte_value))

    if not events:
        raise RuntimeError("No timestamped bytes found in file.")

    return events


def normalize_events(events, keep_absolute_gaps=True):
    t0 = events[0][0]

    if keep_absolute_gaps:
        return [(t - t0, b) for t, b in events]

    main_index = 0

    for i, (t, b) in enumerate(events):
        if b != 0x00:
            main_index = i
            break

    main_events = events[main_index:]
    t0 = main_events[0][0]

    return [(t - t0, b) for t, b in main_events]


def summarize(events):
    print(f"byte count: {len(events)}")
    print(f"first timestamp: {events[0][0]:.6f}s")
    print(f"last timestamp:  {events[-1][0]:.6f}s")
    print(f"capture span:    {events[-1][0] - events[0][0]:.6f}s")
    print()

    print("first 20 bytes:")
    print(" ".join(f"{b:02X}" for _, b in events[:20]))
    print()

    print("candidate burst starts using gap > 3 ms:")
    previous_t = None

    for t, b in events:
        if previous_t is None or (t - previous_t) > 0.003:
            print(f"{t:.6f}s  {b:02X}")
        previous_t = t


def send_timed(port, baud, normalized_events, repeat, inter_repeat_ms):
    ser = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0,
        write_timeout=1,
    )

    try:
        for r in range(repeat):
            print(f"repeat {r + 1}/{repeat}")

            start = time.perf_counter()

            for target_t, byte_value in normalized_events:
                while True:
                    elapsed = time.perf_counter() - start
                    remaining = target_t - elapsed

                    if remaining <= 0:
                        break

                    if remaining > 0.002:
                        time.sleep(remaining - 0.001)
                    else:
                        time.sleep(0)

                ser.write(bytes([byte_value]))

            ser.flush()

            if r + 1 < repeat:
                time.sleep(inter_repeat_ms / 1000.0)

    finally:
        ser.close()


def send_fast(port, baud, normalized_events, repeat, inter_repeat_ms):
    data = bytes(b for _, b in normalized_events)

    ser = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0,
        write_timeout=1,
    )

    try:
        for r in range(repeat):
            print(f"repeat {r + 1}/{repeat}")
            ser.write(data)
            ser.flush()

            if r + 1 < repeat:
                time.sleep(inter_repeat_ms / 1000.0)

    finally:
        ser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="power_sequence.txt")
    parser.add_argument("--port", default="COM4")
    parser.add_argument("--baud", type=int, default=38400)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--inter-repeat-ms", type=float, default=100.0)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--skip-leading-zeros", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    events = parse_dump(Path(args.file))
    summarize(events)

    normalized = normalize_events(
        events,
        keep_absolute_gaps=not args.skip_leading_zeros,
    )

    print()
    print(f"normalized duration: {normalized[-1][0]:.6f}s")
    print(f"mode: {'fast byte stream' if args.fast else 'timed replay'}")
    print(f"port: {args.port}")
    print(f"baud: {args.baud}")

    if args.dry_run:
        print()
        print("dry run only, nothing sent")
        return

    print()
    input("Disconnect the original controller data pair. Press ENTER to transmit.")

    if args.fast:
        send_fast(
            port=args.port,
            baud=args.baud,
            normalized_events=normalized,
            repeat=args.repeat,
            inter_repeat_ms=args.inter_repeat_ms,
        )
    else:
        send_timed(
            port=args.port,
            baud=args.baud,
            normalized_events=normalized,
            repeat=args.repeat,
            inter_repeat_ms=args.inter_repeat_ms,
        )

    print("done")


if __name__ == "__main__":
    main()