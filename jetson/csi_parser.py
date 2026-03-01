"""
CSI Data Parser — Converts raw ESP32 CSI serial lines into structured NumPy arrays.

CSI line format (ESP32):
  CSI_DATA,id,mac,rssi,rate,sig_mode,mcs,bandwidth,smoothing,not_sounding,
  aggregation,stbc,fec_coding,sgi,noise_floor,ampdu_cnt,channel,
  secondary_channel,local_timestamp,ant,sig_len,rx_state,len,first_word,
  "[imag0,real0,imag1,real1,...]"

CSI line format (ESP32-C5/C6):
  CSI_DATA,id,mac,rssi,rate,noise_floor,fft_gain,agc_gain,channel,
  local_timestamp,sig_len,rx_state,len,first_word,"[imag0,real0,...]"
"""

import csv
import json
import numpy as np
from io import StringIO
from dataclasses import dataclass, field
from typing import Optional

# Column names for each chip family
COLUMNS_ESP32 = [
    'type', 'id', 'mac', 'rssi', 'rate', 'sig_mode', 'mcs', 'bandwidth',
    'smoothing', 'not_sounding', 'aggregation', 'stbc', 'fec_coding', 'sgi',
    'noise_floor', 'ampdu_cnt', 'channel', 'secondary_channel',
    'local_timestamp', 'ant', 'sig_len', 'rx_state', 'len', 'first_word', 'data'
]

COLUMNS_C5C6 = [
    'type', 'id', 'mac', 'rssi', 'rate', 'noise_floor', 'fft_gain',
    'agc_gain', 'channel', 'local_timestamp', 'sig_len', 'rx_state',
    'len', 'first_word', 'data'
]


@dataclass
class CSIFrame:
    """A single parsed CSI measurement."""
    timestamp: int          # ESP32 local timestamp (microseconds)
    rssi: int               # Signal strength (dBm)
    mac: str                # Transmitter MAC address
    channel: int            # WiFi channel
    n_subcarriers: int      # Number of subcarriers
    amplitude: np.ndarray   # Amplitude per subcarrier (float64)
    phase: np.ndarray       # Phase per subcarrier (float64, radians)
    complex_csi: np.ndarray # Complex CSI per subcarrier (complex64)
    raw_metadata: dict = field(default_factory=dict)  # All other fields


def parse_csi_line(line: str) -> Optional[CSIFrame]:
    """
    Parse a single CSI_DATA serial line into a CSIFrame.
    Returns None if the line is not valid CSI data.
    """
    # Strip serial framing artifacts
    line = line.strip()
    if isinstance(line, bytes):
        line = line.decode('utf-8', errors='replace')
    line = line.lstrip("b'").rstrip("\\r\\n'")

    # Only process CSI_DATA lines
    if 'CSI_DATA' not in line:
        return None

    # Parse as CSV
    try:
        reader = csv.reader(StringIO(line))
        fields = next(reader)
    except (csv.Error, StopIteration):
        return None

    # Detect chip family by column count
    if len(fields) == len(COLUMNS_ESP32):
        columns = COLUMNS_ESP32
    elif len(fields) == len(COLUMNS_C5C6):
        columns = COLUMNS_C5C6
    else:
        return None  # Unknown format

    # Parse the raw CSI array from the last field
    try:
        csi_raw = json.loads(fields[-1])
    except (json.JSONDecodeError, IndexError):
        return None

    # Validate length matches the declared 'len' field
    declared_len = int(fields[-3])
    if declared_len != len(csi_raw):
        return None

    # Convert [imag0, real0, imag1, real1, ...] into complex numbers
    n_subcarriers = len(csi_raw) // 2
    complex_csi = np.zeros(n_subcarriers, dtype=np.complex64)
    for i in range(n_subcarriers):
        real_part = csi_raw[i * 2 + 1]
        imag_part = csi_raw[i * 2]
        complex_csi[i] = complex(real_part, imag_part)

    amplitude = np.abs(complex_csi)
    phase = np.angle(complex_csi)

    # Build metadata dict
    metadata = {col: val for col, val in zip(columns, fields)}

    return CSIFrame(
        timestamp=int(metadata.get('local_timestamp', 0)),
        rssi=int(metadata.get('rssi', 0)),
        mac=metadata.get('mac', ''),
        channel=int(metadata.get('channel', 0)),
        n_subcarriers=n_subcarriers,
        amplitude=amplitude,
        phase=phase,
        complex_csi=complex_csi,
        raw_metadata=metadata,
    )
