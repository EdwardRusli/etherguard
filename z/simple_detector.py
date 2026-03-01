#!/usr/bin/env python3
"""
Simple Real-Time Fall Detection with Trained WiFall Model

Usage:
    python simple_detector.py --port /dev/ttyUSB0 --model ./output/train_XXX/weights/best_model.pt
"""

import serial
import torch
import torch.nn as nn
import numpy as np
import argparse
import json
import time
import struct
from pathlib import Path
from datetime import datetime


class LightweightFallModel(nn.Module):
    """Lightweight model - must match training architecture"""
    
    def __init__(self, input_dim: int, num_classes: int = 4):
        super(LightweightFallModel, self).__init__()
        
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=5, padding=2),
            nn.BatchNorm1d(16),
            nn.ReLU6(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm1d(32),
            nn.ReLU6(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU6(),
            nn.AdaptiveAvgPool1d(4)
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(64 * 4, 64),
            nn.ReLU6(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size = x.size(0)
        x = x.view(batch_size, 1, -1)
        x = self.features(x)
        x = x.view(batch_size, -1)
        x = self.classifier(x)
        return x


class SimpleCSICollector:
    """Collects CSI data from ESP32 for real-time detection"""
    
    def __init__(self, port: str, baudrate: int = 19200, window_size: int = 100):
        self.port = port
        self.baudrate = baudrate
        self.window_size = window_size
        self.serial = None
        self.buffer = []
        
        # CSI packet structure
        self.HEADER = bytes([0xAA, 0x55])
        self.PACKET_TYPE_CSI = 0x01
        
    def connect(self):
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Connected to {self.port} at {self.baudrate} baud")
            time.sleep(1)  # Wait for connection to stabilize
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        if self.serial:
            self.serial.close()
    
    def read_packet(self, debug=False):
        """Read a single CSI packet from ESP32"""
        if not self.serial:
            return None
        
        try:
            # Look for header
            while True:
                byte = self.serial.read(1)
                if not byte:
                    return None
                if byte == bytes([0xAA]):
                    byte2 = self.serial.read(1)
                    if byte2 == bytes([0x55]):
                        break
            
            # Read packet type
            pkt_type = self.serial.read(1)
            if not pkt_type or pkt_type[0] != self.PACKET_TYPE_CSI:
                if debug and pkt_type:
                    print(f"Skipping packet type: {pkt_type[0]}")
                return None
            
            # Read timestamp (4 bytes)
            ts_bytes = self.serial.read(4)
            timestamp = struct.unpack('<I', ts_bytes)[0]
            
            # Read RSSI (1 byte)
            rssi_byte = self.serial.read(1)
            rssi = struct.unpack('<b', rssi_byte)[0]
            
            # Read channel (1 byte)
            channel = self.serial.read(1)[0]
            
            # Read amplitude data (104 subcarriers * 2 bytes each)
            amp_bytes = self.serial.read(104 * 2)
            amplitudes = struct.unpack('<104h', amp_bytes)
            
            # Read phase data (104 subcarriers * 2 bytes each)
            phase_bytes = self.serial.read(104 * 2)
            phases = struct.unpack('<104h', phase_bytes)
            
            # Read checksum
            checksum = self.serial.read(1)[0]
            
            if debug:
                print(f"Packet: rssi={rssi}, ch={channel}, amp[0]={amplitudes[0]}")
            
            return {
                'timestamp': timestamp,
                'rssi': rssi,
                'channel': channel,
                'amplitude': np.array(amplitudes, dtype=np.float32),
                'phase': np.array(phases, dtype=np.float32)
            }
            
        except Exception as e:
            if debug:
                print(f"Read error: {e}")
            return None
    
    def get_window(self, debug=False):
        """Get a window of CSI data (window_size samples)"""
        # Collect enough packets
        while len(self.buffer) < self.window_size:
            packet = self.read_packet(debug=debug)
            if packet:
                self.buffer.append(packet['amplitude'])
                if debug and len(self.buffer) % 10 == 0:
                    print(f"Buffer: {len(self.buffer)}/{self.window_size}")
        
        # Return window and slide
        if len(self.buffer) >= self.window_size:
            window = np.array(self.buffer[:self.window_size])
            # Slide window by half
            self.buffer = self.buffer[self.window_size // 2:]
            return window
        
        return None


class FallDetector:
    """Main fall detection class"""
    
    ACTIVITY_LABELS = {
        0: "FALL",
        1: "WALK", 
        2: "SIT",
        3: "STAND"
    }
    
    def __init__(self, model_path: str, config_path: str = None, device: str = 'cpu'):
        self.device = device
        self.model_path = model_path
        self.config = self._load_config(config_path)
        
        # Load model
        self.model = self._load_model()
        self.model.eval()
        
        # Normalization stats (will be computed from data)
        self.mean = None
        self.std = None
        
        print(f"Model loaded: {model_path}")
        print(f"Device: {device}")
        print(f"Input shape: ({self.config.get('window_size', 100)}, 104)")
    
    def _load_config(self, config_path: str):
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        return {'window_size': 100, 'num_classes': 4}
    
    def _load_model(self):
        input_dim = self.config.get('window_size', 100) * 104  # 104 subcarriers
        num_classes = self.config.get('num_classes', 4)
        
        model = LightweightFallModel(input_dim, num_classes)
        
        # Load weights
        state_dict = torch.load(self.model_path, map_location=self.device, weights_only=True)
        model.load_state_dict(state_dict)
        model.to(self.device)
        
        return model
    
    def preprocess(self, csi_window: np.ndarray) -> torch.Tensor:
        """Preprocess CSI window for model input"""
        # Normalize
        if self.mean is None:
            self.mean = np.mean(csi_window)
            self.std = np.std(csi_window) + 1e-8
        
        normalized = (csi_window - self.mean) / self.std
        
        # Flatten and convert to tensor
        flat = normalized.flatten().astype(np.float32)
        tensor = torch.from_numpy(flat).unsqueeze(0).float()  # Add batch dim
        
        return tensor.to(self.device)
    
    def predict(self, csi_window: np.ndarray):
        """Run inference on CSI window"""
        tensor = self.preprocess(csi_window)
        
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1)
            pred_class = torch.argmax(probs, dim=1).item()
            confidence = probs[0, pred_class].item()
        
        return pred_class, confidence, probs[0].cpu().numpy()


def main():
    parser = argparse.ArgumentParser(description='Real-time Fall Detection')
    parser.add_argument('--port', type=str, default='/dev/ttyUSB0', help='Serial port')
    parser.add_argument('--baud', type=int, default=19200, help='Baud rate (default: 19200)')
    parser.add_argument('--model', type=str, required=True, help='Path to trained model')
    parser.add_argument('--config', type=str, default=None, help='Path to model config')
    parser.add_argument('--device', type=str, default='auto', help='Device (cpu/cuda/auto)')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()
    
    # Set device
    if args.device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = args.device
    
    print("\n" + "="*50)
    print("  WiFi CSI Fall Detection System")
    print("="*50 + "\n")
    
    # Initialize detector
    detector = FallDetector(args.model, args.config, device)
    
    # Initialize CSI collector
    collector = SimpleCSICollector(args.port, baudrate=args.baud)
    
    if not collector.connect():
        print("Failed to connect to ESP32")
        return 1
    
    print("\nDetection started! Move around to generate CSI data.\n")
    print("-" * 60)
    
    # Detection loop
    inference_count = 0
    fall_count = 0
    debug = args.debug
    
    # Print debug info for first window collection
    if debug:
        print("Debug mode: Collecting first window of 100 packets...")
    
    try:
        while True:
            window = collector.get_window(debug=debug)
            
            if window is not None:
                # Turn off debug after first window
                debug = False
                
                start_time = time.time()
                
                pred_class, confidence, probs = detector.predict(window)
                
                inference_time = (time.time() - start_time) * 1000
                inference_count += 1
                
                activity = detector.ACTIVITY_LABELS.get(pred_class, "UNKNOWN")
                
                if pred_class == 0:  # FALL
                    fall_count += 1
                    alert = "🚨 FALL DETECTED!"
                else:
                    alert = f"✓ {activity}"
                
                # Print result
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[{timestamp}] {alert:20s} | Conf: {confidence:.1%} | "
                      f"Time: {inference_time:.1f}ms | "
                      f"Total: {inference_count}, Falls: {fall_count}")
                
                # Print probability distribution occasionally
                if inference_count % 10 == 0:
                    prob_str = " | ".join([f"{detector.ACTIVITY_LABELS[i]}:{p:.2f}" 
                                          for i, p in enumerate(probs)])
                    print(f"    Probabilities: {prob_str}")
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    
    finally:
        collector.disconnect()
        print(f"\nSummary: {inference_count} inferences, {fall_count} falls detected")
    
    return 0


if __name__ == "__main__":
    exit(main())
