"""
Test the preprocessing pipeline with synthetic CSI data.
No ESP32 needed — generates fake CSI signals with simulated movement.

Usage:
    cd jetson/
    python test_preprocessing.py
"""

import numpy as np
import csv
from pathlib import Path

from preprocessing.filters import filter_csi, hampel_filter, butterworth_lowpass
from preprocessing.pca import fit_pca
from preprocessing.spectrogram import process_csi_to_spectrograms


def generate_fake_csi(n_samples=500, n_subcarriers=52, fs=100.0):
    """
    Generate synthetic CSI amplitude data that mimics real signals:
    - Base signal: steady-state WiFi (small amplitude)
    - Movement event: a 'fall' burst around the middle
    - Noise: random jitter + a few outlier spikes
    """
    t = np.arange(n_samples) / fs

    # Base: gentle sine waves per subcarrier (simulates multipath)
    amplitude = np.zeros((n_samples, n_subcarriers))
    for sc in range(n_subcarriers):
        freq = 0.5 + sc * 0.1  # different base freq per subcarrier
        amplitude[:, sc] = 5.0 + 2.0 * np.sin(2 * np.pi * freq * t)

    # Movement event: big disturbance in the middle (simulates a fall)
    fall_start = int(n_samples * 0.4)
    fall_end = int(n_samples * 0.6)
    for sc in range(n_subcarriers):
        amplitude[fall_start:fall_end, sc] += 10.0 * np.exp(
            -0.5 * ((t[fall_start:fall_end] - t[(fall_start + fall_end) // 2]) / 0.3) ** 2
        )

    # Add noise
    amplitude += np.random.normal(0, 0.5, amplitude.shape)

    # Add 10 random outlier spikes
    for _ in range(10):
        i = np.random.randint(0, n_samples)
        j = np.random.randint(0, n_subcarriers)
        amplitude[i, j] += np.random.choice([-1, 1]) * 30.0

    return amplitude, t


def test_filters(amplitude):
    """Test noise filtering."""
    print("\n--- Test: Hampel filter ---")
    cleaned = hampel_filter(amplitude, window_size=5, n_sigma=3.0)
    spike_reduction = np.abs(amplitude).max() - np.abs(cleaned).max()
    print(f"  Peak reduced by: {spike_reduction:.2f}")
    assert spike_reduction > 0, "Hampel should reduce outlier peaks"
    print("  ✓ Hampel filter works")

    print("\n--- Test: Butterworth low-pass ---")
    smoothed = butterworth_lowpass(cleaned, cutoff=20.0, fs=100.0)
    raw_std = np.std(np.diff(cleaned, axis=0))
    smooth_std = np.std(np.diff(smoothed, axis=0))
    print(f"  Diff std: {raw_std:.4f} → {smooth_std:.4f}")
    assert smooth_std < raw_std, "Butterworth should reduce high-freq variation"
    print("  ✓ Butterworth filter works")

    print("\n--- Test: Full filter pipeline ---")
    filtered = filter_csi(amplitude, fs=100.0, cutoff=20.0)
    print(f"  Shape: {filtered.shape}")
    assert filtered.shape == amplitude.shape
    print("  ✓ Full pipeline works")

    return filtered


def test_pca(filtered):
    """Test PCA dimensionality reduction."""
    print("\n--- Test: PCA ---")
    pca_model, reduced, variance_ratio = fit_pca(filtered, n_components=10)
    print(f"  {filtered.shape[1]} subcarriers → {reduced.shape[1]} components")
    assert reduced.shape[1] <= 10
    assert reduced.shape[0] == filtered.shape[0]
    print(f"  Top 3 variance ratios: {variance_ratio[:3]}")
    print("  ✓ PCA works")
    return reduced


def test_spectrograms(reduced):
    """Test spectrogram generation."""
    print("\n--- Test: Spectrograms ---")
    specs = process_csi_to_spectrograms(reduced, fs=100.0, window_sec=2.0)
    if len(specs) == 0:
        print("  ✗ Not enough data (need >200 samples for 2s windows at 100Hz)")
        return None
    print(f"  Shape: {specs.shape}")
    print(f"  Range: [{specs.min():.3f}, {specs.max():.3f}]")
    assert specs.min() >= 0.0 and specs.max() <= 1.0, "Should be normalized [0,1]"
    print("  ✓ Spectrograms work")
    return specs


def main():
    print("=" * 50)
    print("EtherGuard Preprocessing Pipeline Test")
    print("=" * 50)

    # Generate fake data
    print("\nGenerating synthetic CSI data...")
    amplitude, t = generate_fake_csi(n_samples=500, n_subcarriers=52)
    print(f"  Shape: {amplitude.shape}  (500 samples × 52 subcarriers)")

    # Test each stage
    filtered = test_filters(amplitude)
    reduced = test_pca(filtered)
    specs = test_spectrograms(reduced)

    # Summary
    print("\n" + "=" * 50)
    if specs is not None:
        print("ALL TESTS PASSED ✓")
        print(f"\nPipeline: {amplitude.shape} → {filtered.shape} → "
              f"{reduced.shape} → {specs.shape}")
        print("Spectrograms are ready for the AI model.")
    else:
        print("Some tests did not complete.")
    print("=" * 50)


if __name__ == '__main__':
    main()
