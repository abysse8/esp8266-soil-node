import argparse
import re
import time
from collections import deque
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import serial
import serial.tools.list_ports


LINE_RE = re.compile(r"^\s*([0-9]+\.[0-9]+)s\s+([0-9A-Fa-f]{2})\s+")


def list_ports():
    for p in serial.tools.list_ports.comports():
        print(f"{p.device:8s} {p.description}")
        if p.hwid:
            print(f"         {p.hwid}")


def parse_dump_file(path):
    events = []

    text = Path(path).read_text(encoding="utf-8", errors="replace")

    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue

        t = float(m.group(1))
        b = int(m.group(2), 16)
        events.append((t, b))

    return events


def split_events_into_bursts(events, gap_ms):
    if not events:
        return []

    bursts = []
    current = [events[0]]

    gap_s = gap_ms / 1000.0

    for prev, cur in zip(events, events[1:]):
        prev_t, _ = prev
        cur_t, _ = cur

        if cur_t - prev_t > gap_s:
            bursts.append(current)
            current = [cur]
        else:
            current.append(cur)

    if current:
        bursts.append(current)

    return bursts


def burst_to_bytes(burst):
    return bytes(b for _, b in burst)


def describe_bursts(bursts):
    for i, burst in enumerate(bursts):
        data = burst_to_bytes(burst)
        if not data:
            continue

        start_t = burst[0][0]
        end_t = burst[-1][0]
        header = data[0]
        payload_len = max(0, len(data) - 1)

        print(
            f"burst {i:02d}: "
            f"t={start_t:.6f}s..{end_t:.6f}s "
            f"header={header:02X} "
            f"payload_len={payload_len} "
            f"total={len(data)}"
        )


def bytes_to_pixels_byte_nonzero(payload):
    return [1 if b != 0x00 else 0 for b in payload]


def bytes_to_pixels_bit_msb(payload):
    pixels = []

    for b in payload:
        for bit in range(7, -1, -1):
            pixels.append((b >> bit) & 1)

    return pixels


def bytes_to_pixels_bit_lsb(payload):
    pixels = []

    for b in payload:
        for bit in range(8):
            pixels.append((b >> bit) & 1)

    return pixels


def payloads_to_bitmap(payloads, width, height, mode):
    pixels = []

    for payload in payloads:
        if mode == "byte-nonzero":
            pixels.extend(bytes_to_pixels_byte_nonzero(payload))
        elif mode == "bit-msb":
            pixels.extend(bytes_to_pixels_bit_msb(payload))
        elif mode == "bit-lsb":
            pixels.extend(bytes_to_pixels_bit_lsb(payload))
        else:
            raise ValueError(f"Unknown mode: {mode}")

    needed = width * height

    if len(pixels) < needed:
        pixels.extend([0] * (needed - len(pixels)))

    pixels = pixels[:needed]

    arr = np.array(pixels, dtype=np.uint8).reshape((height, width))
    return arr


def select_payloads_from_bursts(bursts, use_bursts, header_len):
    payloads = []
    headers = []

    for idx in use_bursts:
        if idx < 0 or idx >= len(bursts):
            continue

        data = burst_to_bytes(bursts[idx])

        if len(data) <= header_len:
            continue

        headers.append(data[:header_len])
        payloads.append(data[header_len:])

    return headers, payloads


def render_once(bitmap, title):
    plt.figure(figsize=(12, 4))
    plt.imshow(bitmap, interpolation="nearest", aspect="auto")
    plt.title(title)
    plt.xlabel("x")
    plt.ylabel("y")
    plt.tight_layout()
    plt.show()


def run_file_mode(args):
    events = parse_dump_file(args.file)

    if not events:
        print("No timestamped bytes found.")
        return

    bursts = split_events_into_bursts(events, gap_ms=args.gap_ms)

    print(f"events: {len(events)}")
    print(f"bursts: {len(bursts)}")
    print()

    describe_bursts(bursts)

    selected_headers, payloads = select_payloads_from_bursts(
        bursts=bursts,
        use_bursts=args.use_bursts,
        header_len=args.header_len,
    )

    print()
    print("selected headers:")
    for h in selected_headers:
        print(h.hex(" ").upper())

    bitmap = payloads_to_bitmap(
        payloads=payloads,
        width=args.width,
        height=args.height,
        mode=args.pixel_mode,
    )

    render_once(
        bitmap=bitmap,
        title=(
            f"{Path(args.file).name} | "
            f"mode={args.pixel_mode} | "
            f"use_bursts={args.use_bursts} | "
            f"{args.width}x{args.height}"
        ),
    )


def update_live_plot(ax, image, bitmap, title):
    image.set_data(bitmap)
    ax.set_title(title)
    plt.pause(0.001)


def run_live_mode(args):
    ser = serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=args.timeout,
    )

    print(f"listening on {args.port} at {args.baud} baud")
    print(f"gap_ms={args.gap_ms}")
    print(f"bursts_per_frame={args.bursts_per_frame}")
    print(f"use_bursts={args.use_bursts}")
    print("press Ctrl+C to stop")

    plt.ion()
    fig, ax = plt.subplots(figsize=(12, 4))
    bitmap = np.zeros((args.height, args.width), dtype=np.uint8)
    image = ax.imshow(bitmap, interpolation="nearest", aspect="auto")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    plt.tight_layout()

    t0 = time.perf_counter()

    current_burst = []
    frame_bursts = []

    last_byte_time = None
    frame_count = 0

    try:
        while True:
            b = ser.read(1)
            now = time.perf_counter()
            rel_t = now - t0

            if b:
                value = b[0]

                if last_byte_time is not None:
                    gap_ms = (now - last_byte_time) * 1000.0

                    if gap_ms > args.gap_ms and current_burst:
                        frame_bursts.append(current_burst)
                        current_burst = []

                        if len(frame_bursts) >= args.bursts_per_frame:
                            group = frame_bursts[:args.bursts_per_frame]
                            frame_bursts = frame_bursts[args.bursts_per_frame:]

                            headers, payloads = select_payloads_from_bursts(
                                bursts=group,
                                use_bursts=args.use_bursts,
                                header_len=args.header_len,
                            )

                            bitmap = payloads_to_bitmap(
                                payloads=payloads,
                                width=args.width,
                                height=args.height,
                                mode=args.pixel_mode,
                            )

                            header_text = " ".join(h.hex("").upper() for h in headers)
                            frame_count += 1

                            update_live_plot(
                                ax=ax,
                                image=image,
                                bitmap=bitmap,
                                title=(
                                    f"frame {frame_count} | "
                                    f"headers={header_text} | "
                                    f"mode={args.pixel_mode}"
                                ),
                            )

                current_burst.append((rel_t, value))
                last_byte_time = now

            else:
                if last_byte_time is None:
                    continue

                gap_ms = (now - last_byte_time) * 1000.0

                if gap_ms > args.gap_ms and current_burst:
                    frame_bursts.append(current_burst)
                    current_burst = []

                    if len(frame_bursts) >= args.bursts_per_frame:
                        group = frame_bursts[:args.bursts_per_frame]
                        frame_bursts = frame_bursts[args.bursts_per_frame:]

                        headers, payloads = select_payloads_from_bursts(
                            bursts=group,
                            use_bursts=args.use_bursts,
                            header_len=args.header_len,
                        )

                        bitmap = payloads_to_bitmap(
                            payloads=payloads,
                            width=args.width,
                            height=args.height,
                            mode=args.pixel_mode,
                        )

                        header_text = " ".join(h.hex("").upper() for h in headers)
                        frame_count += 1

                        update_live_plot(
                            ax=ax,
                            image=image,
                            bitmap=bitmap,
                            title=(
                                f"frame {frame_count} | "
                                f"headers={header_text} | "
                                f"mode={args.pixel_mode}"
                            ),
                        )

    except KeyboardInterrupt:
        print("\nstopped")

    finally:
        ser.close()
        plt.ioff()
        plt.show()


def parse_burst_indexes(text):
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--list", action="store_true")

    parser.add_argument("--file", help="offline dump file, for example power_sequence.txt")
    parser.add_argument("--port", default="COM4")
    parser.add_argument("--baud", type=int, default=38400)
    parser.add_argument("--timeout", type=float, default=0.01)

    parser.add_argument("--width", type=int, default=100)
    parser.add_argument("--height", type=int, default=20)

    parser.add_argument("--gap-ms", type=float, default=3.0)
    parser.add_argument("--bursts-per-frame", type=int, default=6)
    parser.add_argument("--use-bursts", type=parse_burst_indexes, default=parse_burst_indexes("0,2"))

    parser.add_argument("--header-len", type=int, default=1)

    parser.add_argument(
        "--pixel-mode",
        choices=["byte-nonzero", "bit-msb", "bit-lsb"],
        default="byte-nonzero",
    )

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if args.file:
        run_file_mode(args)
    else:
        run_live_mode(args)


if __name__ == "__main__":
    main()