"""
Dataset — PyTorch Dataset and DataLoader for CSI spectrograms.

Supports:
  - Loading .npy spectrogram files with labels
  - Train/val/test splits (70/15/15)
  - Synthetic data generation for testing without real data
"""

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, random_split
from pathlib import Path


class CSIDataset(Dataset):
    """PyTorch Dataset for CSI spectrograms."""

    def __init__(self, spectrograms: np.ndarray, labels: np.ndarray):
        """
        Args:
            spectrograms: (N, n_freq, n_time, n_features) array
            labels: (N,) integer class labels
        """
        # Rearrange to PyTorch format: (N, channels, height, width)
        # From (N, freq, time, features) → (N, features, freq, time)
        self.spectrograms = torch.FloatTensor(
            spectrograms.transpose(0, 3, 1, 2)
        )
        self.labels = torch.LongTensor(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return self.spectrograms[idx], self.labels[idx]


def load_dataset(spec_path: str, labels_path: str) -> CSIDataset:
    """Load spectrograms and labels from .npy files."""
    specs = np.load(spec_path)
    labels = np.load(labels_path)
    assert len(specs) == len(labels), "Spectrogram and label counts must match"
    print(f"[dataset] Loaded {len(specs)} samples, shape={specs.shape}")
    return CSIDataset(specs, labels)


def generate_synthetic_dataset(n_samples: int = 400, n_freq: int = 33,
                               n_time: int = 5, n_features: int = 10,
                               n_classes: int = 4) -> CSIDataset:
    """
    Generate synthetic spectrograms for testing the training pipeline.
    Each class gets distinct spectral patterns so the model can learn.
    """
    specs = np.zeros((n_samples, n_freq, n_time, n_features), dtype=np.float32)
    labels = np.zeros(n_samples, dtype=np.int64)

    samples_per_class = n_samples // n_classes

    for c in range(n_classes):
        start = c * samples_per_class
        end = start + samples_per_class

        for i in range(start, end):
            labels[i] = c
            # Each class has a different dominant frequency band
            center_freq = int(n_freq * (c + 1) / (n_classes + 1))
            bandwidth = max(2, n_freq // 8)

            for f in range(n_features):
                base = np.random.randn(n_freq, n_time) * 0.1
                # Add class-specific pattern
                freq_lo = max(0, center_freq - bandwidth)
                freq_hi = min(n_freq, center_freq + bandwidth)
                base[freq_lo:freq_hi, :] += 0.5 + 0.3 * c
                specs[i, :, :, f] = base

    # Normalize to [0, 1]
    specs = (specs - specs.min()) / (specs.max() - specs.min() + 1e-10)

    # Shuffle
    perm = np.random.permutation(n_samples)
    specs = specs[perm]
    labels = labels[perm]

    print(f"[dataset] Generated {n_samples} synthetic samples, "
          f"{n_classes} classes, shape={specs.shape}")
    return CSIDataset(specs, labels)


def create_dataloaders(dataset: CSIDataset, batch_size: int = 32,
                       train_ratio: float = 0.7, val_ratio: float = 0.15,
                       seed: int = 42) -> tuple:
    """
    Split dataset into train/val/test and create DataLoaders.

    Returns:
        (train_loader, val_loader, test_loader)
    """
    n = len(dataset)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    n_test = n - n_train - n_val

    generator = torch.Generator().manual_seed(seed)
    train_set, val_set, test_set = random_split(
        dataset, [n_train, n_val, n_test], generator=generator
    )

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=False)

    print(f"[dataset] Split: {n_train} train / {n_val} val / {n_test} test")
    return train_loader, val_loader, test_loader
