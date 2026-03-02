"""
EtherGuard — Real-Time Fall Detector
======================================
Loads the trained model and runs live inference on CSI from csi_recv_router.

Usage:
    python detect.py --port /dev/ttyUSB0     # live
    python detect.py --simulate              # no hardware

Baud: 115200
"""

import sys
import time
import json
import argparse
import numpy as np
import joblib
from pathlib import Path
from collections import deque
from datetime import datetime
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).parent))
from csi_parser import CSIFrame, parse_csi_line
from event_logger import EventLogger

CLASSES    = ['not_fall', 'fall']
MODEL_DIR  = Path(__file__).parent.parent / 'data' / 'models'
EVENTS_DB  = Path(__file__).parent.parent / 'data' / 'events.db'
BAUD_RATE  = 115200

# Default BIN_SIZE — overridden by meta.json if available
BIN_SIZE   = 4


# ─── Feature extraction (MUST match train_local.py) ─────────────────────
def bandpass(data, fs, lowcut=0.3, highcut=None, order=4):
    nyq = fs / 2.0
    if highcut is None:
        highcut = nyq * 0.8
    low  = max(lowcut / nyq, 0.01)
    high = min(highcut / nyq, 0.99)
    if low >= high:
        return data
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data, axis=0)


def bin_subcarriers(window, bin_size):
    T, n_sub = window.shape
    n_bins = n_sub // bin_size
    if n_bins == 0:
        return window
    trimmed = window[:, :n_bins * bin_size]
    return trimmed.reshape(T, n_bins, bin_size).mean(axis=2)


def extract_features(window, fs, bin_size):
    try:
        filtered = bandpass(window, fs=fs)
    except Exception:
        filtered = window
    binned = bin_subcarriers(filtered, bin_size)
    mean   = binned.mean(axis=0)
    std    = binned.std(axis=0)
    energy = (binned ** 2).sum(axis=0)
    rng    = binned.max(axis=0) - binned.min(axis=0)
    global_feats = np.array([
        mean.mean(), std.mean(), energy.sum(), rng.mean()
    ], dtype=np.float32)
    return np.concatenate([mean, std, energy, rng, global_feats]).astype(np.float32)


# ─── Alert FSM ───────────────────────────────────────────────────────────
class AlertFSM:
    IDLE, MONITORING, ALERT, COOLDOWN = 'idle', 'monitoring', 'alert', 'cooldown'

    def __init__(self, threshold=0.65, cooldown_sec=10.0, logger=None):
        self.threshold    = threshold
        self.cooldown_sec = cooldown_sec
        self.logger       = logger
        self.state        = self.IDLE
        self._consec      = 0
        self._clear_t     = None

    def update(self, label, conf):
        is_fall = (label == 'fall' and conf >= self.threshold)
        if self.state == self.IDLE:
            if is_fall:
                self._consec = 1; self.state = self.MONITORING
        elif self.state == self.MONITORING:
            if is_fall:
                self._consec += 1
                if self._consec >= 2:
                    self.state = self.ALERT
                    print("\n" + "!" * 60)
                    print("  *** FALL DETECTED ***")
                    print(f"  Confidence: {conf:.1%}")
                    print(f"  Time: {datetime.now().strftime('%H:%M:%S')}")
                    print("!" * 60 + "\n")
                    if self.logger:
                        self.logger.log_event('fall_detected', conf,
                                              f"consec={self._consec}")
            else:
                self._consec = 0; self.state = self.IDLE
        elif self.state == self.ALERT:
            self.state = self.COOLDOWN
            self._clear_t = None if is_fall else time.time()
        elif self.state == self.COOLDOWN:
            if is_fall:
                self._clear_t = None
            else:
                if self._clear_t is None:
                    self._clear_t = time.time()
                if time.time() - self._clear_t >= self.cooldown_sec:
                    self.state = self.IDLE; self._consec = 0
                    print("[alert] All clear — idle")
                    if self.logger:
                        self.logger.log_event('all_clear', 0.0, '')
        return self.state


# ─── Detector ────────────────────────────────────────────────────────────
class FallDetector:
    ICONS = {'idle': '[OK]', 'monitoring': '[??]', 'alert': '[!!]', 'cooldown': '[..]'}

    def __init__(self, model_path, scaler_path, meta_path,
                 threshold=0.65, db_path=None):
        print(f"[model] Loading {model_path.name}", flush=True)
        self.clf    = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        with open(meta_path) as f:
            self.meta = json.load(f)

        self.bin_size  = self.meta.get('bin_size', BIN_SIZE)
        self.n_feats   = self.meta['n_features']
        self.fs        = self.meta.get('fs', 25.0)

        # Window size: use 2 seconds worth of samples at measured rate
        self.window_size = max(int(2.0 * self.fs), 10)
        self.step_size   = max(self.window_size // 2, 1)

        # Infer n_subcarriers from feature count
        n_bins = (self.n_feats - 4) // 4
        self.n_sub = n_bins * self.bin_size

        print(f"[model] fs={self.fs:.0f}Hz  subs={self.n_sub}  "
              f"bins={n_bins}  feats={self.n_feats}", flush=True)
        print(f"[model] window={self.window_size} ({self.window_size/self.fs:.1f}s)  "
              f"step={self.step_size} ({self.step_size/self.fs:.1f}s)", flush=True)
        print(f"[model] CV_F1={self.meta.get('cv_f1_mean', '?')}", flush=True)

        self.buffer = deque(maxlen=self.window_size)
        self._steps = 0
        self._total = 0

        logger = EventLogger(str(db_path)) if db_path else None
        self.fsm = AlertFSM(threshold=threshold, logger=logger)

    def _align(self, amp):
        n = len(amp)
        if n == self.n_sub:
            return amp
        if n > self.n_sub:
            return amp[:self.n_sub]
        out = np.zeros(self.n_sub, dtype=np.float32)
        out[:n] = amp
        return out

    def add_frame(self, frame):
        self.buffer.append(self._align(frame.amplitude))
        self._steps += 1
        if len(self.buffer) == self.window_size and self._steps >= self.step_size:
            self._steps = 0
            self._infer()

    def _infer(self):
        window  = np.array(list(self.buffer), dtype=np.float32)
        feats   = extract_features(window, fs=self.fs,
                                   bin_size=self.bin_size).reshape(1, -1)
        feats_s = self.scaler.transform(feats)
        probs   = self.clf.predict_proba(feats_s)[0]
        pred_i  = int(np.argmax(probs))
        conf    = float(probs[pred_i])
        label   = CLASSES[pred_i]

        self._total += 1
        state = self.fsm.update(label, conf)
        icon  = self.ICONS.get(state, '    ')
        bar   = '█' * int(conf * 20) + '░' * (20 - int(conf * 20))
        print(f"\r  {icon} #{self._total:4d} | "
              f"{'FALL    ' if label == 'fall' else 'not_fall'} "
              f"[{bar}] {conf:.0%}  ", end='', flush=True)


# ─── Simulate ────────────────────────────────────────────────────────────
def simulate_stream(n_sub=64, rate=25.0):
    interval = 1.0 / rate
    phases = ['idle', 'idle', 'walk', 'fall']
    t, dur = 0.0, 5.0
    print(f"[sim] idle→idle→walk→fall (5s each, {rate:.0f} Hz)")
    while True:
        ph = phases[int(t / dur) % len(phases)]
        if ph == 'idle':
            amp = 8.0 + np.random.randn(n_sub) * 0.5
        elif ph == 'walk':
            amp = 8.0 + np.sin(2*np.pi*1.5*t)*3 + np.random.randn(n_sub)
        else:
            prog = (t % dur) / dur
            spike = 30 * max(0, 0.5 - abs(prog - 0.25)) / 0.25
            amp = 8.0 + spike + np.random.randn(n_sub) * 2
        amp = np.abs(amp).astype(np.float32)
        yield CSIFrame(
            timestamp=int(t*1e6), rssi=-55, mac='AA:BB:CC:DD:EE:FF',
            channel=6, n_subcarriers=n_sub, amplitude=amp,
            phase=np.zeros(n_sub, dtype=np.float32),
            complex_csi=amp.astype(np.complex64))
        time.sleep(interval)
        t += interval


def main():
    ap = argparse.ArgumentParser(description='EtherGuard Fall Detector')
    ap.add_argument('--port',      default='/dev/ttyUSB0')
    ap.add_argument('--baud',      type=int, default=BAUD_RATE)
    ap.add_argument('--threshold', type=float, default=0.65)
    ap.add_argument('--simulate',  action='store_true')
    ap.add_argument('--no-db',     action='store_true')
    args = ap.parse_args()

    model_path  = MODEL_DIR / 'rf_model.pkl'
    scaler_path = MODEL_DIR / 'scaler.pkl'
    meta_path   = MODEL_DIR / 'meta.json'
    for p in [model_path, scaler_path, meta_path]:
        if not p.exists():
            print(f"[ERROR] Missing {p}\n  Run: python train_local.py")
            sys.exit(1)

    db_path = None if args.no_db else EVENTS_DB
    if db_path:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("  EtherGuard — Real-Time Fall Detection")
    print("=" * 60)
    print(f"  Mode:      {'SIMULATE' if args.simulate else f'LIVE ({args.port} @ {args.baud})'}")
    print(f"  Threshold: {args.threshold:.0%}")
    print("=" * 60 + "\n")

    detector = FallDetector(model_path, scaler_path, meta_path,
                            threshold=args.threshold, db_path=db_path)

    try:
        if args.simulate:
            for frame in simulate_stream():
                detector.add_frame(frame)
        else:
            import serial
            ser = serial.Serial(args.port, args.baud, timeout=2.0)
            ser.reset_input_buffer()
            print(f"[serial] {args.port} @ {args.baud}. Ctrl+C to stop.\n",
                  flush=True)
            while True:
                try:
                    raw = ser.readline()
                except serial.SerialException as e:
                    print(f"\n[serial] {e}")
                    break
                if not raw:
                    continue
                frame = parse_csi_line(raw.decode('utf-8', errors='replace'))
                if frame is not None:
                    detector.add_frame(frame)
    except KeyboardInterrupt:
        print("\n\n[detect] Stopped.")
    finally:
        print(f"\n  Inferences: {detector._total}")
        print("=" * 60)


if __name__ == '__main__':
    main()
