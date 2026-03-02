"""
Serial Reader — Reads csi_recv_router CSV lines from ESP32 over USB serial.

Default baud rate: 115200 (matching csi_recv_router sdkconfig).

Usage (standalone — saves raw CSV):
    python serial_reader.py --port /dev/ttyUSB0 --output ../data/raw/capture.csv

Usage (as module):
    from serial_reader import CSISerialReader
    reader = CSISerialReader('/dev/ttyUSB0')
    for frame in reader.stream():
        print(frame.rssi, frame.amplitude.mean())
"""

import sys
import csv
import time
import argparse
import serial
import numpy as np
from pathlib import Path
from typing import Iterator, Optional

from csi_parser import CSIFrame, parse_csi_line

BAUD_RATE = 115200   # csi_recv_router default


class CSISerialReader:
    """Reads ESP32 CSI data line-by-line from serial."""

    def __init__(self, port: str, baudrate: int = BAUD_RATE,
                 timeout: float = 2.0, debug: bool = False):
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout
        self.debug    = debug
        self._serial  = None
        self._running = False

    def open(self):
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8, parity='N', stopbits=1,
            timeout=self.timeout,
        )
        if not self._serial.is_open:
            raise ConnectionError(f"Cannot open {self.port}")
        self._serial.reset_input_buffer()
        print(f"[serial] Connected {self.port} @ {self.baudrate} baud", flush=True)

    def close(self):
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("[serial] Port closed", flush=True)

    def stream(self) -> Iterator[CSIFrame]:
        """Yield parsed CSIFrame objects; skip non-CSI lines."""
        if not self._serial or not self._serial.is_open:
            self.open()

        self._running = True
        frame_count   = 0
        t0            = time.time()

        try:
            while self._running:
                try:
                    raw = self._serial.readline()
                except serial.SerialException as e:
                    print(f"\n[serial] Error: {e}", flush=True)
                    break

                if not raw:
                    continue

                line = raw.decode('utf-8', errors='replace')

                if self.debug:
                    print(f"[DBG] {line[:120].rstrip()}", flush=True)

                frame = parse_csi_line(line)
                if frame is not None:
                    frame_count += 1
                    elapsed = time.time() - t0
                    rate = frame_count / elapsed if elapsed > 0 else 0
                    print(
                        f"\r[serial] #{frame_count:5d} | "
                        f"RSSI={frame.rssi:4d} dBm | "
                        f"ch={frame.channel:2d} | "
                        f"subs={frame.n_subcarriers:3d} | "
                        f"amp={frame.amplitude.mean():6.1f} | "
                        f"{rate:5.1f} Hz   ",
                        end='', flush=True
                    )
                    yield frame

        except KeyboardInterrupt:
            pass
        finally:
            print(f"\n[serial] Total frames: {frame_count}", flush=True)
            self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


# ─────────────────────────────────────────────────────────────────────────────
def save_to_csv(reader: CSISerialReader, output_path: Path,
                max_frames: Optional[int] = None):
    """Read CSI + write each frame as a CSV row."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame_count    = 0
    header_written = False
    writer         = None

    with open(output_path, 'w', newline='') as f:
        for frame in reader.stream():
            if not header_written:
                amp_cols   = [f"amp_{i}"   for i in range(frame.n_subcarriers)]
                phase_cols = [f"phase_{i}" for i in range(frame.n_subcarriers)]
                header = ['seq', 'timestamp', 'rssi', 'mac', 'channel',
                          'n_subcarriers'] + amp_cols + phase_cols
                writer = csv.writer(f)
                writer.writerow(header)
                header_written = True
                print(f"\n[serial] Subcarriers: {frame.n_subcarriers}", flush=True)

            row = [
                frame.seq, frame.timestamp, frame.rssi,
                frame.mac, frame.channel, frame.n_subcarriers,
            ] + frame.amplitude.tolist() + frame.phase.tolist()
            writer.writerow(row)
            frame_count += 1

            if max_frames and frame_count >= max_frames:
                print(f"\n[serial] Reached {max_frames} frame limit", flush=True)
                break

    print(f"[serial] Saved {frame_count} frames → {output_path}", flush=True)


def main():
    ap = argparse.ArgumentParser(description='ESP32 CSI serial capture')
    ap.add_argument('-p', '--port',       required=True)
    ap.add_argument('-o', '--output',     default='../data/raw/capture.csv')
    ap.add_argument('-n', '--max-frames', type=int, default=None)
    ap.add_argument('-b', '--baudrate',   type=int, default=BAUD_RATE)
    ap.add_argument('-d', '--debug',      action='store_true')
    args = ap.parse_args()

    reader = CSISerialReader(port=args.port, baudrate=args.baudrate,
                             debug=args.debug)
    print(f"[serial] Saving to {args.output}. Press Ctrl+C to stop.\n",
          flush=True)
    save_to_csv(reader, Path(args.output), max_frames=args.max_frames)


if __name__ == '__main__':
    main()
