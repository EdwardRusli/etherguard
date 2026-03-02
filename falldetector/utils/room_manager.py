#!/usr/bin/env python3
"""
Room Manager - Manage multiple room configurations

List, create, and manage room-specific models and data.

Usage:
    python room_manager.py list
    python room_manager.py info --room living_room
    python room_manager.py delete --room old_room
"""

import sys
import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import ROOMS_DIR, MODELS_DIR


def list_rooms():
    """List all configured rooms"""
    print("\n" + "="*60)
    print("  CONFIGURED ROOMS")
    print("="*60)
    
    # Check data directory
    rooms_with_data = []
    if ROOMS_DIR.exists():
        for room_dir in ROOMS_DIR.iterdir():
            if room_dir.is_dir():
                metadata_file = room_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file) as f:
                        metadata = json.load(f)
                    rooms_with_data.append({
                        "name": room_dir.name,
                        "samples": metadata.get("samples", {}),
                        "created": metadata.get("timestamp", "unknown")
                    })
    
    # Check models directory
    rooms_with_models = []
    if MODELS_DIR.exists():
        for model_dir in MODELS_DIR.iterdir():
            if model_dir.is_dir():
                config_file = model_dir / "model_config.json"
                if config_file.exists():
                    with open(config_file) as f:
                        config = json.load(f)
                    rooms_with_models.append({
                        "name": model_dir.name,
                        "accuracy": config.get("best_val_acc", "unknown"),
                        "trained": config.get("timestamp", "unknown")
                    })
    
    # Display
    print("\nRooms with calibration data:")
    if rooms_with_data:
        for room in rooms_with_data:
            samples = room["samples"]
            total = sum(samples.values())
            print(f"\n  📁 {room['name']}")
            print(f"     Created: {room['created'][:10] if room['created'] != 'unknown' else 'unknown'}")
            print(f"     Total samples: {total}")
            print(f"     Fall: {samples.get('fall', 0)}, Walk: {samples.get('walk', 0)}, "
                  f"Sit: {samples.get('sit', 0)}, Stand: {samples.get('stand', 0)}")
    else:
        print("  No rooms with calibration data found.")
    
    print("\nRooms with trained models:")
    if rooms_with_models:
        for room in rooms_with_models:
            print(f"\n  🧠 {room['name']}")
            print(f"     Trained: {room['trained'][:10] if room['trained'] != 'unknown' else 'unknown'}")
            print(f"     Best accuracy: {room['accuracy']:.2%} if isinstance(room['accuracy'], float) else room['accuracy']}")
    else:
        print("  No trained models found.")
    
    print("\n" + "="*60 + "\n")


def show_room_info(room_name: str):
    """Show detailed info for a room"""
    room_dir = ROOMS_DIR / room_name
    model_dir = MODELS_DIR / room_name
    
    print(f"\n{'='*60}")
    print(f"  ROOM: {room_name}")
    print(f"{'='*60}")
    
    # Data info
    print("\n📁 Calibration Data:")
    if room_dir.exists():
        metadata_file = room_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
            print(f"   Created: {metadata.get('timestamp', 'unknown')}")
            print(f"   Window size: {metadata.get('config', {}).get('window_size', 'unknown')}")
            samples = metadata.get("samples", {})
            for activity, count in samples.items():
                print(f"   {activity}: {count} samples")
        else:
            print("   No metadata found.")
        
        # Check data files
        for class_idx in range(4):
            data_file = room_dir / f"class_{class_idx}.npy"
            if data_file.exists():
                import numpy as np
                data = np.load(data_file)
                print(f"   class_{class_idx}.npy: shape {data.shape}")
    else:
        print("   No calibration data found for this room.")
    
    # Model info
    print("\n🧠 Trained Model:")
    if model_dir.exists():
        config_file = model_dir / "model_config.json"
        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
            print(f"   Model type: {config.get('model_type', 'unknown')}")
            print(f"   Best accuracy: {config.get('best_val_acc', 'unknown')}")
            print(f"   Trained: {config.get('timestamp', 'unknown')}")
        
        # List model files
        for f in model_dir.iterdir():
            print(f"   {f.name}")
    else:
        print("   No trained model found for this room.")
    
    print(f"\n{'='*60}\n")


def delete_room(room_name: str, force: bool = False):
    """Delete room data and model"""
    room_dir = ROOMS_DIR / room_name
    model_dir = MODELS_DIR / room_name
    
    if not room_dir.exists() and not model_dir.exists():
        print(f"Room '{room_name}' not found.")
        return
    
    if not force:
        confirm = input(f"Delete all data for room '{room_name}'? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return
    
    if room_dir.exists():
        shutil.rmtree(room_dir)
        print(f"Deleted calibration data: {room_dir}")
    
    if model_dir.exists():
        shutil.rmtree(model_dir)
        print(f"Deleted model: {model_dir}")


def main():
    parser = argparse.ArgumentParser(description="Manage room configurations")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # List command
    subparsers.add_parser("list", help="List all rooms")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show room info")
    info_parser.add_argument("--room", type=str, required=True, help="Room name")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete room")
    delete_parser.add_argument("--room", type=str, required=True, help="Room name")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_rooms()
    elif args.command == "info":
        show_room_info(args.room)
    elif args.command == "delete":
        delete_room(args.room, args.force)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
