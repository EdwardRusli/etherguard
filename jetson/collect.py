"""
EtherGuard — Guided CSI Data Collector
=======================================
Builds a labelled training dataset from live ESP32 CSI in ~10-15 minutes.

Uses csi_recv_router firmware (pings router via ICMP).
Actual CSI rate observed: ~25 Hz (depends on router response time).

Usage:
    python collect.py --port /dev/ttyUSB0

Collection plan:
  • 5 × 30 s rounds of "not_fall" (sitting, walking, standing)
  • 5 × 30 s rounds of "fall"     (controlled falls)
  Each 2 s window → one training sample.  Stride 1 s.

Output: data/training/<label>_<timestamp>.npz
"""

import sys
import time
import argparse
import numpy as np
import serial
from pathlib import Path
from collections import deque
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from csi_parser import parse_csi_line

# ─── tunables ────────────────────────────────
ROUND_SEC     = 30      # seconds per collection round
ROUNDS_EACH   = 5       # rounds per label
BAUD_RATE     = 115200  # csi_recv_router baud

LABELS        = ['not_fall', 'fall']
OUTPUT_DIR    = Path(__file__).parent.parent / 'data' / 'training'


def countdown(seconds: int, msg: str):
    for i in range(seconds, 0, -1):
        print(f"\r  {msg} — {i:2d}s remaining...  ", end='', flush=True)
        time.sleep(1)
    print()


def measure_csi_rate(ser: serial.Serial, duration: float = 3.0) -> float:
    """Measure actual CSI rate by counting frames over a period."""
    t_end = time.time() + duration
    count = 0
    while time.time() < t_end:
        raw = ser.readline()
        if raw:
            frame = parse_csi_line(raw.decode('utf-8', errors='replace'))
            if frame is not None:
                count += 1
    rate = count / duration
    return rate


def collect_window_batch(ser: serial.Serial, duration_sec: float,
                          label: str, window_size: int,
                          step_size: int) -> list[np.ndarray]:
    """
    Read CSI for `duration_sec` seconds.
    Returns list of windows, each shape: (window_size, n_subcarriers).
    """
    buffer  = deque(maxlen=window_size)
    windows = []
    steps   = 0
    frames  = 0
    t_end   = time.time() + duration_sec

    while time.time() < t_end:
        try:
            raw = ser.readline()
        except serial.SerialException:
            break
        if not raw:
            continue

        frame = parse_csi_line(raw.decode('utf-8', errors='replace'))
        if frame is None:
            continue

        buffer.append(frame.amplitude)
        frames += 1
        steps  += 1

        remaining = t_end - time.time()
        print(
            f"\r  [{label:8s}] frames={frames:5d} | "
            f"windows={len(windows):3d} | "
            f"amp={frame.amplitude.mean():6.1f} | "
            f"RSSI={frame.rssi:4d} dBm | "
            f"{remaining:5.1f}s left   ",
            end='', flush=True
        )

        if len(buffer) == window_size and steps >= step_size:
            windows.append(np.array(list(buffer), dtype=np.float32))
            steps = 0

    print()
    return windows


def save_npz(windows: list[np.ndarray], label: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = OUTPUT_DIR / f"{label}_{ts}.npz"
    arr = np.stack(windows, axis=0)   # (N, window_size, n_subcarriers)
    np.savez_compressed(out, X=arr, label=label)
    print(f"  Saved {arr.shape[0]} windows (shape {arr.shape}) → {out}")
    return arr.shape[0]


def main():
    ap = argparse.ArgumentParser(description='EtherGuard CSI Data Collector')
    ap.add_argument('--port',    default='/dev/ttyUSB0')
    ap.add_argument('--baud',    type=int, default=BAUD_RATE)
    ap.add_argument('--rounds',  type=int, default=ROUNDS_EACH,
                    help=f'Rounds per label (default {ROUNDS_EACH})')
    ap.add_argument('--secs',    type=int, default=ROUND_SEC,
                    help=f'Seconds per round (default {ROUND_SEC})')
    ap.add_argument('--window',  type=float, default=2.0,
                    help='Window duration in seconds (default 2.0)')
    args = ap.parse_args()

    print()
    print("=" * 60)
    print("  EtherGuard — CSI Training Data Collector")
    print("=" * 60)
    print(f"  Port:    {args.port} @ {args.baud} baud")
    print(f"  Labels:  {LABELS}")
    print(f"  Rounds:  {args.rounds} per label × {args.secs}s each")
    print("=" * 60)
    print()
    input("  Press ENTER when ESP32 is running csi_recv_router...")

    # Open serial
    try:
        ser = serial.Serial(args.port, args.baud, timeout=2.0)
        ser.reset_input_buffer()
        print(f"[serial] Opened {args.port} @ {args.baud}", flush=True)
    except serial.SerialException as e:
        print(f"[ERROR] Cannot open serial port: {e}")
        sys.exit(1)

    # ── Measure actual CSI rate ──
    print("\n  Measuring CSI rate (3 s)...", flush=True)
    csi_rate = measure_csi_rate(ser, 3.0)
    print(f"  Measured CSI rate: {csi_rate:.1f} Hz")

    if csi_rate < 5:
        print("  ⚠ VERY LOW CSI RATE — check ESP32 + router")
        sys.exit(1)

    # Calculate window/step sizes based on measured rate
    window_size = max(int(args.window * csi_rate), 10)
    step_size   = max(window_size // 2, 1)   # 50% overlap

    # Estimate windows per round
    est_windows = max(1, int((args.secs - args.window) / (step_size / csi_rate)))
    est_total   = est_windows * args.rounds * len(LABELS)

    print(f"  Window:  {window_size} samples ({args.window:.1f}s @ {csi_rate:.0f} Hz)")
    print(f"  Step:    {step_size} samples ({step_size/csi_rate:.1f}s stride)")
    print(f"  Est. ~{est_windows} windows/round, ~{est_total} total")
    est_min = (args.rounds * len(LABELS) * (args.secs + 6)) / 60
    print(f"  Est. time: ~{est_min:.0f} min")
    print()

    # ── Collection ──
    total_windows = {label: 0 for label in LABELS}

    for label in LABELS:
        print(f"{'─' * 60}")
        print(f"  COLLECTING: [{label.upper()}]")
        if label == 'not_fall':
            print("  → Sit, stand, walk around normally. AVOID sudden movements.")
        else:
            print("  → Perform controlled falls / quickly lean and get back up.")
        print(f"{'─' * 60}")

        label_windows = []

        for rnd in range(1, args.rounds + 1):
            print(f"\n  Round {rnd}/{args.rounds} — get ready...")
            countdown(3, "Starting in")

            print(f"  ▶  Collecting '{label}' for {args.secs}s — GO!")
            windows = collect_window_batch(ser, args.secs, label,
                                           window_size, step_size)
            label_windows.extend(windows)
            print(f"  ✓  Round {rnd}: {len(windows)} windows "
                  f"(total: {len(label_windows)})")

            if rnd < args.rounds:
                print("  Rest (3s)...")
                time.sleep(3)

        if label_windows:
            saved = save_npz(label_windows, label)
            total_windows[label] = saved
        else:
            print(f"  [WARN] No windows collected for '{label}'!")

    ser.close()

    # ── Summary ──
    print()
    print("=" * 60)
    print("  Collection Complete!")
    print("=" * 60)
    for label, count in total_windows.items():
        print(f"  {label:10s}: {count:4d} windows")
    total = sum(total_windows.values())
    print(f"  {'TOTAL':10s}: {total:4d} windows")
    print(f"\n  Data saved to: {OUTPUT_DIR}")
    print("\n  Next steps:")
    print("    python validate_data.py   # check data quality")
    print("    python train_local.py     # train model (~2 min)")
    print("=" * 60)


if __name__ == '__main__':
    main()
