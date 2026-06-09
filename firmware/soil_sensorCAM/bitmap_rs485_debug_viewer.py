import argparse
import time
from collections import deque

import numpy as np
import matplotlib.pyplot as plt
import serial
import serial.tools.list_ports


def list_ports():
    for p in serial.tools.list_ports.comports():
        print(f"{p.device:8s} {p.description}")
        if p.hwid:
            print(f"         {p.hwid}")


def parse_burst_indexes(text):
    return [int(x.strip()) for x in text.split(",") if x.strip()]


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
            raise ValueError(f"unknown mode: {mode}")

    needed = width * height

    if len(pixels) < needed:
        pixels.extend([0] * (needed - len(pixels)))

    pixels = pixels[:needed]
    return np.array(pixels, dtype=np.uint8).reshape((height, width))


def burst_to_bytes(burst):
    return bytes(b for _, b in burst)


def select_payloads_from_bursts(bursts, use_bursts, header_len):
    headers = []
    payloads = []

    for idx in use_bursts:
        if idx < 0 or idx >= len(bursts):
            continue

        data = burst_to_bytes(bursts[idx])

        if len(data) <= header_len:
            continue

        headers.append(data[:header_len])
        payloads.append(data[header_len:])

    return headers, payloads


def hex_line(data, max_bytes=64):
    shown = data[:max_bytes]
    s = " ".join(f"{b:02X}" for b in shown)
    if len(data) > max_bytes:
        s += f" ... +{len(data) - max_bytes} bytes"
    return s


def printable_byte(b):
    return chr(b) if 32 <= b <= 126 else "."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")

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

    parser.add_argument("--print-every-byte", action="store_true")
    parser.add_argument("--max-burst-print", type=int, default=96)

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
    )

    print(f"listening on {args.port} at {args.baud} baud")
    print(f"gap_ms={args.gap_ms}")
    print(f"bursts_per_frame={args.bursts_per_frame}")
    print(f"use_bursts={args.use_bursts}")
    print(f"pixel_mode={args.pixel_mode}")
    print("press Ctrl+C to stop")
    print()

    plt.ion()
    fig, ax = plt.subplots(figsize=(12, 4))

    bitmap = np.zeros((args.height, args.width), dtype=np.uint8)
    image = ax.imshow(bitmap, interpolation="nearest", aspect="auto", vmin=0, vmax=1)

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("waiting for bytes...")
    plt.tight_layout()
    plt.show(block=False)

    t0 = time.perf_counter()
    last_byte_wall = None

    current_burst = []
    frame_bursts = []
    byte_count = 0
    burst_count = 0
    frame_count = 0

    try:
        while True:
            b = ser.read(1)
            now = time.perf_counter()
            rel_t = now - t0

            if b:
                value = b[0]
                byte_count += 1

                gap_ms = None
                if last_byte_wall is not None:
                    gap_ms = (now - last_byte_wall) * 1000.0

                if gap_ms is not None and gap_ms > args.gap_ms and current_burst:
                    data = burst_to_bytes(current_burst)
                    burst_count += 1

                    print()
                    print(
                        f"[burst {burst_count:04d}] "
                        f"bytes={len(data)} "
                        f"start={current_burst[0][0]:.6f}s "
                        f"end={current_burst[-1][0]:.6f}s "
                        f"header={data[0]:02X} "
                        f"gap_before={gap_ms:.3f} ms"
                    )
                    print(f"  {hex_line(data, args.max_burst_print)}")

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

                        header_text = " ".join(h.hex().upper() for h in headers)
                        frame_count += 1

                        image.set_data(bitmap)
                        ax.set_title(
                            f"frame {frame_count} | "
                            f"headers={header_text} | "
                            f"mode={args.pixel_mode} | "
                            f"bytes={byte_count}"
                        )
                        fig.canvas.draw_idle()
                        plt.pause(0.001)

                        print()
                        print(
                            f"[frame {frame_count:04d}] "
                            f"selected_headers={header_text} "
                            f"display_updated"
                        )

                current_burst.append((rel_t, value))
                last_byte_wall = now

                if args.print_every_byte:
                    if gap_ms is None:
                        gap_text = "n/a"
                    else:
                        gap_text = f"{gap_ms:.3f} ms"

                    print(
                        f"{rel_t:12.6f}s  "
                        f"gap={gap_text:>10s}  "
                        f"{value:02X}  {value:3d}  {printable_byte(value)}"
                    )

            else:
                plt.pause(0.001)

    except KeyboardInterrupt:
        print()
        print("stopped")

        if current_burst:
            data = burst_to_bytes(current_burst)
            print()
            print("[last incomplete burst]")
            print(f"bytes={len(data)} header={data[0]:02X}")
            print(hex_line(data, args.max_burst_print))

    finally:
        ser.close()
        plt.ioff()
        plt.show()


if __name__ == "__main__":
    main()
