"""
Fall Detection Model Architecture

Lightweight CNN-based model optimized for edge deployment.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional


class LightweightFallDetector(nn.Module):
    """
    Lightweight 1D CNN for fall detection from CSI data.
    
    Input: CSI amplitude window of shape (batch, window_size, subcarriers)
    Output: Class logits of shape (batch, num_classes)
    """
    
    def __init__(
        self,
        input_dim: int = 10400,  # window_size * subcarriers = 100 * 104
        num_classes: int = 4,
        hidden_dim: int = 64
    ):
        super().__init__()
        
        self.input_dim = input_dim
        
        # Feature extraction
        self.features = nn.Sequential(
            # Conv block 1
            nn.Conv1d(1, 16, kernel_size=7, padding=3),
            nn.BatchNorm1d(16),
            nn.ReLU6(),
            nn.MaxPool1d(2),
            nn.Dropout(0.2),
            
            # Conv block 2
            nn.Conv1d(16, 32, kernel_size=5, padding=2),
            nn.BatchNorm1d(32),
            nn.ReLU6(),
            nn.MaxPool1d(2),
            nn.Dropout(0.2),
            
            # Conv block 3
            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU6(),
            nn.AdaptiveAvgPool1d(8),
        )
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 8, hidden_dim),
            nn.ReLU6(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, num_classes)
        )
        
        # Initialize weights
        self._initialize_weights()
    
    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                nn.init.zeros_(m.bias)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, window_size, subcarriers) or (batch, input_dim)
        batch_size = x.size(0)
        
        # Ensure float32
        x = x.float()
        
        # Flatten if needed
        if x.dim() == 3:
            x = x.view(batch_size, -1)
        
        # Add channel dimension
        x = x.unsqueeze(1)  # (batch, 1, input_dim)
        
        # Feature extraction
        x = self.features(x)
        
        # Classification
        x = self.classifier(x)
        
        return x
    
    def predict(self, x: torch.Tensor) -> Tuple[int, float, torch.Tensor]:
        """Get prediction with confidence"""
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probs = F.softmax(logits, dim=1)
            conf, pred = probs.max(dim=1)
            return pred.item(), conf.item(), probs.squeeze()


class FallDetectorWithAttention(nn.Module):
    """
    Enhanced model with attention mechanism for better temporal modeling.
    """
    
    def __init__(
        self,
        window_size: int = 100,
        subcarriers: int = 104,
        num_classes: int = 4,
        hidden_dim: int = 64
    ):
        super().__init__()
        
        self.window_size = window_size
        self.subcarriers = subcarriers
        
        # Per-timestep feature extraction
        self.feature_extractor = nn.Sequential(
            nn.Linear(subcarriers, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU()
        )
        
        # Attention
        self.attention = nn.Sequential(
            nn.Linear(32, 16),
            nn.Tanh(),
            nn.Linear(16, 1)
        )
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Linear(32, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, window_size, subcarriers)
        
        # Ensure float32
        x = x.float()
        
        # Extract features for each timestep
        x = self.feature_extractor(x)  # (batch, window_size, 32)
        
        # Compute attention weights
        attn_weights = self.attention(x)  # (batch, window_size, 1)
        attn_weights = F.softmax(attn_weights, dim=1)
        
        # Weighted sum
        x = (x * attn_weights).sum(dim=1)  # (batch, 32)
        
        # Classify
        x = self.classifier(x)
        
        return x


def create_model(
    model_type: str = "lightweight",
    window_size: int = 100,
    subcarriers: int = 104,
    num_classes: int = 4,
    device: str = "cpu"
) -> nn.Module:
    """Factory function to create model"""
    
    if model_type == "lightweight":
        model = LightweightFallDetector(
            input_dim=window_size * subcarriers,
            num_classes=num_classes
        )
    elif model_type == "attention":
        model = FallDetectorWithAttention(
            window_size=window_size,
            subcarriers=subcarriers,
            num_classes=num_classes
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    return model.to(device)


def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters"""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    # Test model
    model = create_model("lightweight")
    print(f"Model: {model.__class__.__name__}")
    print(f"Parameters: {count_parameters(model):,}")
    
    # Test forward pass
    x = torch.randn(1, 100, 104, dtype=torch.float64)  # Test with float64 input
    out = model(x)
    print(f"Input shape: {x.shape}")
    print(f"Input dtype: {x.dtype}")
    print(f"Output shape: {out.shape}")
    print(f"✓ Model correctly handles float64 input by converting to float32")
