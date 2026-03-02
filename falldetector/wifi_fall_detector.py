#!/usr/bin/env python3
"""
WiFi Fall Detector - Main Entry Point

Quick access to calibration, training, and detection.

Usage:
    python wifi_fall_detector.py calibrate --room living_room --port /dev/ttyUSB0
    python wifi_fall_detector.py train --room living_room
    python wifi_fall_detector.py detect --room living_room --port /dev/ttyUSB0
    python wifi_fall_detector.py list
"""

import sys
import subprocess
import argparse
from pathlib import Path

# Scripts directory
SCRIPTS_DIR = Path(__file__).parent


def run_script(script_path: str, args: list) -> int:
    """Run a Python script with arguments"""
    cmd = [sys.executable, script_path] + args
    return subprocess.run(cmd).returncode


def main():
    parser = argparse.ArgumentParser(
        description="WiFi CSI Fall Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start traffic generator (auto-detects ESP32 IP)
  python wifi_fall_detector.py traffic --port /dev/ttyUSB0
  
  # Calibrate a new room (run traffic generator first!)
  python wifi_fall_detector.py calibrate --room living_room --port /dev/ttyUSB0

  # Train model for a room
  python wifi_fall_detector.py train --room living_room --epochs 50

  # Run real-time detection
  python wifi_fall_detector.py detect --room living_room --port /dev/ttyUSB0

  # Test CSI packet rate
  python wifi_fall_detector.py test --port /dev/ttyUSB0 --duration 30

  # List all configured rooms
  python wifi_fall_detector.py list
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Calibrate command
    cal_parser = subparsers.add_parser("calibrate", help="Collect calibration data")
    cal_parser.add_argument("--room", type=str, required=True, help="Room name")
    cal_parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port")
    cal_parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    cal_parser.add_argument("--append", action="store_true", help="Add to existing data")
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train model")
    train_parser.add_argument("--room", type=str, required=True, help="Room name")
    train_parser.add_argument("--epochs", type=int, default=100, help="Epochs")
    train_parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    train_parser.add_argument("--device", type=str, default="auto", help="Device")
    train_parser.add_argument("--no-augment", action="store_true", help="No augmentation")
    
    # Detect command
    detect_parser = subparsers.add_parser("detect", help="Real-time detection")
    detect_parser.add_argument("--room", type=str, required=True, help="Room name")
    detect_parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port")
    detect_parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    detect_parser.add_argument("--model", type=str, default=None, help="Model path")
    detect_parser.add_argument("--threshold", type=float, default=0.5, help="Fall threshold")
    
    # List command
    subparsers.add_parser("list", help="List all rooms")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show room info")
    info_parser.add_argument("--room", type=str, required=True, help="Room name")
    
    # Traffic command (auto-detect ESP32 IP and generate traffic)
    traffic_parser = subparsers.add_parser("traffic", help="Generate UDP traffic for CSI capture")
    traffic_parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port")
    traffic_parser.add_argument("--rate", type=float, default=20.0, help="Packets per second")
    traffic_parser.add_argument("--duration", type=int, default=0, help="Duration in seconds (0=forever)")
    
    # Test command (test CSI packet rate)
    test_parser = subparsers.add_parser("test", help="Test CSI packet rate consistency")
    test_parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port")
    test_parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    
    args = parser.parse_args()
    
    if args.command == "calibrate":
        script = SCRIPTS_DIR / "calibration" / "collect_data.py"
        cmd_args = [
            "--room", args.room,
            "--port", args.port,
            "--baud", str(args.baud)
        ]
        if args.append:
            cmd_args.append("--append")
        return run_script(str(script), cmd_args)
    
    elif args.command == "train":
        script = SCRIPTS_DIR / "calibration" / "train_model.py"
        cmd_args = [
            "--room", args.room,
            "--epochs", str(args.epochs),
            "--batch-size", str(args.batch_size),
            "--device", args.device
        ]
        if args.no_augment:
            cmd_args.append("--no-augment")
        return run_script(str(script), cmd_args)
    
    elif args.command == "detect":
        script = SCRIPTS_DIR / "detection" / "detect.py"
        cmd_args = [
            "--room", args.room,
            "--port", args.port,
            "--baud", str(args.baud),
            "--threshold", str(args.threshold)
        ]
        if args.model:
            cmd_args.extend(["--model", args.model])
        return run_script(str(script), cmd_args)
    
    elif args.command == "list":
        script = SCRIPTS_DIR / "utils" / "room_manager.py"
        return run_script(str(script), ["list"])
    
    elif args.command == "info":
        script = SCRIPTS_DIR / "utils" / "room_manager.py"
        return run_script(str(script), ["info", "--room", args.room])
    
    elif args.command == "traffic":
        script = SCRIPTS_DIR / "auto_detect_esp.py"
        cmd_args = [
            "--port", args.port,
            "--rate", str(args.rate),
            "--duration", str(args.duration)
        ]
        return run_script(str(script), cmd_args)
    
    elif args.command == "test":
        script = SCRIPTS_DIR / "test_packet_rate.py"
        cmd_args = [
            "--port", args.port,
            "--duration", str(args.duration)
        ]
        return run_script(str(script), cmd_args)
    
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
