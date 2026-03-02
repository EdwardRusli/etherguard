#!/usr/bin/env python3
"""
ESP32 Diagnostic Tool

Diagnoses connection and CSI data issues with ESP32.

Usage:
    python diagnose_esp32.py --port /dev/ttyUSB0
"""

import serial
import time
import struct
import sys
from pathlib import Path

def diagnose(port: str, baudrate: int = 115200):
    print("\n" + "="*60)
    print("  ESP32 CSI DIAGNOSTIC TOOL")
    print("="*60)
    
    # Step 1: Check port exists
    print(f"\n[1] Checking port {port}...")
    port_path = Path(port)
    if not port_path.exists():
        print(f"    ❌ Port {port} does not exist!")
        print(f"    Available ports:")
        import glob
        for p in glob.glob("/dev/tty*"):
            if "USB" in p or "ACM" in p:
                print(f"      {p}")
        return False
    print(f"    ✓ Port exists")
    
    # Step 2: Try to open serial
    print(f"\n[2] Opening serial connection @ {baudrate} baud...")
    try:
        ser = serial.Serial(port, baudrate, timeout=2)
        time.sleep(1)
        print(f"    ✓ Serial opened")
    except serial.SerialException as e:
        print(f"    ❌ Failed to open serial: {e}")
        print(f"    Try: sudo chmod 666 {port}")
        return False
    
    # Step 3: Check for any data
    print(f"\n[3] Checking for any data (5 seconds)...")
    ser.reset_input_buffer()
    all_data = b''
    start = time.time()
    
    while time.time() - start < 5:
        data = ser.read(100)
        if data:
            all_data += data
            print(f"    Received {len(data)} bytes...", end='\r')
    
    print(f"    Total received: {len(all_data)} bytes")
    
    if len(all_data) == 0:
        print(f"    ❌ NO DATA received!")
        print(f"\n    Possible causes:")
        print(f"    1. ESP32 not powered on")
        print(f"    2. ESP32 firmware not uploaded")
        print(f"    3. Wrong baud rate (try 9600, 19200, 115200, 921600)")
        print(f"    4. USB cable only provides power (try different cable)")
        ser.close()
        return False
    
    print(f"    ✓ Data is being received")
    
    # Step 4: Analyze data content
    print(f"\n[4] Analyzing data content...")
    
    # Check for text (startup messages)
    try:
        text = all_data.decode('utf-8', errors='ignore')
        if "ESP32" in text or "CSI" in text or "WiFi" in text:
            print(f"    Found text output:")
            for line in text.split('\n')[:10]:
                if line.strip():
                    print(f"      {line[:70]}")
    except:
        pass
    
    # Check for binary header (0xAA 0x55)
    header_count = 0
    for i in range(len(all_data) - 1):
        if all_data[i] == 0xAA and all_data[i+1] == 0x55:
            header_count += 1
    
    print(f"\n    Binary headers (0xAA55) found: {header_count}")
    
    # Step 5: Look for CSI packets
    print(f"\n[5] Looking for CSI packets...")
    
    if header_count == 0:
        print(f"    ❌ No binary packets found!")
        print(f"\n    The ESP32 may be outputting text only.")
        print(f"    This could mean:")
        print(f"    1. Our firmware is not uploaded (using default firmware)")
        print(f"    2. WiFi is not connected (check credentials in firmware)")
        print(f"    3. CSI callback not triggered (need active WiFi traffic)")
        
        # Show raw data sample
        print(f"\n    Raw data sample (first 200 bytes hex):")
        print(f"    {all_data[:200].hex()}")
    else:
        print(f"    ✓ Found {header_count} packet headers!")
        
        # Try to parse a packet
        print(f"\n[6] Parsing first CSI packet...")
        
        for i in range(len(all_data) - 10):
            if all_data[i] == 0xAA and all_data[i+1] == 0x55:
                pkt_type = all_data[i+2]
                print(f"    Packet type: {pkt_type}")
                
                if pkt_type == 0x01:  # CSI packet
                    try:
                        # Try to parse
                        seq = struct.unpack('<I', all_data[i+3:i+7])[0]
                        timestamp = struct.unpack('<I', all_data[i+7:i+11])[0]
                        rssi = struct.unpack('<b', all_data[i+11:i+12])[0]
                        channel = all_data[i+12]
                        
                        print(f"    ✓ Successfully parsed CSI packet!")
                        print(f"      Sequence: {seq}")
                        print(f"      Timestamp: {timestamp}")
                        print(f"      RSSI: {rssi} dBm")
                        print(f"      Channel: {channel}")
                        print(f"\n    ✅ ESP32 IS WORKING CORRECTLY!")
                        break
                    except Exception as e:
                        print(f"    Parse error: {e}")
                elif pkt_type == 0x02:
                    print(f"    Status packet (ESP32 startup/heartbeat)")
                elif pkt_type == 0x03:
                    print(f"    Heartbeat packet")
    
    ser.close()
    return True


def monitor_mode(port: str, baudrate: int = 115200, duration: int = 10):
    """Monitor ESP32 output in real-time"""
    print(f"\n[MONITOR MODE] Showing ESP32 output for {duration} seconds...")
    print("="*60)
    
    try:
        ser = serial.Serial(port, baudrate, timeout=0.5)
    except Exception as e:
        print(f"Error: {e}")
        return
    
    start = time.time()
    buffer = b''
    
    while time.time() - start < duration:
        data = ser.read(100)
        if data:
            # Try to decode as text
            try:
                text = data.decode('utf-8', errors='ignore')
                print(text, end='', flush=True)
            except:
                # Show as hex
                print(f"[HEX: {data.hex()[:50]}...]")
    
    ser.close()
    print("\n" + "="*60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Diagnose ESP32 connection")
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--monitor", action="store_true", help="Monitor output")
    parser.add_argument("--duration", type=int, default=10, help="Monitor duration")
    args = parser.parse_args()
    
    if args.monitor:
        monitor_mode(args.port, args.baud, args.duration)
    else:
        diagnose(args.port, args.baud)


if __name__ == "__main__":
    main()
