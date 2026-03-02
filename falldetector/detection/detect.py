#!/usr/bin/env python3
"""
Real-Time Fall Detection

Runs real-time fall detection using a trained room-specific model.

Usage:
    python detect.py --room living_room --port /dev/ttyUSB0
    python detect.py --room living_room --model ./models/living_room/best_model.pt
"""

import sys
import time
import argparse
import json
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

import torch
import torch.nn.functional as F
import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import (
    SerialConfig, CSIConfig, ActivityConfig,
    MODELS_DIR, ROOMS_DIR, ACTIVITY_DISPLAY
)
from utils.serial_reader import ESP32Reader, CSIWindowBuffer
from models.model import create_model

# Try rich for better display
try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class RealTimeDetector:
    """
    Real-time fall detection system.
    """
    
    def __init__(
        self,
        room_name: str,
        model_path: str = None,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        threshold: float = 0.5
    ):
        self.room_name = room_name
        self.threshold = threshold
        
        # Paths
        if model_path:
            self.model_path = Path(model_path)
        else:
            self.model_path = MODELS_DIR / room_name / "best_model.pt"
        
        self.config_path = self.model_path.parent / "model_config.json"
        
        # Load config
        self.config = self._load_config()
        
        # Device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load model
        self.model = self._load_model()
        
        # Activity config
        self.activity_config = ActivityConfig()
        
        # Serial reader
        serial_config = SerialConfig(port=port, baudrate=baudrate)
        csi_config = CSIConfig(
            window_size=self.config.get("window_size", 100),
            subcarriers=self.config.get("subcarriers", 104)
        )
        self.reader = ESP32Reader(serial_config, csi_config)
        self.buffer = CSIWindowBuffer(
            window_size=csi_config.window_size,
            hop_size=50
        )
        
        # Statistics
        self.stats = {
            "total_predictions": 0,
            "activity_counts": {0: 0, 1: 0, 2: 0, 3: 0},
            "falls_detected": 0,
            "start_time": None
        }
        
        # Alert callback
        self.alert_callback = None
        
        # Console
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
        
        # Running flag
        self.running = False
    
    def _load_config(self) -> Dict:
        """Load model configuration"""
        if self.config_path.exists():
            with open(self.config_path) as f:
                return json.load(f)
        return {"window_size": 100, "subcarriers": 104, "num_classes": 4}
    
    def _load_model(self) -> torch.nn.Module:
        """Load trained model"""
        window_size = self.config.get("window_size", 100)
        subcarriers = self.config.get("subcarriers", 104)
        num_classes = self.config.get("num_classes", 4)
        
        model = create_model(
            model_type="lightweight",
            window_size=window_size,
            subcarriers=subcarriers,
            num_classes=num_classes,
            device=self.device
        )
        
        if self.model_path.exists():
            state_dict = torch.load(
                self.model_path, 
                map_location=self.device,
                weights_only=True
            )
            model.load_state_dict(state_dict)
            print(f"Loaded model from {self.model_path}")
        else:
            print(f"Warning: Model not found at {self.model_path}")
            print("Using random weights - please train a model first!")
        
        model.eval()
        return model
    
    def connect(self) -> bool:
        """Connect to ESP32"""
        if not self.reader.connect():
            return False
        
        self.reader.start_reading()
        return True
    
    def disconnect(self):
        """Disconnect from ESP32"""
        self.reader.disconnect()
    
    def set_alert_callback(self, callback):
        """Set callback for fall alerts"""
        self.alert_callback = callback
    
    def preprocess(self, window: np.ndarray) -> torch.Tensor:
        """Preprocess window for model input"""
        # Normalize
        mean = window.mean()
        std = window.std() + 1e-8
        normalized = (window - mean) / std
        
        # Convert to tensor
        tensor = torch.from_numpy(normalized).float().unsqueeze(0)
        return tensor.to(self.device)
    
    def predict(self, window: np.ndarray) -> Dict:
        """Run inference on window"""
        tensor = self.preprocess(window)
        
        with torch.no_grad():
            logits = self.model(tensor)
            probs = F.softmax(logits, dim=1)
            conf, pred = probs.max(dim=1)
            
            pred_class = pred.item()
            confidence = conf.item()
            all_probs = probs.squeeze().cpu().numpy()
        
        return {
            "class": pred_class,
            "activity": self.activity_config.labels.get(pred_class, "unknown"),
            "confidence": confidence,
            "probabilities": {i: float(p) for i, p in enumerate(all_probs)},
            "is_fall": pred_class == 0,
            "timestamp": datetime.now().isoformat()
        }
    
    def run(self):
        """Run detection loop"""
        self.running = True
        self.stats["start_time"] = datetime.now()
        
        print("\n" + "="*60)
        print("  REAL-TIME FALL DETECTION")
        print("="*60)
        print(f"  Room: {self.room_name}")
        print(f"  Device: {self.device}")
        print(f"  Model: {self.model_path.name}")
        print("="*60)
        print("\nDetection started. Press Ctrl+C to stop.\n")
        
        try:
            while self.running:
                # Get packets
                packet = self.reader.get_packet(timeout=0.1)
                if packet and packet.valid:
                    self.buffer.add_packet(packet)
                
                # Check if window is ready
                if self.buffer.is_ready():
                    window = self.buffer.get_window()
                    
                    if window is not None:
                        # Run prediction
                        result = self.predict(window)
                        
                        # Update stats
                        self.stats["total_predictions"] += 1
                        self.stats["activity_counts"][result["class"]] += 1
                        
                        if result["is_fall"]:
                            self.stats["falls_detected"] += 1
                        
                        # Display result
                        self._display_result(result)
                        
                        # Alert callback
                        if result["is_fall"] and result["confidence"] > self.threshold:
                            if self.alert_callback:
                                self.alert_callback(result)
        
        except KeyboardInterrupt:
            pass
        
        finally:
            self._print_summary()
    
    def _display_result(self, result: Dict):
        """Display detection result"""
        activity = result["activity"]
        confidence = result["confidence"]
        is_fall = result["is_fall"]
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        if self.console:
            # Rich display
            color = "red" if is_fall else "green"
            icon = "🚨" if is_fall else "✓"
            
            self.console.print(
                f"[{timestamp}] [{color}]{icon} {activity.upper():10s}[/{color}] "
                f"Conf: {confidence:.1%} | "
                f"Total: {self.stats['total_predictions']}, "
                f"Falls: {self.stats['falls_detected']}"
            )
        else:
            # Plain display
            icon = "🚨" if is_fall else "✓"
            print(f"[{timestamp}] {icon} {activity.upper():10s} "
                  f"Conf: {confidence:.1%} | "
                  f"Total: {self.stats['total_predictions']}, "
                  f"Falls: {self.stats['falls_detected']}")
    
    def _print_summary(self):
        """Print detection summary"""
        print("\n" + "="*60)
        print("  DETECTION SUMMARY")
        print("="*60)
        
        if self.stats["start_time"]:
            duration = (datetime.now() - self.stats["start_time"]).total_seconds()
            print(f"  Duration: {duration:.1f} seconds")
        
        print(f"  Total predictions: {self.stats['total_predictions']}")
        print(f"  Falls detected: {self.stats['falls_detected']}")
        print(f"  Activity distribution:")
        for class_idx, count in self.stats["activity_counts"].items():
            activity = self.activity_config.labels.get(class_idx, "unknown")
            print(f"    {activity}: {count}")
        
        print("="*60 + "\n")
    
    def stop(self):
        """Stop detection"""
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="Real-time fall detection")
    parser.add_argument("--room", type=str, required=True, help="Room name")
    parser.add_argument("--model", type=str, default=None, help="Model path")
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--threshold", type=float, default=0.5, help="Fall detection threshold")
    args = parser.parse_args()
    
    # Create detector
    detector = RealTimeDetector(
        room_name=args.room,
        model_path=args.model,
        port=args.port,
        baudrate=args.baud,
        threshold=args.threshold
    )
    
    # Connect
    if not detector.connect():
        print("Failed to connect to ESP32")
        return 1
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        detector.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run detection
    try:
        detector.run()
    finally:
        detector.disconnect()
    
    return 0


if __name__ == "__main__":
    exit(main())
