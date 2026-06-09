import argparse
import time
import serial
import serial.tools.list_ports


def list_ports():
    for p in serial.tools.list_ports.comports():
        print(f"{p.device:8s} {p.description}")
        if p.hwid:
            print(f"         {p.hwid}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--port", help="example: COM3")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--timeout", type=float, default=0.05)
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if not args.port:
        print("missing --port")
        print("run: py basic_rs485_dump.py --list")
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
    print("press Ctrl+C to stop")
    print()

    t0 = time.perf_counter()

    try:
        while True:
            b = ser.read(1)

            if not b:
                continue

            t = time.perf_counter() - t0
            value = b[0]

            printable = chr(value) if 32 <= value <= 126 else "."

            print(f"{t:12.6f}s  {value:02X}  {value:3d}  {printable}")

    except KeyboardInterrupt:
        print("\nstopped")

    finally:
        ser.close()


if __name__ == "__main__":
    main()