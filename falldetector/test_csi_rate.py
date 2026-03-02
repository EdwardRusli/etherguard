#!/usr/bin/env python3
"""
CSI Rate Test with Traffic Generator

Combined script that:
1. Sends UDP packets to ESP32 (traffic generation)
2. Reads CSI packets from serial port
3. Reports packet rate statistics

Usage:
    python test_csi_rate.py --port /dev/ttyUSB0 --esp 192.168.1.100 --duration 30
"""

import sys
import time
import socket
import argparse
import threading
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import SerialConfig, CSIConfig
from utils.serial_reader import ESP32Reader


class CSIRateTest:
    """
    Combined CSI rate test with traffic generation.
    """
    
    def __init__(self, serial_port: str, esp_ip: str, esp_port: int = 12345, rate: float = 20.0):
        self.serial_port = serial_port
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.rate = rate
        self.interval = 1.0 / rate
        
        # Serial reader
        self.reader = None
        
        # UDP socket
        self.sock = None
        
        # Stats
        self.timestamps = []
        self.udp_sent = 0
        self.running = False
        
    def run(self, duration: int = 30):
        """Run the test"""
        print(f"\n{'='*60}")
        print("  CSI Rate Test with Traffic Generator")
        print(f"{'='*60}")
        print(f"Serial: {self.serial_port}")
        print(f"ESP32:  {self.esp_ip}:{self.esp_port}")
        print(f"Rate:   {self.rate} Hz")
        print(f"Duration: {duration}s")
        print()
        
        # Connect to ESP32 serial
        config = SerialConfig(port=self.serial_port)
        csi_config = CSIConfig()
        self.reader = ESP32Reader(config, csi_config)
        
        if not self.reader.connect():
            print("ERROR: Failed to connect to ESP32 serial!")
            return 1
        
        print("Serial connected. Starting reader...")
        self.reader.start_reading()
        
        # Setup UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.01)
        
        self.running = True
        start_time = time.time()
        last_print = start_time
        
        print("\nRunning test... (Ctrl+C to stop)")
        print("-" * 50)
        
        try:
            while time.time() - start_time < duration and self.running:
                now = time.time()
                
                # Send UDP packet
                if now - start_time >= self.interval * self.udp_sent:
                    self._send_udp()
                
                # Read CSI packet
                packet = self.reader.get_packet(timeout=0.01)
                if packet and packet.valid:
                    self.timestamps.append(now)
                
                # Print progress
                if now - last_print >= 5:
                    elapsed = now - start_time
                    csi_rate = len(self.timestamps) / elapsed if elapsed > 0 else 0
                    print(f"  [{elapsed:.0f}s] CSI: {len(self.timestamps)} | "
                          f"UDP: {self.udp_sent} | Rate: {csi_rate:.1f} Hz")
                    last_print = now
                
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            print("\n\nTest interrupted")
        
        self.running = False
        
        # Cleanup
        if self.reader:
            self.reader.disconnect()
        if self.sock:
            self.sock.close()
        
        # Calculate and print results
        self._print_results()
        
        return 0
    
    def _send_udp(self):
        """Send UDP packet to ESP32"""
        try:
            payload = f"CSI{self.udp_sent:08d}".encode()
            self.sock.sendto(payload, (self.esp_ip, self.esp_port))
            self.udp_sent += 1
        except Exception as e:
            pass
    
    def _print_results(self):
        """Print test results"""
        if len(self.timestamps) < 2:
            print("\nNot enough CSI packets collected!")
            return
        
        # Calculate intervals
        intervals = [self.timestamps[i+1] - self.timestamps[i] 
                    for i in range(len(self.timestamps)-1)]
        
        total_time = self.timestamps[-1] - self.timestamps[0]
        avg_rate = len(intervals) / total_time if total_time > 0 else 0
        
        mean_interval = statistics.mean(intervals) * 1000
        stdev_interval = statistics.stdev(intervals) * 1000 if len(intervals) > 1 else 0
        cv = (stdev_interval / mean_interval * 100) if mean_interval > 0 else 0
        
        print(f"\n{'='*60}")
        print("  RESULTS")
        print(f"{'='*60}")
        print(f"\nCSI Packets:      {len(self.timestamps)}")
        print(f"UDP Sent:         {self.udp_sent}")
        print(f"Total Time:       {total_time:.2f}s")
        print(f"Average CSI Rate: {avg_rate:.1f} Hz")
        print()
        print("Inter-packet Interval:")
        print(f"  Mean:           {mean_interval:.2f} ms")
        print(f"  Std Dev:        {stdev_interval:.2f} ms")
        print(f"  CV:             {cv:.1f}%")
        print()
        
        # Assessment
        if cv < 20:
            print("✓ EXCELLENT: Very consistent CSI rate")
        elif cv < 40:
            print("✓ GOOD: Acceptable consistency")
        elif cv < 60:
            print("⚠ FAIR: Some variance")
        else:
            print("✗ POOR: High variance - check network")
        print()


def main():
    parser = argparse.ArgumentParser(description="Test CSI rate with traffic generation")
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0",
                       help="Serial port (default: /dev/ttyUSB0)")
    parser.add_argument("--esp", type=str, required=True,
                       help="ESP32 IP address")
    parser.add_argument("--rate", type=float, default=20.0,
                       help="UDP packet rate (default: 20 Hz)")
    parser.add_argument("--duration", type=int, default=30,
                       help="Test duration in seconds (default: 30)")
    args = parser.parse_args()
    
    test = CSIRateTest(
        serial_port=args.port,
        esp_ip=args.esp,
        rate=args.rate
    )
    
    return test.run(duration=args.duration)


if __name__ == "__main__":
    exit(main())
