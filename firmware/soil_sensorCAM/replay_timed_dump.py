import argparse
import re
import time
from pathlib import Path

import serial


LINE_RE = re.compile(
    r"^\s*([0-9]+\.[0-9]+)s\s+([0-9A-Fa-f]{2})\s+"
)


def parse_dump(path: Path):
    events = []

    text = path.read_text(encoding="utf-8", errors="replace")

    for line in text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue

        t = float(m.group(1))
        b = int(m.group(2), 16)
        events.append((t, b))

    if not events:
        raise RuntimeError("No timestamped bytes found in dump file.")

    return events


def trim_before_main_sequence(events, max_idle_s=1.0):
    if len(events) < 2:
        return events

    gaps = []

    for i in range(1, len(events)):
        gap = events[i][0] - events[i - 1][0]
        gaps.append((gap, i))

    biggest_gap, index_after_gap = max(gaps)

    if biggest_gap >= max_idle_s:
        print(f"Trimming isolated prelude before largest gap: {biggest_gap:.3f} s")
        return events[index_after_gap:]

    return events


def normalize_times(events):
    t0 = events[0][0]
    return [(t - t0, b) for t, b in events]


def print_summary(events):
    print(f"byte count: {len(events)}")
    print(f"start time: {events[0][0]:.6f}s")
    print(f"end time:   {events[-1][0]:.6f}s")
    print(f"duration:   {events[-1][0] - events[0][0]:.6f}s")

    first_bytes = " ".join(f"{b:02X}" for _, b in events[:32])
    print(f"first bytes: {first_bytes}")

    headers = []
    previous_t = None

    for t, b in events:
        if previous_t is None or (t - previous_t) > 0.003:
            headers.append((t, b))
        previous_t = t

    print()
    print("candidate burst starts, using gap > 3 ms:")
    for t, b in headers:
        print(f"  {t:.6f}s  {b:02X}")


def replay(port, baud, events, repeat=1, inter_repeat_s=0.1, speed=1.0):
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
        normalized = normalize_times(events)

        for r in range(repeat):
            print(f"replay {r + 1}/{repeat}")

            start = time.perf_counter()

            for target_t, b in normalized:
                target_t = target_t / speed

                while True:
                    now = time.perf_counter() - start
                    remaining = target_t - now

                    if remaining <= 0:
                        break

                    if remaining > 0.002:
                        time.sleep(remaining - 0.001)
                    else:
                        time.sleep(0)

                ser.write(bytes([b]))

            ser.flush()

            if r + 1 < repeat:
                time.sleep(inter_repeat_s)

    finally:
        ser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--port", default="COM4")
    parser.add_argument("--baud", type=int, default=38400)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--inter-repeat-ms", type=float, default=100.0)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--keep-leading-idle", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    events = parse_dump(Path(args.file))

    if not args.keep_leading_idle:
        events = trim_before_main_sequence(events)

    print_summary(events)

    if args.dry_run:
        print()
        print("dry run only, nothing sent")
        return

    print()
    input("Disconnect the original controller data pair. Press ENTER to replay, or Ctrl+C to abort.")

    replay(
        port=args.port,
        baud=args.baud,
        events=events,
        repeat=args.repeat,
        inter_repeat_s=args.inter_repeat_ms / 1000.0,
        speed=args.speed,
    )

    print("done")


if __name__ == "__main__":
    main()