#!/usr/bin/env python3
"""
Compare ESP32 CSI data with WiFall training data

This script helps verify that your ESP32 data format matches the training data.

Usage:
    python3 compare_csi_data.py --port /dev/ttyUSB0 --wifall ./data/wifall
"""

import serial
import numpy as np
import struct
import time
import argparse
from pathlib import Path


def load_wifall_sample(wifall_dir: str, num_samples: int = 5):
    """Load sample data from WiFall dataset"""
    wifall_path = Path(wifall_dir)
    
    train_csi = np.load(wifall_path / 'train_csi.npy')
    train_labels = np.load(wifall_path / 'train_labels.npy')
    
    print(f"WiFall Dataset Shape: {train_csi.shape}")
    print(f"  - {train_csi.shape[0]} samples")
    print(f"  - {train_csi.shape[1]} time steps per sample")
    print(f"  - {train_csi.shape[2]} subcarriers per time step")
    
    # Get samples from each class
    samples = {}
    for label in range(4):
        idx = np.where(train_labels == label)[0]
        if len(idx) > 0:
            samples[label] = train_csi[idx[:num_samples]]
    
    return train_csi, train_labels, samples


def collect_esp32_sample(port: str, baudrate: int = 19200, num_packets: int = 100, timeout: int = 60):
    """Collect CSI data from ESP32"""
    print(f"\nCollecting {num_packets} packets from ESP32 on {port}...")
    
    ser = serial.Serial(port, baudrate, timeout=1)
    time.sleep(1)
    
    packets = []
    start_time = time.time()
    
    while len(packets) < num_packets and (time.time() - start_time) < timeout:
        try:
            # Look for header
            byte = ser.read(1)
            if not byte:
                continue
            if byte == bytes([0xAA]):
                byte2 = ser.read(1)
                if byte2 == bytes([0x55]):
                    # Read packet type
                    pkt_type = ser.read(1)
                    if not pkt_type or pkt_type[0] != 0x01:
                        continue
                    
                    # Read timestamp (4 bytes)
                    ts_bytes = ser.read(4)
                    
                    # Read RSSI (1 byte)
                    rssi_byte = ser.read(1)
                    rssi = struct.unpack('<b', rssi_byte)[0]
                    
                    # Read channel (1 byte)
                    channel = ser.read(1)[0]
                    
                    # Read amplitude (104 * 2 bytes)
                    amp_bytes = ser.read(104 * 2)
                    amplitudes = struct.unpack('<104h', amp_bytes)
                    
                    # Read phase (104 * 2 bytes)
                    phase_bytes = ser.read(104 * 2)
                    phases = struct.unpack('<104h', phase_bytes)
                    
                    # Read checksum
                    checksum = ser.read(1)
                    
                    packets.append({
                        'rssi': rssi,
                        'channel': channel,
                        'amplitude': np.array(amplitudes, dtype=np.float32),
                        'phase': np.array(phases, dtype=np.float32)
                    })
                    
                    if len(packets) % 10 == 0:
                        print(f"  Collected {len(packets)}/{num_packets} packets...")
        
        except Exception as e:
            print(f"  Error: {e}")
            continue
    
    ser.close()
    
    if packets:
        amp_data = np.array([p['amplitude'] for p in packets])
        phase_data = np.array([p['phase'] for p in packets])
        return amp_data, phase_data, packets
    else:
        return None, None, []


def compare_data(wifall_csi, esp32_amp):
    """Compare WiFall and ESP32 data"""
    print("\n" + "="*60)
    print("DATA COMPARISON")
    print("="*60)
    
    # WiFall statistics
    wifall_flat = wifall_csi.flatten()
    print("\nWiFall Training Data:")
    print(f"  Shape: {wifall_csi.shape}")
    print(f"  Min: {wifall_flat.min():.2f}")
    print(f"  Max: {wifall_flat.max():.2f}")
    print(f"  Mean: {wifall_flat.mean():.2f}")
    print(f"  Std: {wifall_flat.std():.2f}")
    print(f"  Median: {np.median(wifall_flat):.2f}")
    
    # ESP32 statistics
    esp32_flat = esp32_amp.flatten()
    print("\nESP32 Collected Data:")
    print(f"  Shape: {esp32_amp.shape}")
    print(f"  Min: {esp32_flat.min():.2f}")
    print(f"  Max: {esp32_flat.max():.2f}")
    print(f"  Mean: {esp32_flat.mean():.2f}")
    print(f"  Std: {esp32_flat.std():.2f}")
    print(f"  Median: {np.median(esp32_flat):.2f}")
    
    # Check subcarrier activity
    print("\nSubcarrier Activity (non-zero values):")
    wifall_nonzero = np.count_nonzero(wifall_csi, axis=(0, 1))
    esp32_nonzero = np.count_nonzero(esp32_amp, axis=0)
    
    print(f"  WiFall - Active subcarriers: {np.sum(wifall_nonzero > 0)}/104")
    print(f"  ESP32  - Active subcarriers: {np.sum(esp32_nonzero > 0)}/104")
    
    # Check first 64 vs last 40 (padding region)
    print("\nFirst 64 subcarriers vs padded 40:")
    print(f"  WiFall first 64 mean: {wifall_csi[:, :, :64].mean():.2f}")
    print(f"  WiFall last 40 mean: {wifall_csi[:, :, 64:].mean():.2f}")
    print(f"  ESP32 first 64 mean: {esp32_amp[:, :64].mean():.2f}")
    print(f"  ESP32 last 40 mean: {esp32_amp[:, 64:].mean():.2f}")
    
    # Value range comparison
    print("\n" + "="*60)
    print("CRITICAL ANALYSIS")
    print("="*60)
    
    wifall_range = wifall_flat.max() - wifall_flat.min()
    esp32_range = esp32_flat.max() - esp32_flat.min()
    
    print(f"\nValue Range Ratio:")
    print(f"  WiFall range: {wifall_range:.2f}")
    print(f"  ESP32 range: {esp32_range:.2f}")
    print(f"  Ratio (ESP32/WiFall): {esp32_range/wifall_range:.2f}x")
    
    if esp32_range / wifall_range > 10 or esp32_range / wifall_range < 0.1:
        print("\n  ⚠️  WARNING: Value ranges differ significantly!")
        print("     The model may not work correctly.")
        print("     Consider scaling ESP32 data or retraining.")
    else:
        print("\n  ✓ Value ranges are reasonably similar.")
    
    # Check if padding is working
    if esp32_amp[:, 64:].mean() == 0:
        print("\n  ✓ Padding (zeros for subcarriers 64-103) is correct.")
    else:
        print("\n  ⚠️  Padding region has non-zero values!")
    
    return wifall_flat, esp32_flat


def visualize_comparison(wifall_csi, esp32_amp, wifall_samples):
    """Create visual comparison"""
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        
        # 1. WiFall sample heatmap
        ax = axes[0, 0]
        sample_idx = 0
        im = ax.imshow(wifall_csi[sample_idx].T, aspect='auto', cmap='viridis')
        ax.set_title(f'WiFall Sample #{sample_idx}')
        ax.set_xlabel('Time Step')
        ax.set_ylabel('Subcarrier')
        plt.colorbar(im, ax=ax)
        
        # 2. ESP32 sample heatmap
        ax = axes[0, 1]
        im = ax.imshow(esp32_amp.T, aspect='auto', cmap='viridis')
        ax.set_title('ESP32 Collected Data')
        ax.set_xlabel('Packet #')
        ax.set_ylabel('Subcarrier')
        plt.colorbar(im, ax=ax)
        
        # 3. Value distributions
        ax = axes[0, 2]
        wifall_flat = wifall_csi.flatten()
        esp32_flat = esp32_amp.flatten()
        ax.hist(wifall_flat, bins=50, alpha=0.5, label='WiFall', density=True)
        ax.hist(esp32_flat, bins=50, alpha=0.5, label='ESP32', density=True)
        ax.set_title('Value Distributions')
        ax.set_xlabel('CSI Value')
        ax.set_ylabel('Density')
        ax.legend()
        
        # 4. Subcarrier profile (mean across time)
        ax = axes[1, 0]
        wifall_mean = wifall_csi.mean(axis=(0, 1))
        esp32_mean = esp32_amp.mean(axis=0)
        ax.plot(wifall_mean, label='WiFall', alpha=0.7)
        ax.plot(esp32_mean, label='ESP32', alpha=0.7)
        ax.axvline(x=64, color='r', linestyle='--', label='Padding boundary')
        ax.set_title('Mean Subcarrier Profile')
        ax.set_xlabel('Subcarrier Index')
        ax.set_ylabel('Mean Value')
        ax.legend()
        
        # 5. Time series comparison
        ax = axes[1, 1]
        ax.plot(wifall_csi[sample_idx, :, 0], label='WiFall (subcarrier 0)', alpha=0.7)
        ax.plot(esp32_amp[:100, 0], label='ESP32 (subcarrier 0)', alpha=0.7)
        ax.set_title('Time Series - Subcarrier 0')
        ax.set_xlabel('Sample #')
        ax.set_ylabel('CSI Value')
        ax.legend()
        
        # 6. Activity class samples from WiFall
        ax = axes[1, 2]
        labels = {0: 'Fall', 1: 'Walk', 2: 'Sit', 3: 'Stand'}
        for label in wifall_samples:
            if label in wifall_samples and len(wifall_samples[label]) > 0:
                sample = wifall_samples[label][0]
                ax.plot(sample[:, 0], label=labels.get(label, f'Class {label}'), alpha=0.7)
        ax.set_title('WiFall Activity Samples (subcarrier 0)')
        ax.set_xlabel('Time Step')
        ax.set_ylabel('CSI Value')
        ax.legend()
        
        plt.tight_layout()
        plt.savefig('csi_comparison.png', dpi=150)
        print(f"\nVisualization saved to: csi_comparison.png")
        
    except ImportError:
        print("\nMatplotlib not available, skipping visualization")


def main():
    parser = argparse.ArgumentParser(description='Compare ESP32 and WiFall CSI data')
    parser.add_argument('--port', type=str, default='/dev/ttyUSB0', help='ESP32 serial port')
    parser.add_argument('--baud', type=int, default=19200, help='Baud rate')
    parser.add_argument('--wifall', type=str, default='./data/wifall', help='WiFall data directory')
    parser.add_argument('--packets', type=int, default=100, help='Number of ESP32 packets to collect')
    args = parser.parse_args()
    
    print("="*60)
    print("CSI DATA COMPARISON TOOL")
    print("="*60)
    
    # Load WiFall data
    print("\nLoading WiFall training data...")
    wifall_csi, wifall_labels, wifall_samples = load_wifall_sample(args.wifall)
    
    # Collect ESP32 data
    esp32_amp, esp32_phase, packets = collect_esp32_sample(args.port, args.baud, args.packets)
    
    if esp32_amp is None:
        print("\nFailed to collect ESP32 data!")
        print("Make sure:")
        print("  1. ESP32 is connected and running CSI firmware")
        print("  2. Correct serial port is specified")
        print("  3. You have proper permissions (dialout group)")
        return 1
    
    print(f"\nCollected {len(packets)} packets from ESP32")
    
    # Compare data
    compare_data(wifall_csi, esp32_amp)
    
    # Visualize
    visualize_comparison(wifall_csi, esp32_amp, wifall_samples)
    
    # Recommendations
    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    
    wifall_flat = wifall_csi.flatten()
    esp32_flat = esp32_amp.flatten()
    
    wifall_mean = wifall_flat.mean()
    esp32_mean = esp32_flat.mean()
    wifall_std = wifall_flat.std()
    esp32_std = esp32_flat.std()
    
    # Check if normalization would help
    if abs(esp32_mean - wifall_mean) > wifall_std:
        print("\n1. Mean values differ significantly.")
        print(f"   Consider normalizing: (data - {esp32_mean:.2f}) / {esp32_std:.2f}")
    
    if abs(esp32_std - wifall_std) / wifall_std > 0.5:
        print("\n2. Standard deviations differ significantly.")
        print("   The model's internal normalization should handle this.")
    
    print("\n3. For best results:")
    print("   - The model uses per-batch normalization during preprocessing")
    print("   - Ensure ESP32 WiFi channel matches training conditions")
    print("   - Keep ESP32 stationary during detection")
    
    return 0


if __name__ == "__main__":
    exit(main())
