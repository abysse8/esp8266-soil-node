import argparse
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

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


def read_live_events(port, baud, seconds, timeout):
    ser = serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=timeout,
        write_timeout=0,
    )

    ser.reset_input_buffer()

    print(f"listening on {port} at {baud} baud for {seconds}s")
    print("press Ctrl+C to stop early")
    print()

    events = []
    t0 = time.perf_counter()

    try:
        while True:
            now = time.perf_counter()

            if now - t0 >= seconds:
                break

            b = ser.read(1)

            if not b:
                continue

            t = time.perf_counter() - t0
            events.append((t, b[0]))

    except KeyboardInterrupt:
        print()
        print("stopped early")

    finally:
        ser.close()

    return events


def segment_by_idle(events, idle_ms):
    if not events:
        return []

    idle_s = idle_ms / 1000.0

    messages = []
    current = [events[0]]

    for prev, cur in zip(events, events[1:]):
        prev_t, _ = prev
        cur_t, _ = cur

        if cur_t - prev_t >= idle_s:
            messages.append(current)
            current = [cur]
        else:
            current.append(cur)

    if current:
        messages.append(current)

    return messages


def hex_bytes(data, max_len=None):
    if max_len is not None and len(data) > max_len:
        shown = data[:max_len]
        return " ".join(f"{b:02X}" for b in shown) + f" ... +{len(data) - max_len} bytes"

    return " ".join(f"{b:02X}" for b in data)


def summarize_message(msg, msg_id, previous_end=None, preview_len=96):
    start_t = msg[0][0]
    end_t = msg[-1][0]
    duration_ms = (end_t - start_t) * 1000.0

    idle_before_ms = None
    if previous_end is not None:
        idle_before_ms = (start_t - previous_end) * 1000.0

    data = bytes(b for _, b in msg)
    counts = Counter(data)

    top = " ".join(
        f"{byte:02X}:{count}"
        for byte, count in counts.most_common(12)
    )

    unique_sorted = " ".join(f"{b:02X}" for b in sorted(counts.keys()))

    print()
    print(f"[msg {msg_id:04d}]")
    print(f"  start:        {start_t:.6f}s")
    print(f"  end:          {end_t:.6f}s")
    print(f"  duration:     {duration_ms:.3f} ms")
    print(f"  idle_before:  {'n/a' if idle_before_ms is None else f'{idle_before_ms:.3f} ms'}")
    print(f"  bytes:        {len(data)}")
    print(f"  first/last:   {data[0]:02X} / {data[-1]:02X}")
    print(f"  unique_count: {len(counts)}")
    print(f"  unique:       {unique_sorted}")
    print(f"  top:          {top}")
    print(f"  prefix4:      {hex_bytes(data[:4])}")
    print(f"  prefix8:      {hex_bytes(data[:8])}")
    print(f"  prefix12:     {hex_bytes(data[:12])}")
    print(f"  hex:          {hex_bytes(data, preview_len)}")

    return {
        "id": msg_id,
        "start": start_t,
        "end": end_t,
        "duration_ms": duration_ms,
        "idle_before_ms": idle_before_ms,
        "data": data,
        "counts": counts,
    }


def print_global_summary(events, messages):
    all_data = bytes(b for _, b in events)
    counts = Counter(all_data)

    print()
    print("=" * 80)
    print("GLOBAL SUMMARY")
    print("=" * 80)
    print(f"total bytes:    {len(all_data)}")
    print(f"messages:       {len(messages)}")

    if events:
        print(f"capture span:   {events[-1][0] - events[0][0]:.6f}s")

    print()
    print("top symbols:")
    for byte, count in counts.most_common(24):
        pct = 100.0 * count / max(1, len(all_data))
        print(f"  {byte:02X}: {count:8d}  {pct:6.2f}%")

    print()


def print_prefix_groups(summaries, prefix_len):
    groups = defaultdict(list)

    for s in summaries:
        data = s["data"]

        if len(data) >= prefix_len:
            prefix = data[:prefix_len]
        else:
            prefix = data

        groups[prefix].append(s)

    print()
    print("=" * 80)
    print(f"PREFIX GROUPS, prefix_len={prefix_len}")
    print("=" * 80)

    for prefix, items in sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True):
        ids = ", ".join(str(i["id"]) for i in items[:20])
        lengths = Counter(len(i["data"]) for i in items)
        length_text = " ".join(f"{k}:{v}" for k, v in sorted(lengths.items()))

        print()
        print(f"prefix {hex_bytes(prefix)}")
        print(f"  count:   {len(items)}")
        print(f"  msg ids: {ids}")
        print(f"  lengths: {length_text}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--list", action="store_true")

    parser.add_argument("--port", default="COM4")
    parser.add_argument("--baud", type=int, default=38400)
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--timeout", type=float, default=0.001)

    parser.add_argument("--file", help="analyze a pasted dump file instead of live COM port")

    parser.add_argument("--idle-ms", type=float, default=3.0)
    parser.add_argument("--min-bytes", type=int, default=1)
    parser.add_argument("--preview-len", type=int, default=96)

    parser.add_argument("--prefix-groups", action="store_true")
    parser.add_argument("--prefix-len", type=int, default=8)

    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    if args.file:
        print(f"reading file: {args.file}")
        events = parse_dump_file(args.file)
    else:
        events = read_live_events(
            port=args.port,
            baud=args.baud,
            seconds=args.seconds,
            timeout=args.timeout,
        )

    if not events:
        print("no bytes found")
        return

    print()
    print(f"events read: {len(events)}")
    print(f"idle_ms:     {args.idle_ms}")

    messages = segment_by_idle(events, idle_ms=args.idle_ms)
    messages = [m for m in messages if len(m) >= args.min_bytes]

    print_global_summary(events, messages)

    summaries = []
    previous_end = None

    for i, msg in enumerate(messages):
        summary = summarize_message(
            msg=msg,
            msg_id=i,
            previous_end=previous_end,
            preview_len=args.preview_len,
        )

        summaries.append(summary)
        previous_end = msg[-1][0]

    if args.prefix_groups:
        print_prefix_groups(summaries, prefix_len=args.prefix_len)


if __name__ == "__main__":
    main()