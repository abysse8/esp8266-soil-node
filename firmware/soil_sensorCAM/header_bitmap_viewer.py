import argparse
import time

import numpy as np
import matplotlib.pyplot as plt
import serial
import serial.tools.list_ports


HEADER_BYTES = {0xFE, 0xF8, 0xC0, 0xF0, 0xE0}


def list_ports():
    for p in serial.tools.list_ports.comports():
        print(f"{p.device:8s} {p.description}")
        if p.hwid:
            print(f"         {p.hwid}")


def parse_headers(text):
    return {int(x.strip(), 16) for x in text.split(",") if x.strip()}


def byte_nonzero_bitmap(payload, width, height):
    pixels = [1 if b != 0x00 else 0 for b in payload]

    needed = width * height

    if len(pixels) < needed:
        pixels += [0] * (needed - len(pixels))

    pixels = pixels[:needed]

    return np.array(pixels, dtype=np.uint8).reshape(height, width)


def bit_msb_bitmap(payload, width, height):
    pixels = []

    for b in payload:
        for bit in range(7, -1, -1):
            pixels.append((b >> bit) & 1)

    needed = width * height

    if len(pixels) < needed:
        pixels += [0] * (needed - len(pixels))

    pixels = pixels[:needed]

    return np.array(pixels, dtype=np.uint8).reshape(height, width)


def bit_lsb_bitmap(payload, width, height):
    pixels = []

    for b in payload:
        for bit in range(8):
            pixels.append((b >> bit) & 1)

    needed = width * height

    if len(pixels) < needed:
        pixels += [0] * (needed - len(pixels))

    pixels = pixels[:needed]

    return np.array(pixels, dtype=np.uint8).reshape(height, width)


def make_bitmap(blocks, width, height, mode):
    payload = bytearray()

    for header, data in blocks:
        payload.extend(data)

    if mode == "byte":
        return byte_nonzero_bitmap(payload, width, height)

    if mode == "bit-msb":
        return bit_msb_bitmap(payload, width, height)

    if mode == "bit-lsb":
        return bit_lsb_bitmap(payload, width, height)

    raise ValueError(mode)


def print_block(header, payload):
    preview = " ".join(f"{b:02X}" for b in payload[:64])

    if len(payload) > 64:
        preview += f" ... +{len(payload) - 64} bytes"

    print()
    print(f"[block] header={header:02X} payload_len={len(payload)}")
    print(f"        {preview}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--port", default="COM4")
    parser.add_argument("--baud", type=int, default=38400)
    parser.add_argument("--timeout", type=float, default=0.01)

    parser.add_argument("--width", type=int, default=100)
    parser.add_argument("--height", type=int, default=20)

    parser.add_argument("--headers", default="FE,F8,C0,F0,E0")
    parser.add_argument("--blocks-per-frame", type=int, default=6)

    parser.add_argument("--mode", choices=["byte", "bit-msb", "bit-lsb"], default="byte")

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    headers = parse_headers(args.headers)

    ser = serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=args.timeout,
    )

    print(f"listening on {args.port} at {args.baud}")
    print(f"headers = {' '.join(f'{h:02X}' for h in sorted(headers))}")
    print(f"blocks_per_frame = {args.blocks_per_frame}")
    print(f"mode = {args.mode}")
    print("press Ctrl+C to stop")
    print()

    plt.ion()

    fig, ax = plt.subplots(figsize=(12, 4))
    bitmap = np.zeros((args.height, args.width), dtype=np.uint8)

    image = ax.imshow(
        bitmap,
        interpolation="nearest",
        aspect="auto",
        vmin=0,
        vmax=1,
    )

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("waiting for header...")
    plt.tight_layout()
    plt.show(block=False)

    current_header = None
    current_payload = bytearray()

    completed_blocks = []
    frame_count = 0
    byte_count = 0

    try:
        while True:
            b = ser.read(1)

            if not b:
                plt.pause(0.001)
                continue

            value = b[0]
            byte_count += 1

            if value in headers:
                if current_header is not None:
                    print_block(current_header, current_payload)
                    completed_blocks.append((current_header, bytes(current_payload)))

                    if len(completed_blocks) >= args.blocks_per_frame:
                        frame_blocks = completed_blocks[:args.blocks_per_frame]
                        completed_blocks = completed_blocks[args.blocks_per_frame:]

                        bitmap = make_bitmap(
                            blocks=frame_blocks,
                            width=args.width,
                            height=args.height,
                            mode=args.mode,
                        )

                        header_text = " ".join(f"{h:02X}" for h, _ in frame_blocks)

                        frame_count += 1

                        image.set_data(bitmap)
                        ax.set_title(
                            f"frame {frame_count} | headers {header_text} | bytes {byte_count}"
                        )
                        fig.canvas.draw_idle()
                        plt.pause(0.001)

                        print()
                        print(f"[frame {frame_count}] headers={header_text}")
                        print()

                current_header = value
                current_payload = bytearray()

                print()
                print(f"HEADER {value:02X}")

            else:
                if current_header is not None:
                    current_payload.append(value)

    except KeyboardInterrupt:
        print()
        print("stopped")

        if current_header is not None:
            print_block(current_header, current_payload)

    finally:
        ser.close()
        plt.ioff()
        plt.show()


if __name__ == "__main__":
    main()