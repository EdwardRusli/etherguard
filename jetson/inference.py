"""
Real-Time Inference Pipeline — Live fall detection from ESP32 CSI data.

Reads CSI frames from serial, buffers into 2-second windows,
runs preprocessing + model inference, and triggers alerts.

Usage:
    cd jetson/

    # Live mode (ESP32 connected):
    python inference.py --port COM6 --model ../data/processed/models/model_best.pth \
                        --pca ../data/processed/pca_model.pkl

    # Simulation mode (no hardware):
    python inference.py --simulate --model ../data/processed/models/model_best.pth \
                        --pca ../data/processed/pca_model.pkl
"""

import argparse
import sys
import time
import numpy as np
import joblib
import torch
from pathlib import Path
from collections import deque

from csi_parser import CSIFrame
from preprocessing.filters import filter_csi
from preprocessing.pca import apply_pca
from preprocessing.spectrogram import process_csi_to_spectrograms
from event_logger import EventLogger

# Classes (must match training)
CLASSES = ['fall', 'walk', 'sit', 'idle']


# ── Alert State Machine ────────────────────────────────────────────────

class AlertFSM:
    """
    Alert finite state machine with debounce logic.

    States:
        idle        — no activity of concern
        monitoring  — 1 fall prediction seen, waiting for confirmation
        fall_alert  — confirmed fall (2 consecutive windows ≥ threshold)
        cooldown    — post-alert, waiting for 10s of non-fall to reset
    """
    IDLE = 'idle'
    MONITORING = 'monitoring'
    FALL_ALERT = 'fall_alert'
    COOLDOWN = 'cooldown'

    def __init__(self, threshold: float = 0.80, cooldown_sec: float = 10.0,
                 logger: EventLogger = None):
        self.threshold = threshold
        self.cooldown_sec = cooldown_sec
        self.logger = logger
        self.state = self.IDLE
        self._consecutive_falls = 0
        self._non_fall_start = None

    def update(self, prediction: int, confidence: float):
        """Process a new prediction. Returns the current state."""
        is_fall = (prediction == 0 and confidence >= self.threshold)

        if self.state == self.IDLE:
            if is_fall:
                self._consecutive_falls = 1
                self.state = self.MONITORING
            # else: stay idle

        elif self.state == self.MONITORING:
            if is_fall:
                self._consecutive_falls += 1
                if self._consecutive_falls >= 2:
                    self.state = self.FALL_ALERT
                    self._non_fall_start = None
                    print("\n" + "=" * 60)
                    print("  ** FALL DETECTED **")
                    print(f"  Confidence: {confidence:.1%}")
                    print("=" * 60 + "\n")
                    if self.logger:
                        self.logger.log_event(
                            "fall_detected", confidence,
                            f"Confirmed after {self._consecutive_falls} consecutive windows"
                        )
            else:
                # False alarm, reset
                self._consecutive_falls = 0
                self.state = self.IDLE

        elif self.state == self.FALL_ALERT:
            # Move to cooldown immediately
            self.state = self.COOLDOWN
            self._non_fall_start = time.time() if not is_fall else None

        elif self.state == self.COOLDOWN:
            if is_fall:
                self._non_fall_start = None  # Reset cooldown timer
            else:
                if self._non_fall_start is None:
                    self._non_fall_start = time.time()
                elapsed = time.time() - self._non_fall_start
                if elapsed >= self.cooldown_sec:
                    self.state = self.IDLE
                    self._consecutive_falls = 0
                    print("[alert] All clear — returned to idle")
                    if self.logger:
                        self.logger.log_event("all_clear", 0.0,
                                              f"No fall for {self.cooldown_sec}s")

        return self.state


# ── Simulated CSI Source ────────────────────────────────────────────────

def simulate_csi_stream(n_subcarriers: int = 52, rate_hz: float = 100.0):
    """
    Generate synthetic CSI frames for testing without hardware.
    Cycles through phases: idle → walk → fall → idle.
    """
    interval = 1.0 / rate_hz
    phase_duration = 5.0  # seconds per phase
    phases = ['idle', 'walk', 'fall', 'idle']

    print("[simulate] Starting synthetic CSI stream")
    print(f"[simulate] Phases: {' -> '.join(phases)} ({phase_duration}s each)")

    t = 0.0
    while True:
        phase_idx = int(t / phase_duration) % len(phases)
        phase = phases[phase_idx]

        # Base amplitude varies by activity
        if phase == 'idle':
            base = 10.0 + np.random.randn(n_subcarriers) * 0.5
        elif phase == 'walk':
            base = 10.0 + np.sin(2 * np.pi * 2.0 * t) * 3.0
            base = base + np.random.randn(n_subcarriers) * 1.0
        elif phase == 'fall':
            # Sharp spike then drop
            fall_progress = (t % phase_duration) / phase_duration
            if fall_progress < 0.3:
                base = 10.0 + fall_progress * 30.0
            else:
                base = 10.0 + (1.0 - fall_progress) * 5.0
            base = base + np.random.randn(n_subcarriers) * 2.0
        else:
            base = 10.0 + np.random.randn(n_subcarriers) * 0.5

        amplitude = np.abs(base)
        phase_angle = np.random.uniform(-np.pi, np.pi, n_subcarriers)

        frame = CSIFrame(
            timestamp=int(t * 1e6),
            rssi=-50,
            mac="AA:BB:CC:DD:EE:FF",
            channel=6,
            n_subcarriers=n_subcarriers,
            amplitude=amplitude.astype(np.float64),
            phase=phase_angle.astype(np.float64),
            complex_csi=(amplitude * np.exp(1j * phase_angle)).astype(np.complex64),
        )

        yield frame
        time.sleep(interval)
        t += interval


# ── Inference Engine ────────────────────────────────────────────────────

class InferenceEngine:
    """
    Real-time inference pipeline.

    Collects CSI frames into a rolling buffer, then runs:
    filter → PCA → spectrogram → model → alert
    """

    def __init__(self, model_path: str, pca_path: str,
                 window_samples: int = 200, step_samples: int = 100,
                 fs: float = 100.0, threshold: float = 0.80,
                 db_path: str = "../data/events.db"):
        self.window_samples = window_samples
        self.step_samples = step_samples
        self.fs = fs

        # Load PCA model
        print(f"[inference] Loading PCA model from {pca_path}")
        pca_bundle = joblib.load(pca_path)
        self.pca_model = pca_bundle['pca']
        self.n_pca_components = pca_bundle['n_components']
        self.n_pca_input_features = self.pca_model.n_features_in_
        print(f"[inference] PCA: {self.n_pca_components} components, "
              f"expects {self.n_pca_input_features} subcarriers")

        # Load PyTorch model
        print(f"[inference] Loading model from {model_path}")
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)

        from model.architecture import get_model
        self.model = get_model(
            n_freq=33,
            n_features=self.n_pca_components,
            n_classes=len(CLASSES),
        )
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.to(self.device)
        self.model.eval()
        print(f"[inference] Device: {self.device}")

        # Rolling buffer for raw amplitudes
        self.buffer = deque(maxlen=window_samples)
        self._frames_since_inference = 0

        # Event logger and alert FSM
        self.logger = EventLogger(db_path)
        self.alert = AlertFSM(threshold=threshold, logger=self.logger)

        # Stats
        self._total_frames = 0
        self._total_inferences = 0
        self._subcarrier_warning_shown = False

    def _align_subcarriers(self, amplitude: np.ndarray) -> np.ndarray:
        """Align subcarrier count to match what PCA expects."""
        n = len(amplitude)
        expected = self.n_pca_input_features
        if n == expected:
            return amplitude
        if not self._subcarrier_warning_shown:
            print(f"[inference] Subcarrier alignment: {n} -> {expected} "
                  f"({'truncating' if n > expected else 'padding'})")
            self._subcarrier_warning_shown = True
        if n > expected:
            return amplitude[:expected]
        else:
            padded = np.zeros(expected, dtype=amplitude.dtype)
            padded[:n] = amplitude
            return padded

    def add_frame(self, frame: CSIFrame):
        """Add a CSI frame to the rolling buffer."""
        aligned = self._align_subcarriers(frame.amplitude)
        self.buffer.append(aligned)
        self._frames_since_inference += 1
        self._total_frames += 1

        # Run inference every step_samples frames, once buffer is full
        if (len(self.buffer) >= self.window_samples and
                self._frames_since_inference >= self.step_samples):
            self._run_inference()
            self._frames_since_inference = 0

    def _run_inference(self):
        """Run the full preprocessing + model inference pipeline."""
        # Get current window from buffer
        amplitude = np.array(list(self.buffer))  # (window_samples, n_subcarriers)

        # Step 1: Filter
        filtered = filter_csi(amplitude, fs=self.fs)

        # Step 2: PCA
        reduced = apply_pca(self.pca_model, filtered,
                            n_components=self.n_pca_components)

        # Step 3: Spectrogram
        # process_csi_to_spectrograms uses sliding windows internally,
        # but we already have a single window, so we use the full buffer
        specs = process_csi_to_spectrograms(
            reduced, fs=self.fs, window_sec=self.window_samples / self.fs,
            nperseg=64, noverlap=48,
        )

        if len(specs) == 0:
            return

        # Take the first (and typically only) spectrogram window
        spec = specs[0]  # (n_freq, n_time, n_features)

        # Rearrange to model input: (batch, n_features, n_freq, n_time)
        spec_tensor = torch.tensor(
            spec.transpose(2, 0, 1),  # (n_features, n_freq, n_time)
            dtype=torch.float32,
        ).unsqueeze(0).to(self.device)

        # Step 4: Model inference
        with torch.no_grad():
            logits = self.model(spec_tensor)
            probs = torch.softmax(logits, dim=1)
            confidence, prediction = torch.max(probs, dim=1)
            prediction = prediction.item()
            confidence = confidence.item()

        self._total_inferences += 1

        # Display
        class_name = CLASSES[prediction]
        bar = "#" * int(confidence * 20) + "." * (20 - int(confidence * 20))
        state_indicator = {
            'idle': '[OK]', 'monitoring': '[??]',
            'fall_alert': '[!!]', 'cooldown': '[..]',
        }.get(self.alert.state, '[  ]')

        print(f"  [{self._total_inferences:4d}] {state_indicator} "
              f"{class_name:6s} {bar} {confidence:.1%}  "
              f"(frames: {self._total_frames})", end='\r')

        # Step 5: Log every prediction to SQLite
        self.logger.log_event(
            f"prediction_{class_name}", confidence,
            f"inference #{self._total_inferences}",
            silent=True,
        )

        # Step 6: Alert logic
        self.alert.update(prediction, confidence)

    def close(self):
        self.logger.close()


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='EtherGuard — Real-time fall detection inference'
    )
    parser.add_argument('--port', help='Serial port (e.g. COM6, /dev/ttyUSB0)')
    parser.add_argument('--model', required=True,
                        help='Path to model_best.pth')
    parser.add_argument('--pca', required=True,
                        help='Path to pca_model.pkl')
    parser.add_argument('--threshold', type=float, default=0.80,
                        help='Fall confidence threshold (default: 0.80)')
    parser.add_argument('--fs', type=float, default=100.0,
                        help='CSI sampling rate in Hz (default: 100)')
    parser.add_argument('--window-sec', type=float, default=2.0,
                        help='Sliding window duration in seconds (default: 2.0)')
    parser.add_argument('--db', default='../data/events.db',
                        help='SQLite database path for event logging')
    parser.add_argument('--simulate', action='store_true',
                        help='Use synthetic CSI data (no hardware needed)')
    parser.add_argument('--sim-duration', type=float, default=30.0,
                        help='Simulation duration in seconds (default: 30)')
    args = parser.parse_args()

    if not args.simulate and not args.port:
        parser.error("Either --port or --simulate is required")

    window_samples = int(args.window_sec * args.fs)
    step_samples = window_samples // 2  # 50% overlap

    print("=" * 60)
    print("  EtherGuard — Real-Time Fall Detection")
    print("=" * 60)
    print(f"  Window:    {args.window_sec}s ({window_samples} samples)")
    print(f"  Step:      {step_samples} samples ({args.window_sec / 2}s)")
    print(f"  Threshold: {args.threshold:.0%}")
    print(f"  Mode:      {'Simulation' if args.simulate else f'Live ({args.port})'}")
    print("=" * 60 + "\n")

    engine = InferenceEngine(
        model_path=args.model,
        pca_path=args.pca,
        window_samples=window_samples,
        step_samples=step_samples,
        fs=args.fs,
        threshold=args.threshold,
        db_path=args.db,
    )

    try:
        if args.simulate:
            # Simulation mode
            start_time = time.time()
            for frame in simulate_csi_stream(rate_hz=args.fs):
                engine.add_frame(frame)
                if time.time() - start_time >= args.sim_duration:
                    print(f"\n\n[simulate] Duration reached ({args.sim_duration}s)")
                    break
        else:
            # Live mode
            from serial_reader import CSISerialReader
            reader = CSISerialReader(port=args.port, baudrate=115200)
            print("[inference] Press Ctrl+C to stop\n")
            for frame in reader.stream():
                engine.add_frame(frame)

    except KeyboardInterrupt:
        print("\n\n[inference] Stopped by user")
    finally:
        # Summary
        print(f"\n{'=' * 60}")
        print(f"  Total frames:     {engine._total_frames}")
        print(f"  Total inferences: {engine._total_inferences}")
        events = engine.logger.get_recent_events(limit=50)
        fall_events = [e for e in events if e['event_type'] == 'fall_detected']
        print(f"  Fall events:      {len(fall_events)}")
        print(f"  Events database:  {engine.logger.db_path}")
        print(f"{'=' * 60}")
        engine.close()


if __name__ == '__main__':
    main()
