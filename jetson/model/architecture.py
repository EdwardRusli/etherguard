"""
CNN + Bi-LSTM Model — Hybrid architecture for WiFi CSI fall detection.

Architecture:
    Input: spectrogram (1, H, W) per PCA component
        ↓
    Conv2D → BatchNorm → ReLU → MaxPool  (×3 blocks)
        ↓
    Flatten along time axis → sequence of feature vectors
        ↓
    Bi-LSTM (2 layers, hidden=128)
        ↓
    Fully Connected → Dropout → Softmax
    Output: [fall, walk, sit, idle]
"""

import torch
import torch.nn as nn


class CSIFallDetector(nn.Module):
    """CNN + Bi-LSTM hybrid for CSI spectrogram classification."""

    def __init__(self, n_classes: int = 4, n_features: int = 10,
                 n_freq: int = 33, lstm_hidden: int = 128,
                 lstm_layers: int = 2, dropout: float = 0.3):
        """
        Args:
            n_classes: Number of output classes (fall, walk, sit, idle)
            n_features: Number of PCA components / input channels
            n_freq: Number of frequency bins in spectrogram
            lstm_hidden: LSTM hidden size
            lstm_layers: Number of LSTM layers
            dropout: Dropout rate
        """
        super().__init__()

        self.n_features = n_features

        # CNN blocks: extract spatial features from spectrogram
        # MaxPool only along frequency axis (2,1) — time axis preserved for LSTM
        self.cnn = nn.Sequential(
            # Block 1
            nn.Conv2d(n_features, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d((2, 1)),

            # Block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d((2, 1)),

            # Block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d((2, 1)),
        )

        # Calculate CNN output size dynamically
        self._cnn_out_freq = n_freq // 8  # 3 MaxPool2d(2) layers
        if self._cnn_out_freq < 1:
            self._cnn_out_freq = 1

        # LSTM: track temporal sequence
        self.lstm = nn.LSTM(
            input_size=128 * self._cnn_out_freq,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if lstm_layers > 1 else 0,
        )

        # Classifier
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(lstm_hidden * 2, 64),  # *2 for bidirectional
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, n_classes),
        )

    def forward(self, x):
        """
        Args:
            x: (batch, n_features, n_freq, n_time) spectrogram tensor
        Returns:
            (batch, n_classes) logits
        """
        batch_size = x.size(0)

        # CNN: extract features
        # x shape: (batch, channels, freq, time)
        cnn_out = self.cnn(x)
        # cnn_out shape: (batch, 128, freq//8, time//8)

        # Reshape for LSTM: treat time as sequence
        # (batch, 128, freq_reduced, time_reduced) → (batch, time_reduced, 128*freq_reduced)
        cnn_out = cnn_out.permute(0, 3, 1, 2)  # (batch, time, channels, freq)
        cnn_out = cnn_out.reshape(batch_size, cnn_out.size(1), -1)  # (batch, time, features)

        # LSTM: temporal modeling
        lstm_out, _ = self.lstm(cnn_out)
        # Use the last time step output
        last_output = lstm_out[:, -1, :]

        # Classify
        logits = self.classifier(last_output)
        return logits


# Class labels
CLASSES = ['fall', 'walk', 'sit', 'idle']


def get_model(n_freq: int = 33, n_features: int = 10, n_classes: int = 4) -> CSIFallDetector:
    """Create a model with default hyperparameters."""
    model = CSIFallDetector(
        n_classes=n_classes,
        n_features=n_features,
        n_freq=n_freq,
    )
    total_params = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[model] Parameters: {total_params:,} total, {trainable:,} trainable")
    return model
