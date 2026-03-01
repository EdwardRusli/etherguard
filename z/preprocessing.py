#!/usr/bin/env python3
"""
CSI Data Preprocessing for Fall Detection
Based on research methodology from Chu et al., IEEE Access 2023

Preprocessing pipeline:
1. Amplitude normalization
2. Outlier removal and smoothing
3. Feature extraction (time-domain, frequency-domain)
4. Spectrogram generation
"""

import numpy as np
from scipy import signal
from scipy.ndimage import uniform_filter1d
from typing import Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class CSIPreprocessor:
    """
    Preprocesses CSI data for fall detection model.
    
    Key preprocessing steps based on the paper:
    1. Linear transformation to remove DC component
    2. Low-pass filtering to remove high-frequency noise
    3. Amplitude normalization
    4. Outlier detection and removal
    """
    
    def __init__(
        self,
        num_subcarriers: int = 64,
        sample_rate: float = 100.0,  # Hz
        lowpass_cutoff: float = 30.0,  # Hz
        normalize: bool = True,
        remove_outliers: bool = True,
        outlier_threshold: float = 3.0  # Standard deviations
    ):
        """
        Initialize CSI preprocessor.
        
        Args:
            num_subcarriers: Number of CSI subcarriers
            sample_rate: CSI sample rate in Hz
            lowpass_cutoff: Low-pass filter cutoff frequency
            normalize: Whether to normalize amplitude values
            remove_outliers: Whether to remove outliers
            outlier_threshold: Threshold for outlier detection (in std devs)
        """
        self.num_subcarriers = num_subcarriers
        self.sample_rate = sample_rate
        self.lowpass_cutoff = lowpass_cutoff
        self.normalize = normalize
        self.remove_outliers = remove_outliers
        self.outlier_threshold = outlier_threshold
        
        # Design low-pass filter
        nyquist = sample_rate / 2
        normalized_cutoff = min(lowpass_cutoff / nyquist, 0.99)
        self.b, self.a = signal.butter(4, normalized_cutoff, btype='low')
        
        # State for filter (to handle streaming data)
        self.filter_state_amp = None
        self.filter_state_phase = None
    
    def remove_dc_component(self, data: np.ndarray) -> np.ndarray:
        """
        Remove DC component using linear detrending.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
        
        Returns:
            DC-removed data
        """
        return signal.detrend(data, axis=0)
    
    def apply_lowpass_filter(self, data: np.ndarray, is_amplitude: bool = True) -> np.ndarray:
        """
        Apply low-pass filter to remove high-frequency noise.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
            is_amplitude: Whether this is amplitude data (for state tracking)
        
        Returns:
            Filtered data
        """
        if is_amplitude:
            if self.filter_state_amp is None:
                filtered_data, self.filter_state_amp = signal.lfilter(
                    self.b, self.a, data, axis=0, zi=signal.lfilter_zi(self.b, self.a)
                )
                # Initialize state for all subcarriers
                self.filter_state_amp = np.tile(
                    self.filter_state_amp[:, 0:1], 
                    (1, self.num_subcarriers)
                )
            else:
                filtered_data, self.filter_state_amp = signal.lfilter(
                    self.b, self.a, data, axis=0, zi=self.filter_state_amp
                )
        else:
            if self.filter_state_phase is None:
                filtered_data, self.filter_state_phase = signal.lfilter(
                    self.b, self.a, data, axis=0, zi=signal.lfilter_zi(self.b, self.a)
                )
                self.filter_state_phase = np.tile(
                    self.filter_state_phase[:, 0:1],
                    (1, self.num_subcarriers)
                )
            else:
                filtered_data, self.filter_state_phase = signal.lfilter(
                    self.b, self.a, data, axis=0, zi=self.filter_state_phase
                )
        
        return filtered_data
    
    def normalize_data(self, data: np.ndarray) -> np.ndarray:
        """
        Normalize CSI data to zero mean and unit variance.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
        
        Returns:
            Normalized data
        """
        mean = np.mean(data, axis=0, keepdims=True)
        std = np.std(data, axis=0, keepdims=True) + 1e-8
        return (data - mean) / std
    
    def remove_outliers_from_data(self, data: np.ndarray) -> np.ndarray:
        """
        Remove outliers using median absolute deviation.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
        
        Returns:
            Data with outliers replaced by median-filtered values
        """
        # Calculate median and MAD
        median = np.median(data, axis=0)
        mad = np.median(np.abs(data - median), axis=0) + 1e-8
        
        # Identify outliers
        z_scores = np.abs((data - median) / (1.4826 * mad))
        outlier_mask = z_scores > self.outlier_threshold
        
        # Replace outliers with median-filtered values
        if np.any(outlier_mask):
            median_filtered = uniform_filter1d(data, size=5, axis=0)
            data = np.where(outlier_mask, median_filtered, data)
        
        return data
    
    def unwrap_phase(self, phase: np.ndarray) -> np.ndarray:
        """
        Unwrap phase to remove 2π discontinuities.
        
        Args:
            phase: Phase values (may be wrapped)
        
        Returns:
            Unwrapped phase
        """
        return np.unwrap(phase, axis=0)
    
    def preprocess(
        self,
        amplitude: np.ndarray,
        phase: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Full preprocessing pipeline for CSI data.
        
        Args:
            amplitude: Amplitude data of shape (num_samples, num_subcarriers)
            phase: Phase data of shape (num_samples, num_subcarriers)
        
        Returns:
            Tuple of (processed_amplitude, processed_phase)
        """
        # Make copies to avoid modifying original data
        amp = amplitude.copy().astype(np.float32)
        ph = phase.copy().astype(np.float32)
        
        # 1. Remove DC component
        amp = self.remove_dc_component(amp)
        ph = self.remove_dc_component(ph)
        
        # 2. Unwrap phase
        ph = self.unwrap_phase(ph)
        
        # 3. Apply low-pass filter
        amp = self.apply_lowpass_filter(amp, is_amplitude=True)
        ph = self.apply_lowpass_filter(ph, is_amplitude=False)
        
        # 4. Remove outliers
        if self.remove_outliers:
            amp = self.remove_outliers_from_data(amp)
        
        # 5. Normalize
        if self.normalize:
            amp = self.normalize_data(amp)
            ph = self.normalize_data(ph)
        
        return amp, ph
    
    def reset_filter_state(self):
        """Reset filter state for new data stream"""
        self.filter_state_amp = None
        self.filter_state_phase = None


class FeatureExtractor:
    """
    Extracts features from preprocessed CSI data for fall detection.
    
    Features include:
    - Time-domain features: mean, std, max, min, energy
    - Frequency-domain features: dominant frequency, spectral energy
    - Statistical features: kurtosis, skewness
    - Wavelet features: energy in different frequency bands
    """
    
    def __init__(self, num_subcarriers: int = 64, sample_rate: float = 100.0):
        """
        Initialize feature extractor.
        
        Args:
            num_subcarriers: Number of CSI subcarriers
            sample_rate: CSI sample rate in Hz
        """
        self.num_subcarriers = num_subcarriers
        self.sample_rate = sample_rate
    
    def extract_time_features(self, data: np.ndarray) -> np.ndarray:
        """
        Extract time-domain features.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
        
        Returns:
            Time-domain features
        """
        features = []
        
        # Statistical features per subcarrier
        features.append(np.mean(data, axis=0))
        features.append(np.std(data, axis=0))
        features.append(np.max(data, axis=0))
        features.append(np.min(data, axis=0))
        features.append(np.ptp(data, axis=0))  # Peak-to-peak
        
        # Energy
        features.append(np.sum(data ** 2, axis=0))
        
        # Root mean square
        features.append(np.sqrt(np.mean(data ** 2, axis=0)))
        
        # Velocity (rate of change)
        velocity = np.diff(data, axis=0)
        features.append(np.mean(velocity, axis=0))
        features.append(np.std(velocity, axis=0))
        
        # Acceleration (second derivative)
        acceleration = np.diff(velocity, axis=0)
        features.append(np.mean(np.abs(acceleration), axis=0))
        
        return np.concatenate(features)
    
    def extract_frequency_features(self, data: np.ndarray) -> np.ndarray:
        """
        Extract frequency-domain features using FFT.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
        
        Returns:
            Frequency-domain features
        """
        features = []
        
        # Compute FFT
        fft_data = np.fft.rfft(data, axis=0)
        fft_magnitude = np.abs(fft_data)
        fft_freqs = np.fft.rfftfreq(data.shape[0], 1/self.sample_rate)
        
        # Dominant frequency
        dom_freq_idx = np.argmax(fft_magnitude, axis=0)
        dom_freq = fft_freqs[dom_freq_idx]
        features.append(dom_freq)
        
        # Spectral centroid
        spectral_centroid = np.sum(
            fft_magnitude * fft_freqs[:, np.newaxis], axis=0
        ) / (np.sum(fft_magnitude, axis=0) + 1e-8)
        features.append(spectral_centroid)
        
        # Spectral bandwidth
        spectral_bw = np.sqrt(np.sum(
            ((fft_freqs[:, np.newaxis] - spectral_centroid) ** 2) * fft_magnitude, axis=0
        ) / (np.sum(fft_magnitude, axis=0) + 1e-8))
        features.append(spectral_bw)
        
        # Spectral energy in different bands
        low_band = (fft_freqs >= 0) & (fft_freqs < 5)
        mid_band = (fft_freqs >= 5) & (fft_freqs < 15)
        high_band = (fft_freqs >= 15) & (fft_freqs < 30)
        
        features.append(np.sum(fft_magnitude[low_band] ** 2, axis=0))
        features.append(np.sum(fft_magnitude[mid_band] ** 2, axis=0))
        features.append(np.sum(fft_magnitude[high_band] ** 2, axis=0))
        
        return np.concatenate(features)
    
    def extract_correlation_features(self, data: np.ndarray) -> np.ndarray:
        """
        Extract correlation-based features between subcarriers.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
        
        Returns:
            Correlation features
        """
        features = []
        
        # Correlation matrix
        corr_matrix = np.corrcoef(data.T)
        
        # Mean correlation (excluding diagonal)
        mask = ~np.eye(self.num_subcarriers, dtype=bool)
        mean_corr = np.mean(np.abs(corr_matrix[mask]))
        features.append([mean_corr])
        
        # Max correlation
        max_corr = np.max(corr_matrix[mask])
        features.append([max_corr])
        
        return np.concatenate(features)
    
    def extract_features(
        self,
        amplitude: np.ndarray,
        phase: np.ndarray
    ) -> np.ndarray:
        """
        Extract all features from CSI data.
        
        Args:
            amplitude: Amplitude data of shape (num_samples, num_subcarriers)
            phase: Phase data of shape (num_samples, num_subcarriers)
        
        Returns:
            Feature vector
        """
        features = []
        
        # Time-domain features from amplitude
        features.append(self.extract_time_features(amplitude))
        
        # Time-domain features from phase
        features.append(self.extract_time_features(phase))
        
        # Frequency-domain features from amplitude
        features.append(self.extract_frequency_features(amplitude))
        
        # Frequency-domain features from phase
        features.append(self.extract_frequency_features(phase))
        
        # Correlation features
        features.append(self.extract_correlation_features(amplitude))
        
        return np.concatenate(features)


class SpectrogramGenerator:
    """
    Generates spectrograms from CSI data for CNN-based fall detection.
    
    Based on the paper methodology, spectrograms capture the temporal-frequency
    patterns that distinguish falls from other activities.
    """
    
    def __init__(
        self,
        sample_rate: float = 100.0,
        nperseg: int = 32,
        noverlap: int = 24,
        nfft: int = 64
    ):
        """
        Initialize spectrogram generator.
        
        Args:
            sample_rate: CSI sample rate in Hz
            nperseg: Segment length for STFT
            noverlap: Overlap between segments
            nfft: FFT size
        """
        self.sample_rate = sample_rate
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.nfft = nfft
    
    def generate_spectrogram(
        self,
        data: np.ndarray,
        aggregate_subcarriers: bool = True
    ) -> np.ndarray:
        """
        Generate spectrogram from CSI data.
        
        Args:
            data: CSI data of shape (num_samples, num_subcarriers)
            aggregate_subcarriers: If True, average across subcarriers
        
        Returns:
            Spectrogram of shape (freq_bins, time_bins) or 
            (freq_bins, time_bins, num_subcarriers) if not aggregated
        """
        if aggregate_subcarriers:
            # Average across subcarriers
            data_avg = np.mean(data, axis=1)
            
            f, t, Sxx = signal.spectrogram(
                data_avg,
                fs=self.sample_rate,
                nperseg=self.nperseg,
                noverlap=self.noverlap,
                nfft=self.nfft
            )
            
            # Normalize
            Sxx = 10 * np.log10(Sxx + 1e-10)
            Sxx = (Sxx - np.min(Sxx)) / (np.max(Sxx) - np.min(Sxx) + 1e-10)
            
            return Sxx
        else:
            # Generate spectrogram for each subcarrier
            spectrograms = []
            for sc in range(data.shape[1]):
                f, t, Sxx = signal.spectrogram(
                    data[:, sc],
                    fs=self.sample_rate,
                    nperseg=self.nperseg,
                    noverlap=self.noverlap,
                    nfft=self.nfft
                )
                Sxx = 10 * np.log10(Sxx + 1e-10)
                Sxx = (Sxx - np.min(Sxx)) / (np.max(Sxx) - np.min(Sxx) + 1e-10)
                spectrograms.append(Sxx)
            
            return np.stack(spectrograms, axis=-1)
    
    def generate_doppler_spectrogram(
        self,
        amplitude: np.ndarray,
        phase: np.ndarray
    ) -> np.ndarray:
        """
        Generate Doppler spectrogram using phase derivative.
        
        The phase derivative approximates Doppler shift caused by motion.
        
        Args:
            amplitude: Amplitude data
            phase: Phase data
        
        Returns:
            Doppler spectrogram
        """
        # Phase derivative (instantaneous Doppler frequency)
        doppler = np.diff(phase, axis=0) * self.sample_rate / (2 * np.pi)
        
        # Weight by amplitude
        weighted_doppler = doppler * amplitude[:-1]
        
        # Generate spectrogram
        return self.generate_spectrogram(weighted_doppler)


if __name__ == "__main__":
    # Test preprocessing
    preprocessor = CSIPreprocessor()
    feature_extractor = FeatureExtractor()
    spectrogram_gen = SpectrogramGenerator()
    
    # Generate synthetic CSI data for testing
    num_samples = 100
    num_subcarriers = 64
    
    amplitude = np.random.randn(num_samples, num_subcarriers).astype(np.float32)
    phase = np.random.randn(num_samples, num_subcarriers).astype(np.float32)
    
    # Preprocess
    amp_processed, phase_processed = preprocessor.preprocess(amplitude, phase)
    print(f"Processed amplitude shape: {amp_processed.shape}")
    print(f"Processed phase shape: {phase_processed.shape}")
    
    # Extract features
    features = feature_extractor.extract_features(amp_processed, phase_processed)
    print(f"Feature vector length: {len(features)}")
    
    # Generate spectrogram
    spec = spectrogram_gen.generate_spectrogram(amp_processed)
    print(f"Spectrogram shape: {spec.shape}")
