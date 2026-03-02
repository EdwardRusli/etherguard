#!/usr/bin/env python3
"""
WiFi CSI Traffic Generator

Sends UDP packets TO the ESP32 to trigger consistent CSI capture.
CSI is captured on received packets, so external traffic is needed.

Run this on the Jetson Nano (or any computer on the same network) 
while the ESP32 is connected and listening.

Usage:
    python traffic_generator.py --esp 192.168.1.100 --rate 20

The ESP32 IP is printed in the serial monitor on startup.
"""

import sys
import time
import socket
import argparse
import threading
import signal
from pathlib import Path


class TrafficGenerator:
    """
    Sends UDP packets to ESP32 to trigger CSI capture.
    """
    
    def __init__(self, esp_ip: str, esp_port: int = 12345, rate: float = 20.0):
        self.esp_ip = esp_ip
        self.esp_port = esp_port
        self.rate = rate  # packets per second
        self.interval = 1.0 / rate
        
        self.running = False
        self.sent_count = 0
        self.recv_count = 0
        self.error_count = 0
        
        # Create UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(0.1)  # Non-blocking for receives
        
        # Local port for receiving ACKs
        self.local_port = 12346
        self.sock.bind(('0.0.0.0', self.local_port))
        
        self._stop_event = threading.Event()
        
    def start(self):
        """Start the traffic generator"""
        print(f"\n{'='*60}")
        print("  WiFi CSI Traffic Generator")
        print(f"{'='*60}")
        print(f"Target: {self.esp_ip}:{self.esp_port}")
        print(f"Rate: {self.rate} Hz ({self.interval*1000:.1f}ms interval)")
        print(f"Local port: {self.local_port}")
        print()
        print("Press Ctrl+C to stop")
        print("-" * 40)
        
        self.running = True
        
        # Start receiver thread
        self._receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self._receiver_thread.start()
        
        # Main send loop
        last_print = time.time()
        last_send = time.time()
        
        try:
            while self.running:
                now = time.time()
                
                # Send packet at target rate
                if now - last_send >= self.interval:
                    self._send_packet()
                    last_send = now
                
                # Print stats every 5 seconds
                if now - last_print >= 5.0:
                    elapsed = now - self.start_time if hasattr(self, 'start_time') else 1
                    actual_rate = self.sent_count / elapsed if elapsed > 0 else 0
                    print(f"  [{elapsed:.0f}s] Sent: {self.sent_count} | "
                          f"Recv: {self.recv_count} | "
                          f"Errors: {self.error_count} | "
                          f"Rate: {actual_rate:.1f} Hz")
                    last_print = now
                
                # Small sleep to prevent CPU spinning
                time.sleep(0.001)
                
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def _send_packet(self):
        """Send a UDP packet to ESP32"""
        if not hasattr(self, 'start_time'):
            self.start_time = time.time()
            
        try:
            # Small payload with timestamp for debugging
            payload = f"CSI{self.sent_count:08d}".encode()
            self.sock.sendto(payload, (self.esp_ip, self.esp_port))
            self.sent_count += 1
        except Exception as e:
            self.error_count += 1
            if self.error_count < 10:  # Only print first few errors
                print(f"Send error: {e}")
    
    def _receiver_loop(self):
        """Background thread to receive ACKs"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                if data:
                    self.recv_count += 1
            except socket.timeout:
                pass
            except Exception:
                pass
    
    def stop(self):
        """Stop the traffic generator"""
        self.running = False
        
        # Print final stats
        if hasattr(self, 'start_time'):
            elapsed = time.time() - self.start_time
            print()
            print("-" * 40)
            print("Final Statistics:")
            print(f"  Duration:     {elapsed:.1f}s")
            print(f"  Sent:         {self.sent_count}")
            print(f"  Received:     {self.recv_count}")
            print(f"  Errors:       {self.error_count}")
            print(f"  Avg Rate:     {self.sent_count/elapsed:.1f} Hz")
            print()
        
        self.sock.close()
        print("Traffic generator stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate UDP traffic for ESP32 CSI capture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python traffic_generator.py --esp 192.168.1.100
  python traffic_generator.py --esp 192.168.1.100 --rate 30
  python traffic_generator.py --esp 192.168.1.100 --rate 50 --duration 60
        """
    )
    parser.add_argument("--esp", type=str, required=True, 
                       help="ESP32 IP address")
    parser.add_argument("--port", type=int, default=12345,
                       help="ESP32 UDP port (default: 12345)")
    parser.add_argument("--rate", type=float, default=20.0,
                       help="Packets per second (default: 20)")
    parser.add_argument("--duration", type=int, default=0,
                       help="Duration in seconds (0=run forever, default: 0)")
    args = parser.parse_args()
    
    gen = TrafficGenerator(
        esp_ip=args.esp,
        esp_port=args.port,
        rate=args.rate
    )
    
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        gen.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run with optional duration
    if args.duration > 0:
        import threading
        timer = threading.Timer(args.duration, gen.stop)
        timer.start()
    
    gen.start()


if __name__ == "__main__":
    main()
