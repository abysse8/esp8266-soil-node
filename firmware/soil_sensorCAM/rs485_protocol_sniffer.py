#!/usr/bin/env python3

import argparse
import time
import csv
import sys
from datetime import datetime
from pathlib import Path

import serial
import serial.tools.list_ports


COMMON_BAUDRATES = [
    1200,
    2400,
    4800,
    9600,
    19200,
    38400,
    57600,
    115200,
]


def list_ports():
    ports = list(serial.tools.list_ports.comports())

    if not ports:
        print("No serial ports found.")
        return

    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device:8s}  {p.description}")
        if p.hwid:
            print(f"            {p.hwid}")


def hex_bytes(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def ascii_preview(data: bytes) -> str:
    out = []
    for b in data:
        if 32 <= b <= 126:
            out.append(chr(b))
        else:
            out.append(".")
    return "".join(out)


def classify_frame(data: bytes, duration_ms: float, idle_before_ms: float | None):
    n = len(data)

    if n == 0:
        return "empty", 0.0

    starts_02_ends_03 = data[0] == 0x02 and data[-1] == 0x03
    starts_01_ends_04 = data[0] == 0x01 and data[-1] == 0x04

    if starts_02_ends_03:
        return "stx_etx_frame_candidate", 0.90

    if starts_01_ends_04:
        return "soh_eot_frame_candidate", 0.90

    if n <= 2:
        return "tiny_reply_or_noise", 0.35

    if n <= 8:
        if idle_before_ms is not None and idle_before_ms > 100:
            return "short_after_idle_polling_candidate", 0.65
        return "short_control_candidate", 0.55

    if n <= 64:
        return "medium_message_candidate", 0.60

    return "large_payload_candidate", 0.70


def print_frame(frame_id, t0, t1, data, idle_before_ms, label, confidence):
    duration_ms = (t1 - t0) * 1000.0

    idle_text = "n/a" if idle_before_ms is None else f"{idle_before_ms:.3f} ms"

    print()
    print(f"[frame {frame_id:06d}]")
    print(f"  time:        {t0:.6f}s -> {t1:.6f}s")
    print(f"  duration:    {duration_ms:.3f} ms")
    print(f"  idle before: {idle_text}")
    print(f"  bytes:       {len(data)}")
    print(f"  class:       {label}  confidence={confidence:.2f}")
    print(f"  hex:         {hex_bytes(data)}")
    print(f"  ascii:       {ascii_preview(data)}")


def open_serial(port, baudrate, timeout):
    return serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
        write_timeout=0,
    )


def sniff(port, baudrate, idle_gap_ms, timeout, csv_path=None, raw_path=None):
    print(f"Opening {port} at {baudrate} baud")
    print(f"Frame split idle gap: {idle_gap_ms} ms")
    print("Listening only. Do not type into the bus. Press Ctrl+C to stop.")
    print()

    ser = open_serial(port, baudrate, timeout)

    start_wall = datetime.now().isoformat(timespec="seconds")
    start = time.perf_counter()

    csv_file = None
    csv_writer = None

    if csv_path:
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            "frame_id",
            "wall_start",
            "relative_start_s",
            "relative_end_s",
            "duration_ms",
            "idle_before_ms",
            "baudrate",
            "byte_count",
            "class",
            "confidence",
            "hex",
            "ascii",
        ])

    raw_file = None

    if raw_path:
        raw_file = open(raw_path, "ab")

    frame = bytearray()
    frame_start = None
    last_byte_time = None
    previous_frame_end = None
    frame_id = 0

    idle_gap_s = idle_gap_ms / 1000.0

    try:
        while True:
            b = ser.read(1)
            now = time.perf_counter()
            rel = now - start

            if b:
                if raw_file:
                    raw_file.write(b)
                    raw_file.flush()

                if frame and last_byte_time is not None:
                    gap = now - last_byte_time

                    if gap >= idle_gap_s:
                        t0 = frame_start
                        t1 = last_byte_time
                        data = bytes(frame)
                        duration_ms = (t1 - t0) * 1000.0

                        idle_before_ms = None
                        if previous_frame_end is not None:
                            idle_before_ms = (t0 - previous_frame_end) * 1000.0

                        label, confidence = classify_frame(
                            data=data,
                            duration_ms=duration_ms,
                            idle_before_ms=idle_before_ms,
                        )

                        print_frame(
                            frame_id=frame_id,
                            t0=t0,
                            t1=t1,
                            data=data,
                            idle_before_ms=idle_before_ms,
                            label=label,
                            confidence=confidence,
                        )

                        if csv_writer:
                            csv_writer.writerow([
                                frame_id,
                                start_wall,
                                f"{t0:.9f}",
                                f"{t1:.9f}",
                                f"{duration_ms:.6f}",
                                "" if idle_before_ms is None else f"{idle_before_ms:.6f}",
                                baudrate,
                                len(data),
                                label,
                                f"{confidence:.3f}",
                                hex_bytes(data),
                                ascii_preview(data),
                            ])
                            csv_file.flush()

                        previous_frame_end = t1
                        frame_id += 1
                        frame = bytearray()
                        frame_start = None

                if not frame:
                    frame_start = rel

                frame.extend(b)
                last_byte_time = rel

            else:
                if frame and last_byte_time is not None:
                    gap = rel - last_byte_time

                    if gap >= idle_gap_s:
                        t0 = frame_start
                        t1 = last_byte_time
                        data = bytes(frame)
                        duration_ms = (t1 - t0) * 1000.0

                        idle_before_ms = None
                        if previous_frame_end is not None:
                            idle_before_ms = (t0 - previous_frame_end) * 1000.0

                        label, confidence = classify_frame(
                            data=data,
                            duration_ms=duration_ms,
                            idle_before_ms=idle_before_ms,
                        )

                        print_frame(
                            frame_id=frame_id,
                            t0=t0,
                            t1=t1,
                            data=data,
                            idle_before_ms=idle_before_ms,
                            label=label,
                            confidence=confidence,
                        )

                        if csv_writer:
                            csv_writer.writerow([
                                frame_id,
                                start_wall,
                                f"{t0:.9f}",
                                f"{t1:.9f}",
                                f"{duration_ms:.6f}",
                                "" if idle_before_ms is None else f"{idle_before_ms:.6f}",
                                baudrate,
                                len(data),
                                label,
                                f"{confidence:.3f}",
                                hex_bytes(data),
                                ascii_preview(data),
                            ])
                            csv_file.flush()

                        previous_frame_end = t1
                        frame_id += 1
                        frame = bytearray()
                        frame_start = None

    except KeyboardInterrupt:
        print()
        print("Stopping.")

        if frame:
            t0 = frame_start
            t1 = last_byte_time
            data = bytes(frame)
            duration_ms = (t1 - t0) * 1000.0

            idle_before_ms = None
            if previous_frame_end is not None:
                idle_before_ms = (t0 - previous_frame_end) * 1000.0

            label, confidence = classify_frame(
                data=data,
                duration_ms=duration_ms,
                idle_before_ms=idle_before_ms,
            )

            print_frame(
                frame_id=frame_id,
                t0=t0,
                t1=t1,
                data=data,
                idle_before_ms=idle_before_ms,
                label=label,
                confidence=confidence,
            )

    finally:
        ser.close()

        if csv_file:
            csv_file.close()

        if raw_file:
            raw_file.close()


def auto_probe(port, idle_gap_ms, timeout, seconds_per_baud):
    print(f"Auto-probing {port}")
    print("This only listens. It does not transmit.")
    print()

    for baud in COMMON_BAUDRATES:
        print(f"===== trying {baud} baud for {seconds_per_baud}s =====")

        try:
            ser = open_serial(port, baud, timeout=0.02)
        except Exception as e:
            print(f"Could not open {port}: {e}")
            return

        start = time.perf_counter()
        data = bytearray()

        while time.perf_counter() - start < seconds_per_baud:
            chunk = ser.read(256)
            if chunk:
                data.extend(chunk)

        ser.close()

        if data:
            print(f"received {len(data)} bytes")
            print(hex_bytes(bytes(data[:128])))
            print(ascii_preview(bytes(data[:128])))
        else:
            print("no bytes")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Real-time RS485 UART sniffer for Waveshare USB-RS485 adapters on Windows."
    )

    parser.add_argument("--list", action="store_true", help="List COM ports and exit")
    parser.add_argument("--port", help="COM port, for example COM3")
    parser.add_argument("--baud", type=int, default=9600, help="Baudrate")
    parser.add_argument("--idle-gap-ms", type=float, default=5.0, help="Idle gap that splits frames")
    parser.add_argument("--timeout", type=float, default=0.01, help="Serial read timeout in seconds")
    parser.add_argument("--csv", help="Write decoded frame log to CSV")
    parser.add_argument("--raw", help="Append raw received bytes to binary file")
    parser.add_argument("--auto-probe", action="store_true", help="Try common baudrates")
    parser.add_argument("--probe-seconds", type=float, default=5.0, help="Seconds per baudrate during auto probe")

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if not args.port:
        print("Missing --port. Use --list first.")
        print("Example:")
        print("  py rs485_protocol_sniffer.py --list")
        print("  py rs485_protocol_sniffer.py --port COM3 --baud 9600")
        sys.exit(1)

    if args.auto_probe:
        auto_probe(
            port=args.port,
            idle_gap_ms=args.idle_gap_ms,
            timeout=args.timeout,
            seconds_per_baud=args.probe_seconds,
        )
        return

    sniff(
        port=args.port,
        baudrate=args.baud,
        idle_gap_ms=args.idle_gap_ms,
        timeout=args.timeout,
        csv_path=args.csv,
        raw_path=args.raw,
    )


if __name__ == "__main__":
    main()