"""
Spectrogram — Convert CSI time series into time-frequency spectrograms.

Creates 2D spectrogram images from CSI amplitude data using STFT.
These spectrograms become the input to the CNN + Bi-LSTM model —
the CNN reads the "shape" of the disturbance, the LSTM tracks the sequence.
"""

import numpy as np
from scipy.signal import stft


def generate_spectrogram(amplitude: np.ndarray, fs: float = 100.0,
                         nperseg: int = 64, noverlap: int = 48) -> tuple:
    """
    Generate a spectrogram from a 1D CSI amplitude signal.

    Args:
        amplitude: (n_samples,) single subcarrier or PCA component
        fs: Sampling frequency in Hz
        nperseg: STFT window length (samples)
        noverlap: STFT overlap (samples)
    Returns:
        (frequencies, times, spectrogram_magnitude)
    """
    f, t, Zxx = stft(amplitude, fs=fs, nperseg=nperseg, noverlap=noverlap)
    magnitude = np.abs(Zxx)
    return f, t, magnitude


def create_sliding_windows(data: np.ndarray, window_size: int,
                           step_size: int) -> np.ndarray:
    """
    Slice data into overlapping windows.

    Args:
        data: (n_samples, n_features) array
        window_size: Number of samples per window
        step_size: Step between windows (window_size // 2 for 50% overlap)
    Returns:
        (n_windows, window_size, n_features) array
    """
    n_samples = data.shape[0]
    n_windows = (n_samples - window_size) // step_size + 1

    if n_windows <= 0:
        return np.array([])

    windows = np.zeros((n_windows, window_size) + data.shape[1:], dtype=data.dtype)
    for i in range(n_windows):
        start = i * step_size
        windows[i] = data[start:start + window_size]

    return windows


def windows_to_spectrograms(windows: np.ndarray, fs: float = 100.0,
                            nperseg: int = 64,
                            noverlap: int = 48) -> np.ndarray:
    """
    Convert sliding windows of CSI data into spectrograms.

    Args:
        windows: (n_windows, window_size, n_features) from create_sliding_windows
        fs: Sampling frequency
        nperseg: STFT window length
        noverlap: STFT overlap
    Returns:
        (n_windows, n_freq_bins, n_time_steps, n_features) spectrogram array
    """
    spectrograms = []

    for window in windows:
        # window shape: (window_size, n_features)
        window_specs = []
        for feat_idx in range(window.shape[1]):
            _, _, mag = generate_spectrogram(
                window[:, feat_idx], fs=fs, nperseg=nperseg, noverlap=noverlap
            )
            window_specs.append(mag)

        # Stack features: (n_freq, n_time, n_features)
        spec = np.stack(window_specs, axis=-1)
        spectrograms.append(spec)

    return np.array(spectrograms)


def normalize_spectrograms(spectrograms: np.ndarray) -> np.ndarray:
    """
    Normalize spectrograms to [0, 1] range per-sample.

    Args:
        spectrograms: (n_windows, n_freq, n_time, n_features) array
    Returns:
        Normalized array, same shape
    """
    normalized = np.zeros_like(spectrograms)
    for i in range(len(spectrograms)):
        s_min = spectrograms[i].min()
        s_max = spectrograms[i].max()
        if s_max - s_min > 1e-10:
            normalized[i] = (spectrograms[i] - s_min) / (s_max - s_min)
        else:
            normalized[i] = 0.0
    return normalized


def process_csi_to_spectrograms(amplitude: np.ndarray, fs: float = 100.0,
                                window_sec: float = 2.0,
                                overlap: float = 0.5,
                                nperseg: int = 64,
                                noverlap: int = 48) -> np.ndarray:
    """
    Full pipeline: CSI amplitude → sliding windows → spectrograms → normalized.

    Args:
        amplitude: (n_samples, n_features) filtered CSI data
        fs: Sampling rate (Hz)
        window_sec: Window duration in seconds
        overlap: Fraction of window overlap (0.5 = 50%)
        nperseg: STFT segment length
        noverlap: STFT overlap
    Returns:
        (n_windows, n_freq, n_time, n_features) normalized spectrograms
    """
    window_size = int(window_sec * fs)
    step_size = int(window_size * (1 - overlap))

    print(f"[spectrogram] window={window_size} samples ({window_sec}s), "
          f"step={step_size}, total_samples={amplitude.shape[0]}")

    # Create sliding windows
    windows = create_sliding_windows(amplitude, window_size, step_size)
    if len(windows) == 0:
        print("[spectrogram] Not enough data for even one window")
        return np.array([])

    print(f"[spectrogram] {len(windows)} windows created")

    # Convert to spectrograms
    specs = windows_to_spectrograms(windows, fs=fs, nperseg=nperseg, noverlap=noverlap)

    # Normalize
    specs = normalize_spectrograms(specs)

    print(f"[spectrogram] Output shape: {specs.shape}")
    return specs
