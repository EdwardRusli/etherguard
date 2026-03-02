"""
CSI Data Parser — Parses csi_recv_router CSV lines into structured CSIFrame.

The csi_recv_router example (ESP-IDF / esp-csi toolkit) outputs lines like:

  CSI_DATA,<seq>,<mac>,<rssi>,<rate>,<sig_mode>,<mcs>,<bandwidth>,
  <smoothing>,<not_sounding>,<aggregation>,<stbc>,<fec_coding>,<sgi>,
  <noise_floor>,<ampdu_cnt>,<channel>,<secondary_channel>,
  <local_timestamp>,<ant>,<sig_len>,<rx_state>,<len>,<first_word>,
  "[i0,r0,i1,r1,...]"

Where CSI data is packed as imag/real int8 pairs (or int16 with gain
compensation). 128 bytes → 64 subcarriers.
"""

import csv
import json
import numpy as np
from io import StringIO
from dataclasses import dataclass, field
from typing import Optional

# Column names matching csi_recv_router ESP32 output (25 fields total)
COLUMNS_ESP32 = [
    'type', 'id', 'mac', 'rssi', 'rate', 'sig_mode', 'mcs', 'bandwidth',
    'smoothing', 'not_sounding', 'aggregation', 'stbc', 'fec_coding', 'sgi',
    'noise_floor', 'ampdu_cnt', 'channel', 'secondary_channel',
    'local_timestamp', 'ant', 'sig_len', 'rx_state', 'len', 'first_word', 'data'
]


@dataclass
class CSIFrame:
    """A single parsed CSI measurement."""
    timestamp: int           # ESP32 local timestamp (µs)
    rssi: int                # RSSI dBm
    mac: str                 # Transmitter MAC
    channel: int             # WiFi channel
    n_subcarriers: int       # Number of OFDM subcarriers
    amplitude: np.ndarray    # |CSI| per subcarrier (float32)
    phase: np.ndarray        # angle(CSI) per subcarrier (float32, radians)
    complex_csi: np.ndarray  # Complex CSI (complex64)
    seq: int = 0             # Packet sequence number
    raw_metadata: dict = field(default_factory=dict)


def parse_csi_line(line: str) -> Optional[CSIFrame]:
    """
    Parse one CSI_DATA serial line from csi_recv_router into a CSIFrame.
    Returns None for non-CSI lines (logs, heartbeats, etc.).
    """
    if isinstance(line, bytes):
        line = line.decode('utf-8', errors='replace')
    line = line.strip()

    # Only process lines that start with CSI_DATA
    if not line.startswith('CSI_DATA'):
        return None

    try:
        reader = csv.reader(StringIO(line))
        fields = next(reader)
    except (csv.Error, StopIteration):
        return None

    if len(fields) != len(COLUMNS_ESP32):
        return None

    # Parse the CSI JSON array: "[i0,r0,i1,r1,...]"
    try:
        csi_raw = json.loads(fields[-1])
    except (json.JSONDecodeError, IndexError, ValueError):
        return None

    # Validate length vs declared 'len' field (byte count)
    try:
        declared_len = int(fields[COLUMNS_ESP32.index('len')])
    except (ValueError, IndexError):
        return None

    if declared_len != len(csi_raw):
        return None

    # Build complex CSI: pairs are (imag, real) → complex(real, imag)
    n_sub = len(csi_raw) // 2
    if n_sub == 0:
        return None

    csi_array = np.array(csi_raw, dtype=np.float32)
    imag = csi_array[0::2]  # even indices = imaginary
    real = csi_array[1::2]  # odd indices  = real
    complex_csi = (real + 1j * imag).astype(np.complex64)

    amplitude = np.abs(complex_csi)
    phase     = np.angle(complex_csi)

    meta = dict(zip(COLUMNS_ESP32, fields))

    return CSIFrame(
        timestamp=int(meta.get('local_timestamp', 0)),
        rssi=int(meta.get('rssi', 0)),
        mac=meta.get('mac', ''),
        channel=int(meta.get('channel', 0)),
        n_subcarriers=n_sub,
        amplitude=amplitude,
        phase=phase,
        complex_csi=complex_csi,
        seq=int(meta.get('id', 0)),
        raw_metadata=meta,
    )
