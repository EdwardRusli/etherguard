"""
Preprocessing Demo — Run the full Phase 2 pipeline on captured CSI data.

Usage:
    # First capture some CSI data:
    python serial_reader.py -p /dev/ttyUSB0 -b 115200 -n 500 -o ../data/raw/csi_capture.csv

    # Then run this pipeline:
    python run_preprocessing.py --input ../data/raw/csi_capture.csv
"""

import argparse
import numpy as np
import csv
from pathlib import Path

from preprocessing.filters import filter_csi
from preprocessing.pca import fit_pca
from preprocessing.spectrogram import process_csi_to_spectrograms


def load_csi_csv(csv_path: str) -> tuple:
    """Load a CSV file produced by serial_reader.py."""
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)

        # Find amplitude columns
        amp_cols = [i for i, h in enumerate(header) if h.startswith('amp_')]
        phase_cols = [i for i, h in enumerate(header) if h.startswith('phase_')]

        amplitudes = []
        timestamps = []
        rssi_values = []

        for row in reader:
            timestamps.append(int(row[0]))
            rssi_values.append(int(row[1]))
            amplitudes.append([float(row[i]) for i in amp_cols])

    amplitude = np.array(amplitudes)
    timestamps = np.array(timestamps)
    rssi = np.array(rssi_values)

    print(f"[load] {len(timestamps)} frames, {amplitude.shape[1]} subcarriers")
    return timestamps, rssi, amplitude


def main():
    parser = argparse.ArgumentParser(description='Run CSI preprocessing pipeline')
    parser.add_argument('-i', '--input', required=True, help='Input CSV from serial_reader')
    parser.add_argument('-o', '--output', default='../data/processed/',
                        help='Output directory for processed data')
    parser.add_argument('--fs', type=float, default=100.0,
                        help='Sampling frequency in Hz (packet rate)')
    parser.add_argument('--cutoff', type=float, default=20.0,
                        help='Low-pass filter cutoff frequency in Hz')
    parser.add_argument('--pca-components', type=int, default=10,
                        help='Max PCA components to keep')
    parser.add_argument('--window-sec', type=float, default=2.0,
                        help='Spectrogram window duration in seconds')
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load raw CSI data
    print("\n=== Step 1: Load Raw Data ===")
    timestamps, rssi, amplitude = load_csi_csv(args.input)

    # Step 2: Filter noise
    print("\n=== Step 2: Noise Filtering ===")
    filtered = filter_csi(amplitude, fs=args.fs, cutoff=args.cutoff)
    print(f"[filter] Input range: [{amplitude.min():.2f}, {amplitude.max():.2f}]")
    print(f"[filter] Output range: [{filtered.min():.2f}, {filtered.max():.2f}]")

    # Step 3: PCA dimensionality reduction
    print("\n=== Step 3: PCA ===")
    pca_model, reduced, variance_ratio = fit_pca(filtered, n_components=args.pca_components)
    print(f"[pca] Reduced from {filtered.shape[1]} to {reduced.shape[1]} dimensions")

    # Step 4: Generate spectrograms
    print("\n=== Step 4: Spectrograms ===")
    spectrograms = process_csi_to_spectrograms(
        reduced, fs=args.fs, window_sec=args.window_sec
    )

    if len(spectrograms) == 0:
        print("[!] Not enough data for spectrograms. Capture more frames.")
        return

    # Save outputs
    np.save(output_dir / 'filtered.npy', filtered)
    np.save(output_dir / 'pca_reduced.npy', reduced)
    np.save(output_dir / 'spectrograms.npy', spectrograms)
    np.save(output_dir / 'timestamps.npy', timestamps)

    print(f"\n=== Done ===")
    print(f"Saved to {output_dir}/:")
    print(f"  filtered.npy      — {filtered.shape}")
    print(f"  pca_reduced.npy   — {reduced.shape}")
    print(f"  spectrograms.npy  — {spectrograms.shape}")
    print(f"  timestamps.npy    — {timestamps.shape}")
    print(f"\nSpectrograms are ready for the CNN + Bi-LSTM model (Phase 3).")


if __name__ == '__main__':
    main()
