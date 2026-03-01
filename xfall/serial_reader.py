"""
Serial Reader — Reads CSI data from ESP32 over USB serial.

Usage (as module):
    from serial_reader import CSISerialReader

    reader = CSISerialReader(port="COM6")
    for frame in reader.stream():
        print(f"RSSI={frame.rssi}, subcarriers={frame.n_subcarriers}")
"""

import serial
import numpy as np
from typing import Iterator
from XFall import CSIFrame, parse_csi_line


class CSISerialReader:
    """Reads and parses CSI data from ESP32 serial port."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0, debug: bool = False):
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

    def close(self):
        """Close the serial connection."""
        self._running = False
        if self._serial and self._serial.is_open:
            self._serial.close()
            print("[serial_reader] Serial port closed")

    def stream(self) -> Iterator[CSIFrame]:
        """
        Generator that yields parsed CSIFrame objects.
        Logs all received lines/frames to the console.
        """
        if not self._serial or not self._serial.is_open:
            self.open()

        self._running = True
        frame_count = 0
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
                        frame_count += 1
                        print(f"[serial_reader] #{frame_count} | "
                              f"RSSI={frame.rssi} ch={frame.channel} "
                              f"subs={frame.n_subcarriers} "
                              f"amp_mean={frame.amplitude.mean():.1f}")
                        yield frame
                    else:
                        print(f"[serial_reader] (non-CSI) {line[:80]}")

                except serial.SerialException as e:
                    if self._running:
                        print(f"[serial_reader] Serial error: {e}")
                    break
        except KeyboardInterrupt:
            pass
        finally:
            print(f"\n[serial_reader] Total frames received: {frame_count}")
            self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
