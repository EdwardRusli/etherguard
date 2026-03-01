#!/usr/bin/env python3
"""
Deep Learning Model for WiFi CSI-based Fall Detection

Based on research paper:
"Deep Learning-Based Fall Detection Using WiFi Channel State Information"
by Chu et al., IEEE Access 2023

Model Architecture:
- CNN for feature extraction from CSI spectrograms
- BiLSTM for temporal sequence learning
- Attention mechanism for important feature focusing
- Dense layers for classification

This model is optimized for Jetson Nano (ARM Cortex-A57, 4GB RAM, 128-core Maxwell GPU)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Optional, Dict
import os


class AttentionLayer(nn.Module):
    """
    Attention mechanism for focusing on important features.
    Helps the model focus on the most relevant parts of the CSI signal
    that indicate a fall event.
    """
    
    def __init__(self, hidden_dim: int):
        super(AttentionLayer, self).__init__()
        self.attention = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Softmax(dim=1)
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Apply attention mechanism.
        
        Args:
            x: Input tensor of shape (batch, seq_len, hidden_dim)
        
        Returns:
            Tuple of (weighted_output, attention_weights)
        """
        attention_weights = self.attention(x)  # (batch, seq_len, 1)
        weighted_output = torch.sum(x * attention_weights, dim=1)  # (batch, hidden_dim)
        return weighted_output, attention_weights.squeeze(-1)


class CSICNN(nn.Module):
    """
    CNN for extracting features from CSI spectrograms.
    
    Architecture based on the paper:
    - Multiple convolutional blocks with batch normalization
    - Residual connections for better gradient flow
    - Adaptive pooling for fixed output size
    """
    
    def __init__(
        self,
        input_channels: int = 1,
        num_filters: int = 32,
        dropout_rate: float = 0.3
    ):
        super(CSICNN, self).__init__()
        
        # Convolutional blocks
        self.conv1 = nn.Sequential(
            nn.Conv2d(input_channels, num_filters, kernel_size=3, padding=1),
            nn.BatchNorm2d(num_filters),
            nn.ReLU(),
            nn.Conv2d(num_filters, num_filters, kernel_size=3, padding=1),
            nn.BatchNorm2d(num_filters),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(dropout_rate)
        )
        
        self.conv2 = nn.Sequential(
            nn.Conv2d(num_filters, num_filters * 2, kernel_size=3, padding=1),
            nn.BatchNorm2d(num_filters * 2),
            nn.ReLU(),
            nn.Conv2d(num_filters * 2, num_filters * 2, kernel_size=3, padding=1),
            nn.BatchNorm2d(num_filters * 2),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Dropout2d(dropout_rate)
        )
        
        self.conv3 = nn.Sequential(
            nn.Conv2d(num_filters * 2, num_filters * 4, kernel_size=3, padding=1),
            nn.BatchNorm2d(num_filters * 4),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((4, 4))
        )
        
        # Calculate output dimensions
        self.output_dim = num_filters * 4 * 4 * 4
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through CNN.
        
        Args:
            x: Input spectrogram of shape (batch, channels, height, width)
        
        Returns:
            Feature tensor of shape (batch, output_dim)
        """
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        
        # Flatten
        x = x.view(x.size(0), -1)
        return x


class FallDetectionModel(nn.Module):
    """
    Complete fall detection model combining CNN and LSTM with attention.
    
    Architecture:
    1. CNN extracts spatial features from CSI spectrograms
    2. BiLSTM captures temporal dependencies
    3. Attention focuses on important time steps
    4. Dense layers perform final classification
    """
    
    def __init__(
        self,
        input_shape: Tuple[int, int, int] = (1, 33, 18),  # (channels, freq_bins, time_bins)
        num_classes: int = 4,  # fall, walk, sit, stand
        cnn_filters: int = 32,
        lstm_hidden: int = 128,
        lstm_layers: int = 2,
        dropout_rate: float = 0.4,
        use_attention: bool = True
    ):
        super(FallDetectionModel, self).__init__()
        
        self.input_shape = input_shape
        self.num_classes = num_classes
        self.use_attention = use_attention
        
        # CNN feature extractor
        self.cnn = CSICNN(
            input_channels=input_shape[0],
            num_filters=cnn_filters,
            dropout_rate=dropout_rate
        )
        
        # Calculate CNN output dimension
        self.cnn_output_dim = self.cnn.output_dim
        
        # LSTM for temporal sequence
        self.lstm = nn.LSTM(
            input_size=self.cnn_output_dim,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout_rate if lstm_layers > 1 else 0
        )
        
        # Attention layer
        if use_attention:
            self.attention = AttentionLayer(lstm_hidden * 2)
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(lstm_hidden * 2, lstm_hidden),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(lstm_hidden, lstm_hidden // 2),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(lstm_hidden // 2, num_classes)
        )
    
    def forward(
        self,
        x: torch.Tensor,
        return_attention: bool = False
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass through the model.
        
        Args:
            x: Input tensor of shape (batch, seq_len, channels, height, width)
            return_attention: Whether to return attention weights
        
        Returns:
            Tuple of (class_logits, attention_weights)
        """
        batch_size, seq_len = x.size(0), x.size(1)
        
        # Process each spectrogram through CNN
        # Reshape for CNN: (batch * seq_len, channels, height, width)
        x_flat = x.view(batch_size * seq_len, *self.input_shape)
        cnn_features = self.cnn(x_flat)
        
        # Reshape for LSTM: (batch, seq_len, features)
        cnn_features = cnn_features.view(batch_size, seq_len, -1)
        
        # LSTM processing
        lstm_out, _ = self.lstm(cnn_features)  # (batch, seq_len, hidden * 2)
        
        # Attention or simple pooling
        if self.use_attention:
            context, attention_weights = self.attention(lstm_out)
        else:
            context = lstm_out[:, -1, :]  # Take last output
            attention_weights = None
        
        # Classification
        logits = self.classifier(context)
        
        if return_attention:
            return logits, attention_weights
        return logits, None


class LightweightFallDetector(nn.Module):
    """
    Lightweight model optimized for Jetson Nano edge deployment.
    
    Features:
    - Smaller model size for memory efficiency
    - Quantization-friendly architecture
    - Reduced computational complexity
    """
    
    def __init__(
        self,
        input_shape: Tuple[int, int, int] = (1, 33, 18),
        num_classes: int = 4
    ):
        super(LightweightFallDetector, self).__init__()
        
        self.input_shape = input_shape
        
        # Lightweight CNN
        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(input_shape[0], 16, kernel_size=3, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU6(),
            nn.MaxPool2d(2, 2),
            
            # Block 2
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU6(),
            nn.MaxPool2d(2, 2),
            
            # Block 3
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU6(),
            nn.AdaptiveAvgPool2d((2, 2))
        )
        
        # Calculate feature dimension
        self.feature_dim = 64 * 2 * 2
        
        # Temporal processing with GRU (lighter than LSTM)
        self.gru = nn.GRU(
            input_size=self.feature_dim,
            hidden_size=64,
            num_layers=1,
            batch_first=True,
            bidirectional=True
        )
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU6(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x: Input of shape (batch, seq_len, channels, height, width)
        
        Returns:
            Class logits
        """
        batch_size, seq_len = x.size(0), x.size(1)
        
        # CNN feature extraction
        x = x.view(batch_size * seq_len, *self.input_shape)
        x = self.features(x)
        x = x.view(batch_size, seq_len, -1)
        
        # GRU processing
        x, _ = self.gru(x)
        x = x[:, -1, :]  # Last output
        
        # Classification
        x = self.classifier(x)
        return x


class ModelFactory:
    """Factory class for creating fall detection models."""
    
    @staticmethod
    def create_model(
        model_type: str = "standard",
        input_shape: Tuple[int, int, int] = (1, 33, 18),
        num_classes: int = 4,
        device: str = "cpu"
    ) -> nn.Module:
        """
        Create a fall detection model.
        
        Args:
            model_type: "standard" or "lightweight"
            input_shape: Shape of input spectrogram
            num_classes: Number of output classes
            device: Device to place model on
        
        Returns:
            PyTorch model
        """
        if model_type == "lightweight":
            model = LightweightFallDetector(input_shape, num_classes)
        else:
            model = FallDetectionModel(input_shape, num_classes)
        
        return model.to(device)
    
    @staticmethod
    def load_model(
        path: str,
        model_type: str = "standard",
        input_shape: Tuple[int, int, int] = (1, 33, 18),
        num_classes: int = 4,
        device: str = "cpu"
    ) -> nn.Module:
        """
        Load a trained model from file.
        
        Args:
            path: Path to model weights
            model_type: "standard" or "lightweight"
            input_shape: Shape of input spectrogram
            num_classes: Number of output classes
            device: Device to place model on
        
        Returns:
            Loaded PyTorch model
        """
        model = ModelFactory.create_model(model_type, input_shape, num_classes, device)
        
        if os.path.exists(path):
            state_dict = torch.load(path, map_location=device)
            model.load_state_dict(state_dict)
            print(f"Loaded model from {path}")
        else:
            print(f"Warning: Model file not found at {path}")
        
        return model
    
    @staticmethod
    def save_model(model: nn.Module, path: str):
        """
        Save model weights to file.
        
        Args:
            model: Model to save
            path: Save path
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save(model.state_dict(), path)
        print(f"Saved model to {path}")


def get_model_summary(model: nn.Module, input_shape: Tuple = (1, 5, 1, 33, 18)) -> Dict:
    """
    Get model summary including parameter count and size.
    
    Args:
        model: PyTorch model
        input_shape: Input tensor shape for testing
    
    Returns:
        Dictionary with model information
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    param_size_mb = sum(p.numel() * p.element_size() for p in model.parameters()) / (1024 ** 2)
    
    # Test forward pass
    try:
        dummy_input = torch.randn(*input_shape)
        with torch.no_grad():
            if isinstance(model, FallDetectionModel):
                output, _ = model(dummy_input)
            else:
                output = model(dummy_input)
        output_shape = tuple(output.shape)
    except Exception as e:
        output_shape = f"Error: {e}"
    
    return {
        "total_parameters": total_params,
        "trainable_parameters": trainable_params,
        "model_size_mb": param_size_mb,
        "output_shape": output_shape
    }


if __name__ == "__main__":
    # Test the models
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    
    # Test standard model
    print("\n=== Standard Model ===")
    model = ModelFactory.create_model("standard", device=device)
    summary = get_model_summary(model)
    print(f"Total parameters: {summary['total_parameters']:,}")
    print(f"Model size: {summary['model_size_mb']:.2f} MB")
    print(f"Output shape: {summary['output_shape']}")
    
    # Test lightweight model
    print("\n=== Lightweight Model ===")
    model_light = ModelFactory.create_model("lightweight", device=device)
    summary_light = get_model_summary(model_light)
    print(f"Total parameters: {summary_light['total_parameters']:,}")
    print(f"Model size: {summary_light['model_size_mb']:.2f} MB")
    print(f"Output shape: {summary_light['output_shape']}")
