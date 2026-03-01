"""
Noise Filters — Butterworth low-pass and Hampel filters for CSI data.

Removes high-frequency electronic noise and sudden outlier spikes from
raw CSI amplitude/phase signals.
"""

import numpy as np
from scipy.signal import butter, filtfilt


def butterworth_lowpass(data: np.ndarray, cutoff: float = 20.0,
                        fs: float = 100.0, order: int = 4) -> np.ndarray:
    """
    Apply a Butterworth low-pass filter along axis 0 (time).

    Args:
        data: (n_samples, n_subcarriers) array
        cutoff: Cut-off frequency in Hz
        fs: Sampling frequency in Hz (= packet rate from ESP32)
        order: Filter order
    Returns:
        Filtered array, same shape as input
    """
    nyq = 0.5 * fs
    normalized_cutoff = cutoff / nyq

    # Clamp to valid range
    if normalized_cutoff >= 1.0:
        return data  # cutoff >= Nyquist, no filtering needed

    b, a = butter(order, normalized_cutoff, btype='low')

    # Need enough samples for filtfilt (at least 3 * max(len(a), len(b)))
    min_samples = 3 * max(len(a), len(b))
    if data.shape[0] < min_samples:
        return data  # Not enough data to filter

    return filtfilt(b, a, data, axis=0).astype(data.dtype)


def hampel_filter(data: np.ndarray, window_size: int = 5,
                  n_sigma: float = 3.0) -> np.ndarray:
    """
    Hampel filter — replaces outliers with the local median.

    For each point, computes the median and MAD (median absolute deviation)
    within a sliding window. Points deviating more than n_sigma * MAD
    from the median are replaced with the median value.

    Args:
        data: (n_samples, n_subcarriers) array
        window_size: Half-window size (total window = 2*window_size + 1)
        n_sigma: Number of MAD deviations to consider as outlier
    Returns:
        Cleaned array, same shape as input
    """
    filtered = data.copy()
    n_samples = data.shape[0]
    k = 1.4826  # Scale factor for MAD to approximate std dev

    for i in range(window_size, n_samples - window_size):
        window = data[i - window_size:i + window_size + 1]
        median = np.median(window, axis=0)
        mad = k * np.median(np.abs(window - median), axis=0)

        # Avoid division by zero
        mad = np.where(mad < 1e-10, 1e-10, mad)

        # Replace outliers
        diff = np.abs(data[i] - median)
        outlier_mask = diff > n_sigma * mad
        filtered[i] = np.where(outlier_mask, median, data[i])

    return filtered


def filter_csi(amplitude: np.ndarray, fs: float = 100.0,
               cutoff: float = 20.0, hampel_window: int = 5) -> np.ndarray:
    """
    Full filtering pipeline: Hampel (remove spikes) → Butterworth (smooth).

    Args:
        amplitude: (n_samples, n_subcarriers) array of CSI amplitudes
        fs: Sampling frequency (packets per second from ESP32)
        cutoff: Low-pass cutoff frequency in Hz
        hampel_window: Hampel filter half-window size
    Returns:
        Filtered amplitude array
    """
    # Step 1: Remove outlier spikes
    cleaned = hampel_filter(amplitude, window_size=hampel_window)

    # Step 2: Smooth with low-pass filter
    smoothed = butterworth_lowpass(cleaned, cutoff=cutoff, fs=fs)

    return smoothed
