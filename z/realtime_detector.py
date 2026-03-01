#!/usr/bin/env python3
"""
Real-time Fall Detection Pipeline for Jetson Nano

Integrates CSI reception, preprocessing, and model inference
for real-time fall detection with web dashboard updates.
"""

import numpy as np
import torch
import time
import threading
import queue
import json
import logging
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import os

# Import local modules
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from csi_receiver import CSIReceiver, CSIBuffer, CSIDataPacket
from preprocessing import CSIPreprocessor, FeatureExtractor, SpectrogramGenerator
from fall_detection_model import ModelFactory, FallDetectionModel, LightweightFallDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ActivityClass(Enum):
    """Activity classes for fall detection"""
    FALL = 0
    WALK = 1
    SIT = 2
    STAND = 3
    
    @classmethod
    def to_labels(cls) -> Dict[int, str]:
        return {
            cls.FALL.value: "Fall",
            cls.WALK.value: "Walking",
            cls.SIT.value: "Sitting",
            cls.STAND.value: "Standing"
        }


@dataclass
class DetectionResult:
    """Fall detection result"""
    timestamp: str
    activity: str
    activity_id: int
    confidence: float
    probabilities: Dict[str, float]
    is_fall: bool
    fall_confidence: float
    processing_time_ms: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


class FallDetector:
    """
    Real-time fall detection system.
    
    Pipeline:
    1. Receive CSI data from ESP32
    2. Preprocess CSI (filter, normalize)
    3. Generate spectrograms
    4. Run model inference
    5. Post-process and alert
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        model_type: str = "lightweight",
        serial_port: Optional[str] = None,
        window_size: int = 100,
        sequence_length: int = 5,
        use_gpu: bool = True,
        alert_callback=None
    ):
        """
        Initialize fall detector.
        
        Args:
            model_path: Path to trained model weights
            model_type: "standard" or "lightweight"
            serial_port: ESP32 serial port
            window_size: CSI samples per window
            sequence_length: Number of spectrograms per inference
            use_gpu: Whether to use GPU acceleration
            alert_callback: Callback function for fall alerts
        """
        # Device configuration
        self.device = "cuda" if (use_gpu and torch.cuda.is_available()) else "cpu"
        logger.info(f"Using device: {self.device}")
        
        # Model configuration
        self.model_type = model_type
        self.model = self._load_model(model_path, model_type)
        self.model.eval()
        
        # CSI receiver
        self.receiver = CSIReceiver(port=serial_port)
        self.csi_buffer = CSIBuffer(window_size=window_size)
        
        # Preprocessing
        self.preprocessor = CSIPreprocessor(num_subcarriers=64)
        self.spectrogram_gen = SpectrogramGenerator()
        
        # Sequence buffer for temporal inference
        self.sequence_length = sequence_length
        self.spectrogram_buffer: List[np.ndarray] = []
        
        # Detection parameters
        self.window_size = window_size
        self.confidence_threshold = 0.7
        self.fall_sensitivity = 0.6  # Lower = more sensitive
        
        # Alert callback
        self.alert_callback = alert_callback
        
        # State
        self.is_running = False
        self.detection_thread: Optional[threading.Thread] = None
        self.result_queue = queue.Queue(maxsize=100)
        
        # Statistics
        self.stats = {
            "total_inferences": 0,
            "falls_detected": 0,
            "avg_processing_time_ms": 0,
            "start_time": None
        }
    
    def _load_model(self, model_path: Optional[str], model_type: str) -> torch.nn.Module:
        """Load the fall detection model"""
        # Default model path
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__),
                "models",
                "weights",
                f"fall_detector_{model_type}.pt"
            )
        
        # Create model
        model = ModelFactory.create_model(
            model_type=model_type,
            input_shape=(1, 33, 18),
            num_classes=4,
            device=self.device
        )
        
        # Load weights if available
        if os.path.exists(model_path):
            try:
                state_dict = torch.load(model_path, map_location=self.device)
                model.load_state_dict(state_dict)
                logger.info(f"Loaded model from {model_path}")
            except Exception as e:
                logger.warning(f"Could not load model weights: {e}")
                logger.info("Using model with random weights")
        else:
            logger.warning(f"Model file not found: {model_path}")
            logger.info("Using model with random weights")
        
        return model
    
    def _generate_spectrogram(self, amplitude: np.ndarray, phase: np.ndarray) -> np.ndarray:
        """Generate spectrogram from CSI data"""
        # Generate spectrogram from amplitude
        spec = self.spectrogram_gen.generate_spectrogram(amplitude, aggregate_subcarriers=True)
        
        # Normalize to [0, 1]
        spec = (spec - spec.min()) / (spec.max() - spec.min() + 1e-8)
        
        return spec.astype(np.float32)
    
    def _run_inference(self, spectrograms: np.ndarray) -> Tuple[int, np.ndarray]:
        """
        Run model inference on spectrogram sequence.
        
        Args:
            spectrograms: Array of shape (seq_len, freq_bins, time_bins)
        
        Returns:
            Tuple of (predicted_class, probabilities)
        """
        # Prepare input tensor
        # Shape: (1, seq_len, 1, freq_bins, time_bins)
        x = torch.from_numpy(spectrograms).float()
        x = x.unsqueeze(0).unsqueeze(2)  # Add batch and channel dims
        x = x.to(self.device)
        
        # Run inference
        start_time = time.time()
        
        with torch.no_grad():
            if isinstance(self.model, FallDetectionModel):
                logits, _ = self.model(x)
            else:
                logits = self.model(x)
            
            probabilities = torch.softmax(logits, dim=1)
            predicted_class = torch.argmax(probabilities, dim=1).item()
        
        processing_time = (time.time() - start_time) * 1000  # ms
        
        # Update statistics
        self.stats["total_inferences"] += 1
        prev_avg = self.stats["avg_processing_time_ms"]
        n = self.stats["total_inferences"]
        self.stats["avg_processing_time_ms"] = prev_avg + (processing_time - prev_avg) / n
        
        return predicted_class, probabilities.squeeze().cpu().numpy(), processing_time
    
    def _detection_loop(self):
        """Main detection loop running in background thread"""
        logger.info("Detection loop started")
        
        while self.is_running:
            try:
                # Get CSI data from buffer
                if not self.csi_buffer.is_ready():
                    # Add new CSI packets to buffer
                    packet = self.receiver.get_csi_data(timeout=0.1)
                    if packet:
                        self.csi_buffer.add_packet(packet)
                    continue
                
                # Get current window
                window = self.csi_buffer.get_window()
                if window is None:
                    continue
                
                amplitude, phase = window
                
                # Preprocess
                amp_processed, phase_processed = self.preprocessor.preprocess(amplitude, phase)
                
                # Generate spectrogram
                spectrogram = self._generate_spectrogram(amp_processed, phase_processed)
                
                # Add to sequence buffer
                self.spectrogram_buffer.append(spectrogram)
                if len(self.spectrogram_buffer) > self.sequence_length:
                    self.spectrogram_buffer.pop(0)
                
                # Check if we have enough spectrograms for inference
                if len(self.spectrogram_buffer) >= self.sequence_length:
                    # Stack spectrograms
                    spec_sequence = np.stack(self.spectrogram_buffer[-self.sequence_length:])
                    
                    # Run inference
                    predicted_class, probabilities, proc_time = self._run_inference(spec_sequence)
                    
                    # Create result
                    labels = ActivityClass.to_labels()
                    result = DetectionResult(
                        timestamp=datetime.now().isoformat(),
                        activity=labels[predicted_class],
                        activity_id=predicted_class,
                        confidence=float(probabilities[predicted_class]),
                        probabilities={labels[i]: float(p) for i, p in enumerate(probabilities)},
                        is_fall=(predicted_class == ActivityClass.FALL.value),
                        fall_confidence=float(probabilities[ActivityClass.FALL.value]),
                        processing_time_ms=proc_time
                    )
                    
                    # Update statistics
                    if result.is_fall:
                        self.stats["falls_detected"] += 1
                    
                    # Put result in queue
                    try:
                        self.result_queue.put_nowait(result)
                    except queue.Full:
                        pass
                    
                    # Alert callback
                    if result.is_fall and result.fall_confidence > self.fall_sensitivity:
                        if self.alert_callback:
                            self.alert_callback(result)
                
                # Small delay to prevent busy waiting
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                time.sleep(0.1)
    
    def start(self) -> bool:
        """Start the fall detection system"""
        if self.is_running:
            logger.warning("Detector already running")
            return True
        
        # Connect to ESP32
        if not self.receiver.connect():
            logger.error("Failed to connect to ESP32")
            return False
        
        # Start receiving CSI data
        if not self.receiver.start_receiving():
            logger.error("Failed to start CSI reception")
            return False
        
        # Start detection thread
        self.is_running = True
        self.stats["start_time"] = datetime.now()
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        logger.info("Fall detection system started")
        return True
    
    def stop(self):
        """Stop the fall detection system"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.detection_thread:
            self.detection_thread.join(timeout=3)
            self.detection_thread = None
        
        self.receiver.stop_receiving()
        self.receiver.disconnect()
        
        logger.info("Fall detection system stopped")
    
    def get_result(self, timeout: float = 0.1) -> Optional[DetectionResult]:
        """Get latest detection result"""
        try:
            return self.result_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_statistics(self) -> Dict:
        """Get detection statistics"""
        stats = self.stats.copy()
        stats["receiver_stats"] = self.receiver.get_statistics()
        
        if stats["start_time"]:
            stats["uptime_seconds"] = (datetime.now() - stats["start_time"]).total_seconds()
        
        return stats


class FallAlertHandler:
    """Handler for fall alert notifications"""
    
    def __init__(self, alert_webhook: Optional[str] = None):
        """
        Initialize alert handler.
        
        Args:
            alert_webhook: Webhook URL for notifications
        """
        self.alert_webhook = alert_webhook
        self.alert_history: List[DetectionResult] = []
        self.max_history = 100
    
    def handle_alert(self, result: DetectionResult):
        """Handle a fall detection alert"""
        # Add to history
        self.alert_history.append(result)
        if len(self.alert_history) > self.max_history:
            self.alert_history.pop(0)
        
        logger.warning(f"🚨 FALL DETECTED! Confidence: {result.fall_confidence:.2%}")
        
        # Send webhook notification if configured
        if self.alert_webhook:
            self._send_webhook(result)
    
    def _send_webhook(self, result: DetectionResult):
        """Send alert to webhook"""
        try:
            import requests
            payload = {
                "event": "fall_detected",
                "timestamp": result.timestamp,
                "confidence": result.fall_confidence,
                "details": result.to_dict()
            }
            requests.post(self.alert_webhook, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")


if __name__ == "__main__":
    # Test the fall detection system
    import signal
    
    print("=== WiFi CSI Fall Detection System ===")
    print("Press Ctrl+C to stop\n")
    
    # Create alert handler
    alert_handler = FallAlertHandler()
    
    # Create fall detector
    detector = FallDetector(
        model_type="lightweight",
        alert_callback=alert_handler.handle_alert
    )
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down...")
        detector.stop()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start detection
    if detector.start():
        print("Detection started. Waiting for CSI data...")
        
        try:
            while True:
                result = detector.get_result(timeout=1.0)
                if result:
                    status = "🚨 FALL!" if result.is_fall else f"✓ {result.activity}"
                    print(f"[{result.timestamp}] {status} "
                          f"(conf: {result.confidence:.2%}, "
                          f"time: {result.processing_time_ms:.1f}ms)")
                
                # Print stats every 10 seconds
                stats = detector.get_statistics()
                if stats["total_inferences"] > 0:
                    print(f"Stats: {stats['total_inferences']} inferences, "
                          f"{stats['falls_detected']} falls, "
                          f"avg {stats['avg_processing_time_ms']:.1f}ms/inference")
        
        except KeyboardInterrupt:
            pass
        finally:
            detector.stop()
    else:
        print("Failed to start detection system")
