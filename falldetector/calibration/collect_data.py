#!/usr/bin/env python3
"""
Room Calibration Data Collection

Guides user through collecting CSI data for each activity class.
Data is saved for training a room-specific model.

Usage:
    python collect_data.py --room living_room --port /dev/ttyUSB0
"""

import sys
import os
import time
import argparse
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import (
    SerialConfig, CSIConfig, ActivityConfig, 
    ROOMS_DIR, CALIBRATION_SEQUENCE
)
from utils.serial_reader import ESP32Reader, CSIPacket

# Try import for better display
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.panel import Panel
    from rich.prompt import Prompt
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class CalibrationCollector:
    """
    Guides user through calibration data collection.
    """
    
    def __init__(
        self,
        room_name: str,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200
    ):
        self.room_name = room_name
        self.room_dir = ROOMS_DIR / room_name
        self.room_dir.mkdir(parents=True, exist_ok=True)
        
        # Config
        self.serial_config = SerialConfig(port=port, baudrate=baudrate)
        self.csi_config = CSIConfig()
        self.activity_config = ActivityConfig()
        
        # Reader
        self.reader = ESP32Reader(self.serial_config, self.csi_config)
        
        # Data storage
        self.data: Dict[int, List[np.ndarray]] = {0: [], 1: [], 2: [], 3: []}
        
        # Console
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None
    
    def print(self, message: str, style: str = None):
        """Print message with optional styling"""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)
    
    def print_panel(self, title: str, content: str, style: str = "blue"):
        """Print a panel"""
        if self.console:
            self.console.print(Panel(content, title=title, border_style=style))
        else:
            print(f"\n{'='*50}")
            print(f"  {title}")
            print(f"{'='*50}")
            print(content)
            print(f"{'='*50}\n")
    
    def connect(self) -> bool:
        """Connect to ESP32"""
        self.print("\n[bold]Connecting to ESP32...[/bold]" if self.console else "\nConnecting to ESP32...")
        
        if not self.reader.connect():
            self.print("[red]Failed to connect![/red]" if self.console else "Failed to connect!")
            return False
        
        self.reader.start_reading()
        time.sleep(1)
        
        stats = self.reader.get_statistics()
        if stats["total_packets"] == 0:
            self.print("[yellow]Warning: No data received yet. ESP32 may need WiFi connection.[/yellow]" 
                      if self.console else "Warning: No data received yet.")
        
        return True
    
    def disconnect(self):
        """Disconnect from ESP32"""
        self.reader.disconnect()
    
    def collect_activity(
        self,
        activity_name: str,
        description: str,
        num_samples: int,
        duration: int
    ) -> int:
        """
        Collect data for one activity.
        
        Returns number of samples collected.
        """
        activity_idx = self.activity_config.get_label(activity_name)
        if activity_idx < 0:
            self.print(f"[red]Unknown activity: {activity_name}[/red]" if self.console else f"Unknown activity: {activity_name}")
            return 0
        
        # Show instructions
        self.print_panel(
            f"COLLECTING: {activity_name.upper()}",
            f"""
{description}

Target: {num_samples} samples
Duration: ~{duration} seconds

Press ENTER when ready to start...
            """,
            style="green" if activity_idx != 0 else "red"  # Red for fall
        )
        
        # Wait for user
        if self.console:
            Prompt.ask("[bold]Press ENTER to start[/bold]")
        else:
            input("Press ENTER to start...")
        
        # Collect data
        packets: List[np.ndarray] = []
        target_packets = num_samples * self.csi_config.window_size
        
        self.print(f"\n[bold]Collecting data...[/bold] Move now!" 
                  if self.console else "\nCollecting data... Move now!")
        
        start_time = time.time()
        last_print = 0
        
        while len(packets) < target_packets:
            elapsed = time.time() - start_time
            
            # Timeout check
            if elapsed > duration + 5:
                self.print(f"\n[yellow]Time limit reached[/yellow]" if self.console else "\nTime limit reached")
                break
            
            # Get packet
            packet = self.reader.get_packet(timeout=0.5)
            if packet and packet.valid:
                packets.append(packet.amplitude.copy())
            
            # Progress update
            if time.time() - last_print > 0.5:
                progress = len(packets) / target_packets * 100
                if self.console:
                    self.console.print(f"  Progress: {progress:.0f}% ({len(packets)}/{target_packets} packets)", end="\r")
                else:
                    print(f"  Progress: {progress:.0f}% ({len(packets)}/{target_packets} packets)", end="\r")
                last_print = time.time()
        
        print()  # New line after progress
        
        # Convert to windows
        window_size = self.csi_config.window_size
        hop_size = self.csi_config.hop_size
        
        windows_created = 0
        for i in range(0, len(packets) - window_size, hop_size):
            window = np.array(packets[i:i + window_size])
            self.data[activity_idx].append(window)
            windows_created += 1
        
        self.print(f"\n[green]✓ Collected {windows_created} {activity_name} samples[/green]"
                  if self.console else f"\n✓ Collected {windows_created} {activity_name} samples")
        
        # Short break between activities
        self.print("\n[i]Rest for 3 seconds...[/i]" if self.console else "\nRest for 3 seconds...")
        time.sleep(3)
        
        return windows_created
    
    def run_calibration(self, custom_sequence: list = None):
        """Run full calibration sequence"""
        sequence = custom_sequence or CALIBRATION_SEQUENCE
        
        self.print_panel(
            "ROOM CALIBRATION",
            f"""
Room: {self.room_name}

IMPORTANT: Run traffic generator in another terminal first!
  python wifi_fall_detector.py traffic --port {self.serial_config.port}

You will collect data for 4 activities:
  1. FALL - Fall onto a soft surface (bed/mat)
  2. WALK - Walk around the room
  3. SIT  - Sit down on a chair
  4. STAND - Stand up from sitting

For best results:
  - Keep ESP32 in fixed position
  - Perform actions naturally
  - Stay within 2-5 meters of ESP32
  - Ensure traffic generator is running!
            """,
            style="blue"
        )
        
        if self.console:
            Prompt.ask("\n[bold]Press ENTER to begin calibration[/bold]")
        else:
            input("\nPress ENTER to begin calibration...")
        
        # Collect each activity
        total_samples = 0
        for activity, description, num_samples, duration in sequence:
            samples = self.collect_activity(activity, description, num_samples, duration)
            total_samples += samples
        
        # Summary
        self.print_panel(
            "CALIBRATION COMPLETE",
            f"""
Total samples collected:
  Fall:  {len(self.data[0])}
  Walk:  {len(self.data[1])}
  Sit:   {len(self.data[2])}
  Stand: {len(self.data[3])}
  
Total: {total_samples} samples

Save this data? (Y/n)
            """,
            style="green"
        )
        
        if self.console:
            save = Prompt.ask("Save data?", default="Y")
        else:
            save = input("Save data? (Y/n): ").strip().upper()
        
        if save != "N":
            self.save_data()
        else:
            self.print("[yellow]Data not saved[/yellow]" if self.console else "Data not saved")
    
    def save_data(self):
        """Save collected data to files"""
        self.print("\n[bold]Saving data...[/bold]" if self.console else "\nSaving data...")
        
        # Save each class
        for class_idx, windows in self.data.items():
            if windows:
                data_array = np.array(windows)
                filepath = self.room_dir / f"class_{class_idx}.npy"
                np.save(filepath, data_array)
                self.print(f"  Saved {len(windows)} samples to {filepath}")
        
        # Save metadata
        metadata = {
            "room_name": self.room_name,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "window_size": self.csi_config.window_size,
                "subcarriers": self.csi_config.subcarriers,
            },
            "samples": {
                "fall": len(self.data[0]),
                "walk": len(self.data[1]),
                "sit": len(self.data[2]),
                "stand": len(self.data[3])
            }
        }
        
        with open(self.room_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        self.print(f"\n[green]✓ Data saved to {self.room_dir}[/green]"
                  if self.console else f"\n✓ Data saved to {self.room_dir}")
    
    def load_data(self) -> bool:
        """Load existing data for this room"""
        for class_idx in range(4):
            filepath = self.room_dir / f"class_{class_idx}.npy"
            if filepath.exists():
                data = np.load(filepath)
                self.data[class_idx] = list(data)
        
        return any(len(w) > 0 for w in self.data.values())


def main():
    parser = argparse.ArgumentParser(description="Collect calibration data for a room")
    parser.add_argument("--room", type=str, required=True, help="Room name/identifier")
    parser.add_argument("--port", type=str, default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--append", action="store_true", help="Append to existing data")
    args = parser.parse_args()
    
    collector = CalibrationCollector(
        room_name=args.room,
        port=args.port,
        baudrate=args.baud
    )
    
    if not collector.connect():
        return 1
    
    try:
        if args.append:
            collector.load_data()
        
        collector.run_calibration()
    finally:
        collector.disconnect()
    
    return 0


if __name__ == "__main__":
    exit(main())
