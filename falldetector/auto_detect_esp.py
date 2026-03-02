#!/usr/bin/env python3
"""
ESP32 Auto-Detection and Traffic Generator

Automatically detects ESP32 IP address from serial output,
then starts traffic generation for CSI capture.

Usage:
    python auto_detect_esp.py --port /dev/ttyUSB0
    python auto_detect_esp.py --port COM3 --rate 30
"""

import sys
import time
import re
import socket
import argparse
import threading
import signal
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import SerialConfig, CSIConfig
from utils.serial_reader import ESP32Reader


class ESP32AutoDetector:
    """
    Detects ESP32 IP address from serial output and starts traffic generation.
    """
    
    IP_PATTERN = re.compile(r'IP:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
    READY_PATTERN = re.compile(r'Ready|CSI collection enabled', re.IGNORECASE)
    
    def __init__(self, serial_port: str, rate: float = 20.0):
        self.serial_port = serial_port
        self.rate = rate
        self.interval = 1.0 / rate
        
        self.esp_ip = None
        self.reader = None
        self.sock = None
        
        self.running = False
        self.detected = threading.Event()
        
        self.csi_count = 0
        self.udp_sent = 0
        self.timestamps = []
        
    def detect_and_run(self, duration: int = 0):
        """
        Detect ESP32 IP and run traffic generator.
        
        Args:
            duration: 0 = run forever, otherwise seconds
        """
        print(f"\n{'='*60}")
        print("  ESP32 Auto-Detection + Traffic Generator")
        print(f"{'='*60}")
        print(f"Serial: {self.serial_port}")
        print(f"Rate:   {self.rate} Hz")
        print()
        print("Waiting for ESP32 to connect to WiFi...")
        print("-" * 40)
        
        # Connect to serial
        config = SerialConfig(port=self.serial_port, timeout=1.0)
        csi_config = CSIConfig()
        self.reader = ESP32Reader(config, csi_config)
        
        if not self.reader.connect():
            print("ERROR: Failed to connect to serial port!")
            return 1
        
        # Start reading (this clears buffer and starts background thread)
        self.reader.start_reading()
        
        # Read raw serial data for IP detection
        import serial
        ser = serial.Serial(self.serial_port, 115200, timeout=1.0)
        time.sleep(0.5)
        ser.reset_input_buffer()
        
        # Wait for IP address in output
        timeout = 30  # seconds
        start = time.time()
        buffer = ""
        
        while time.time() - start < timeout:
            if ser.in_waiting > 0:
                try:
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data
                    print(data, end='', flush=True)
                    
                    # Check for IP address
                    match = self.IP_PATTERN.search(buffer)
                    if match:
                        self.esp_ip = match.group(1)
                        print(f"\n{'='*40}")
                        print(f"DETECTED ESP32 IP: {self.esp_ip}")
                        print(f"{'='*40}\n")
                        self.detected.set()
                        break
                        
                except Exception as e:
                    pass
            
            time.sleep(0.1)
        
        if not self.esp_ip:
            print("\nERROR: Could not detect ESP32 IP address!")
            print("Make sure ESP32 is connected to WiFi.")
            ser.close()
            return 1
        
        # Setup UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.01)
        
        # Send 'S' command to get status (triggers fresh output)
        ser.write(b'S')
        time.sleep(0.5)
        
        # Now start traffic generation and CSI monitoring
        print(f"\nStarting traffic generator to {self.esp_ip}:12345")
        print("Press Ctrl+C to stop")
        print("-" * 40)
        
        self.running = True
        start_time = time.time()
        last_print = start_time
        last_udp = start_time
        
        try:
            while self.running:
                now = time.time()
                
                # Send UDP at target rate
                if now - last_udp >= self.interval:
                    self._send_udp()
                    last_udp = now
                
                # Read CSI packets
                packet = self.reader.get_packet(timeout=0.01)
                if packet and packet.valid:
                    self.timestamps.append(now)
                    self.csi_count += 1
                
                # Print stats every 5 seconds
                if now - last_print >= 5:
                    elapsed = now - start_time
                    csi_rate = self.csi_count / elapsed if elapsed > 0 else 0
                    print(f"  [{elapsed:.0f}s] CSI: {self.csi_count} | "
                          f"UDP: {self.udp_sent} | Rate: {csi_rate:.1f} Hz")
                    last_print = now
                
                # Check duration
                if duration > 0 and now - start_time >= duration:
                    break
                
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            print("\n\nStopped by user")
        
        self.running = False
        ser.close()
        self.reader.disconnect()
        if self.sock:
            self.sock.close()
        
        self._print_results(start_time)
        return 0
    
    def _send_udp(self):
        """Send UDP packet to ESP32"""
        try:
            payload = f"CSI{self.udp_sent:08d}".encode()
            self.sock.sendto(payload, (self.esp_ip, 12345))
            self.udp_sent += 1
        except Exception:
            pass
    
    def _print_results(self, start_time):
        """Print final statistics"""
        import statistics
        
        elapsed = time.time() - start_time
        
        print(f"\n{'='*60}")
        print("  RESULTS")
        print(f"{'='*60}")
        print(f"\nESP32 IP:     {self.esp_ip}")
        print(f"Duration:     {elapsed:.1f}s")
        print(f"CSI Packets:  {self.csi_count}")
        print(f"UDP Sent:     {self.udp_sent}")
        
        if self.csi_count > 1 and len(self.timestamps) > 1:
            intervals = [self.timestamps[i+1] - self.timestamps[i] 
                        for i in range(len(self.timestamps)-1)]
            mean_int = statistics.mean(intervals) * 1000
            std_int = statistics.stdev(intervals) * 1000 if len(intervals) > 1 else 0
            cv = (std_int / mean_int * 100) if mean_int > 0 else 0
            
            print(f"\nCSI Rate:     {self.csi_count/elapsed:.1f} Hz")
            print(f"Mean Interval: {mean_int:.1f} ms")
            print(f"Std Dev:       {std_int:.1f} ms")
            print(f"CV:            {cv:.1f}%")
            
            if cv < 30:
                print("\n✓ GOOD: Consistent CSI packet rate")
            else:
                print("\n⚠ Check network stability")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-detect ESP32 IP and run traffic generator"
    )
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0",
                       help="Serial port (default: /dev/ttyUSB0, Windows: COM3)")
    parser.add_argument("--rate", type=float, default=20.0,
                       help="UDP packet rate Hz (default: 20)")
    parser.add_argument("--duration", type=int, default=0,
                       help="Duration in seconds (0=forever, default: 0)")
    args = parser.parse_args()
    
    detector = ESP32AutoDetector(
        serial_port=args.port,
        rate=args.rate
    )
    
    return detector.detect_and_run(duration=args.duration)


if __name__ == "__main__":
    exit(main())
