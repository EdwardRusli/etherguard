"""
Serial Reader — Reads CSI data from ESP32 over USB serial and logs to CSV.

Usage (standalone):
    python serial_reader.py --port /dev/ttyUSB0 --output ../data/raw/csi_capture.csv

Usage (as module):
    from serial_reader import CSISerialReader

    reader = CSISerialReader(port="/dev/ttyUSB0")
    for frame in reader.stream():
        print(f"RSSI={frame.rssi}, subcarriers={frame.n_subcarriers}, amp_mean={frame.amplitude.mean():.2f}")
"""

import csv
import sys
import time
import signal
import argparse
import serial
import numpy as np
from pathlib import Path
from typing import Iterator, Optional
from csi_parser import CSIFrame, parse_csi_line, COLUMNS_ESP32


class CSISerialReader:
    """Reads and parses CSI data from ESP32 serial port."""

    def __init__(self, port: str, baudrate: int = 921600, timeout: float = 1.0, debug: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = None
        self.debug = debug
        self._running = False

    def open(self):
        """Open the serial connection."""
        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=self.timeout,
        )
        if not self._serial.is_open:
            raise ConnectionError(f"Failed to open {self.port}")
        self._serial.reset_input_buffer()
        print(f"[serial_reader] Connected to {self.port} @ {self.baudrate} baud")
        print(f"[serial_reader] Press the RST button on the ESP32 now...")

    def close(self):
        """Close the serial connection."""
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("[serial_reader] Serial port closed")

    def stream(self) -> Iterator[CSIFrame]:
        """
        Generator that yields parsed CSIFrame objects.
        Non-CSI lines (boot logs, etc.) are silently skipped.
        """
        if not self._serial or not self._serial.is_open:
            self.open()

        self._running = True
        try:
            while self._running:
                try:
                    raw_line = self._serial.readline()
                    if not raw_line:
                        continue

                    line = raw_line.decode('utf-8', errors='replace').strip()
                    if not line:
                        continue

                    if self.debug:
                        print(f"[DEBUG] {line[:120]}")

                    frame = parse_csi_line(line)
                    if frame is not None:
                        yield frame
                    elif self.debug and 'CSI_DATA' in line:
                        print(f"[DEBUG] CSI line found but parse failed!")

                except serial.SerialException as e:
                    if self._running:
                        print(f"[serial_reader] Serial error: {e}")
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


def save_to_csv(reader: CSISerialReader, output_path: Path, max_frames: Optional[int] = None):
    """
    Read CSI frames and save to a CSV file.
    Each row contains metadata + amplitude values for all subcarriers.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frame_count = 0
    header_written = False

    with open(output_path, 'w', newline='') as f:
        writer = None

        for frame in reader.stream():
            if not header_written:
                # Build CSV header: metadata columns + amplitude_0, amplitude_1, ...
                amp_cols = [f"amp_{i}" for i in range(frame.n_subcarriers)]
                phase_cols = [f"phase_{i}" for i in range(frame.n_subcarriers)]
                header = ['timestamp', 'rssi', 'mac', 'channel', 'n_subcarriers'] + amp_cols + phase_cols
                writer = csv.writer(f)
                writer.writerow(header)
                header_written = True
                print(f"[serial_reader] Detected {frame.n_subcarriers} subcarriers")

            row = [
                frame.timestamp,
                frame.rssi,
                frame.mac,
                frame.channel,
                frame.n_subcarriers,
            ] + frame.amplitude.tolist() + frame.phase.tolist()

            writer.writerow(row)
            frame_count += 1

            if frame_count % 100 == 0:
                print(f"[serial_reader] {frame_count} frames captured", end='\r')

            if max_frames and frame_count >= max_frames:
                print(f"\n[serial_reader] Reached {max_frames} frame limit")
                break

    print(f"\n[serial_reader] Saved {frame_count} frames to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Read CSI data from ESP32 serial port')
    parser.add_argument('-p', '--port', required=True,
                        help='Serial port (e.g. /dev/ttyUSB0 on Linux, COM6 on Windows)')
    parser.add_argument('-o', '--output', default='../data/raw/csi_capture.csv',
                        help='Output CSV file path (default: ../data/raw/csi_capture.csv)')
    parser.add_argument('-n', '--max-frames', type=int, default=None,
                        help='Stop after N frames (default: run until Ctrl+C)')
    parser.add_argument('-b', '--baudrate', type=int, default=921600,
                        help='Serial baud rate (default: 921600)')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Print raw serial lines for debugging')
    args = parser.parse_args()

    reader = CSISerialReader(port=args.port, baudrate=args.baudrate, debug=args.debug)

    print(f"[serial_reader] Capturing CSI to {args.output}")
    print("[serial_reader] Press Ctrl+C to stop\n")

    save_to_csv(reader, Path(args.output), max_frames=args.max_frames)


if __name__ == '__main__':
    main()
