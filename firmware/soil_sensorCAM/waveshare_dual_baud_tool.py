import argparse
import time
import serial
import serial.tools.list_ports


def list_ports():
    for p in serial.tools.list_ports.comports():
        print(f"{p.device:8s} {p.description}")
        if p.hwid:
            print(f"         {p.hwid}")


def open_port(port, baud):
    return serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0.01,
        write_timeout=1,
    )


def print_hex_line(data):
    print(" ".join(f"{b:02X}" for b in data))


def listen(port, baud, seconds):
    print(f"Listening on {port} at {baud} baud for {seconds}s")

    ser = open_port(port, baud)
    t0 = time.perf_counter()
    count = 0

    try:
        while time.perf_counter() - t0 < seconds:
            b = ser.read(1)

            if not b:
                continue

            count += 1
            t = time.perf_counter() - t0
            value = b[0]
            printable = chr(value) if 32 <= value <= 126 else "."

            print(f"{t:10.6f}s  {value:02X}  {value:3d}  {printable}")

    finally:
        ser.close()

    print(f"received {count} bytes")


def send_bytes(port, baud, data, repeat, inter_repeat_ms):
    print(f"Sending on {port} at {baud} baud")
    print(f"bytes={len(data)} repeat={repeat}")

    ser = open_port(port, baud)

    try:
        for i in range(repeat):
            print(f"send {i + 1}/{repeat}")
            ser.write(data)
            ser.flush()

            if i + 1 < repeat:
                time.sleep(inter_repeat_ms / 1000.0)

    finally:
        ser.close()


def send_4800_control_probe(port):
    data = bytes.fromhex(
        "F0 F1 74 E4 5B 59 57 A6 DD DD 2D"
    )

    send_bytes(
        port=port,
        baud=4800,
        data=data,
        repeat=1,
        inter_repeat_ms=100,
    )


def send_38400_bitmap_probe(port):
    data = bytes.fromhex(
        "FE 00 00 80 80 80 00 80 00 80 00 00 80 80 80 00 "
        "F8 00 00 80 80 80 00 80 00 80 80 00 00 80 80 00 "
        "FE 00 80 80 80 80 80 00 80 00 80 80 00 00 80 80 "
        "C0 00 80 80 80 80 00 80 00 "
        "F0 00 00 80 80 80 80 00 80"
    )

    send_bytes(
        port=port,
        baud=38400,
        data=data,
        repeat=1,
        inter_repeat_ms=30,
    )


def dual_listen(port, control_seconds, bitmap_seconds):
    listen(port, 4800, control_seconds)
    time.sleep(0.2)
    listen(port, 38400, bitmap_seconds)


def dual_send_probe(port):
    send_4800_control_probe(port)
    time.sleep(0.2)
    send_38400_bitmap_probe(port)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--port", default="COM4")

    parser.add_argument(
        "--mode",
        choices=[
            "listen4800",
            "listen38400",
            "dual-listen",
            "send4800",
            "send38400",
            "dual-send",
        ],
        required=False,
    )

    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--control-seconds", type=float, default=10.0)
    parser.add_argument("--bitmap-seconds", type=float, default=10.0)
    parser.add_argument("--repeat", type=int, default=1)

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if not args.mode:
        print("Missing --mode")
        return

    if args.mode == "listen4800":
        listen(args.port, 4800, args.seconds)

    elif args.mode == "listen38400":
        listen(args.port, 38400, args.seconds)

    elif args.mode == "dual-listen":
        dual_listen(args.port, args.control_seconds, args.bitmap_seconds)

    elif args.mode == "send4800":
        send_4800_control_probe(args.port)

    elif args.mode == "send38400":
        send_38400_bitmap_probe(args.port)

    elif args.mode == "dual-send":
        dual_send_probe(args.port)


if __name__ == "__main__":
    main()