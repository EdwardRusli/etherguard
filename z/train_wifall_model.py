#!/usr/bin/env python3
"""
Training Script for WiFi CSI Fall Detection Model
Using WiFall Dataset from HuggingFace

This script trains the fall detection model on the preprocessed WiFall dataset.
Supports both standard and lightweight model architectures optimized for Jetson Nano.

Usage:
    python train_wifall_model.py --data ./data/wifall --model-type lightweight
    python train_wifall_model.py --data ./data/wifall --epochs 50 --batch-size 64
"""

import os
import sys
import argparse
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from torch.utils.tensorboard import SummaryWriter
import json
from datetime import datetime
from pathlib import Path
import logging
from tqdm import tqdm
from typing import Tuple, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WiFallDataset(Dataset):
    """
    PyTorch Dataset for preprocessed WiFall CSI data.
    
    Loads CSI windows and labels from numpy files created by load_wifall_dataset.py.
    """
    
    def __init__(
        self,
        data_dir: str,
        split: str = 'train',
        transform=None,
        augment: bool = False
    ):
        """
        Initialize WiFall dataset.
        
        Args:
            data_dir: Directory containing processed data
            split: 'train', 'val', or 'test'
            transform: Optional transforms to apply
            augment: Whether to apply data augmentation
        """
        self.data_dir = Path(data_dir)
        self.split = split
        self.transform = transform
        self.augment = augment and (split == 'train')  # Only augment training data
        
        # Load data
        csi_path = self.data_dir / f'{split}_csi.npy'
        labels_path = self.data_dir / f'{split}_labels.npy'
        
        if not csi_path.exists() or not labels_path.exists():
            raise FileNotFoundError(
                f"Data files not found. Run load_wifall_dataset.py first.\n"
                f"Expected: {csi_path}, {labels_path}"
            )
        
        self.csi_data = np.load(csi_path)
        self.labels = np.load(labels_path)
        
        # Load metadata
        metadata_path = self.data_dir / 'metadata.json'
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
        
        logger.info(f"Loaded {split} dataset: {len(self.csi_data)} samples")
        logger.info(f"CSI shape: {self.csi_data.shape}")
        logger.info(f"Labels shape: {self.labels.shape}")
        
        # Get unique classes
        self.num_classes = len(np.unique(self.labels))
        logger.info(f"Number of classes: {self.num_classes}")
        
        # Normalize data
        self._normalize_data()
    
    def _normalize_data(self):
        """Normalize CSI data to zero mean and unit variance"""
        # Compute statistics on training data
        if self.split == 'train':
            self.mean = np.mean(self.csi_data, axis=(0, 1), keepdims=True)
            self.std = np.std(self.csi_data, axis=(0, 1), keepdims=True) + 1e-8
        else:
            # Use training statistics for val/test
            train_csi = np.load(self.data_dir / 'train_csi.npy')
            self.mean = np.mean(train_csi, axis=(0, 1), keepdims=True)
            self.std = np.std(train_csi, axis=(0, 1), keepdims=True) + 1e-8
        
        self.csi_data = (self.csi_data - self.mean) / self.std
    
    def __len__(self) -> int:
        return len(self.csi_data)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        csi = self.csi_data[idx].astype(np.float32)
        label = int(self.labels[idx])
        
        # Apply augmentation
        if self.augment:
            csi = self._augment(csi)
        
        # Convert to tensor
        # Shape: (window_size, num_subcarriers)
        # Add channel dimension for CNN: (1, window_size, num_subcarriers)
        csi_tensor = torch.from_numpy(csi).unsqueeze(0).float()
        
        return csi_tensor, label
    
    def _augment(self, csi: np.ndarray) -> np.ndarray:
        """Apply data augmentation to CSI sample"""
        # Random noise injection
        if np.random.random() < 0.3:
            noise = np.random.normal(0, 0.05, csi.shape)
            csi = csi + noise
        
        # Random scaling
        if np.random.random() < 0.3:
            scale = np.random.uniform(0.9, 1.1)
            csi = csi * scale
        
        # Random time shift
        if np.random.random() < 0.2:
            shift = np.random.randint(-5, 5)
            csi = np.roll(csi, shift, axis=0)
        
        return csi


class CSICNN(nn.Module):
    """1D CNN for CSI feature extraction"""
    
    def __init__(self, num_filters: int = 32, dropout_rate: float = 0.3):
        super(CSICNN, self).__init__()
        
        self.conv1 = nn.Sequential(
            nn.Conv1d(1, num_filters, kernel_size=7, padding=3),
            nn.BatchNorm1d(num_filters),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Dropout(dropout_rate)
        )
        
        self.conv2 = nn.Sequential(
            nn.Conv1d(num_filters, num_filters * 2, kernel_size=5, padding=2),
            nn.BatchNorm1d(num_filters * 2),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Dropout(dropout_rate)
        )
        
        self.conv3 = nn.Sequential(
            nn.Conv1d(num_filters * 2, num_filters * 4, kernel_size=3, padding=1),
            nn.BatchNorm1d(num_filters * 4),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(8)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, 1, window_size, subcarriers)
        # Flatten subcarriers into features
        batch_size = x.size(0)
        x = x.view(batch_size, 1, -1)  # (batch, 1, window_size * subcarriers)
        
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        
        x = x.view(batch_size, -1)
        return x


class FallDetectionModel(nn.Module):
    """Fall detection model using CNN + Attention"""
    
    def __init__(
        self,
        input_dim: int,
        num_classes: int = 4,
        hidden_dim: int = 128,
        dropout_rate: float = 0.4
    ):
        super(FallDetectionModel, self).__init__()
        
        self.cnn = CSICNN(num_filters=32, dropout_rate=dropout_rate)
        
        # Calculate CNN output dimension (approximate)
        self.cnn_output_dim = 32 * 4 * 8  # num_filters * 4 * adaptive_pool
        
        self.classifier = nn.Sequential(
            nn.Linear(self.cnn_output_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout_rate),
            nn.Linear(hidden_dim // 2, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.cnn(x)
        logits = self.classifier(features)
        return logits


class LightweightFallModel(nn.Module):
    """Lightweight model optimized for edge deployment"""
    
    def __init__(self, input_dim: int, num_classes: int = 4):
        super(LightweightFallModel, self).__init__()
        
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=5, padding=2),
            nn.BatchNorm1d(16),
            nn.ReLU6(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(16, 32, kernel_size=3, padding=1),
            nn.BatchNorm1d(32),
            nn.ReLU6(),
            nn.MaxPool1d(2),
            
            nn.Conv1d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU6(),
            nn.AdaptiveAvgPool1d(4)
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(64 * 4, 64),
            nn.ReLU6(),
            nn.Dropout(0.3),
            nn.Linear(64, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size = x.size(0)
        x = x.view(batch_size, 1, -1)
        x = self.features(x)
        x = x.view(batch_size, -1)
        x = self.classifier(x)
        return x


def train_epoch(
    model: nn.Module,
    train_loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: str
) -> Tuple[float, float]:
    """Train for one epoch"""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    
    pbar = tqdm(train_loader, desc='Training')
    for batch_idx, (data, labels) in enumerate(pbar):
        data, labels = data.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(data)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item()
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()
        
        pbar.set_postfix({
            'loss': f'{loss.item():.4f}',
            'acc': f'{100.*correct/total:.2f}%'
        })
    
    avg_loss = total_loss / len(train_loader)
    accuracy = correct / total
    return avg_loss, accuracy


def validate(
    model: nn.Module,
    val_loader: DataLoader,
    criterion: nn.Module,
    device: str
) -> Tuple[float, float, Dict[str, float]]:
    """Validate the model"""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    
    # Per-class accuracy
    class_correct = {}
    class_total = {}
    
    with torch.no_grad():
        for data, labels in val_loader:
            data, labels = data.to(device), labels.to(device)
            
            outputs = model(data)
            loss = criterion(outputs, labels)
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
            
            # Per-class stats
            for label, pred in zip(labels, predicted):
                label_idx = label.item()
                if label_idx not in class_total:
                    class_total[label_idx] = 0
                    class_correct[label_idx] = 0
                class_total[label_idx] += 1
                if label.item() == pred.item():
                    class_correct[label_idx] += 1
    
    avg_loss = total_loss / len(val_loader)
    accuracy = correct / total
    
    # Calculate per-class accuracy
    per_class_acc = {}
    for cls in class_total:
        per_class_acc[f'class_{cls}'] = class_correct[cls] / class_total[cls]
    
    return avg_loss, accuracy, per_class_acc


def main():
    parser = argparse.ArgumentParser(description='Train fall detection model on WiFall dataset')
    parser.add_argument('--data', type=str, default='./data/wifall',
                        help='Path to processed WiFall data')
    parser.add_argument('--output', type=str, default='./output',
                        help='Output directory for model and logs')
    parser.add_argument('--model-type', type=str, default='lightweight',
                        choices=['standard', 'lightweight'],
                        help='Model architecture')
    parser.add_argument('--epochs', type=int, default=100,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Batch size for training')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='Learning rate')
    parser.add_argument('--weight-decay', type=float, default=1e-4,
                        help='Weight decay for optimizer')
    parser.add_argument('--patience', type=int, default=15,
                        help='Early stopping patience')
    parser.add_argument('--device', type=str, default='auto',
                        choices=['auto', 'cuda', 'cpu'],
                        help='Device to use for training')
    parser.add_argument('--augment', action='store_true',
                        help='Use data augmentation')
    args = parser.parse_args()
    
    # Set device
    if args.device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = args.device
    
    logger.info(f"Using device: {device}")
    
    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(args.output) / f'train_{timestamp}'
    output_dir.mkdir(parents=True, exist_ok=True)
    weights_dir = output_dir / 'weights'
    weights_dir.mkdir(exist_ok=True)
    
    # Load datasets
    logger.info("Loading datasets...")
    train_dataset = WiFallDataset(args.data, 'train', augment=args.augment)
    val_dataset = WiFallDataset(args.data, 'val')
    test_dataset = WiFallDataset(args.data, 'test')
    
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size,
        shuffle=True, num_workers=0, pin_memory=(device == 'cuda')
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size,
        shuffle=False, num_workers=0, pin_memory=(device == 'cuda')
    )
    test_loader = DataLoader(
        test_dataset, batch_size=args.batch_size,
        shuffle=False, num_workers=0, pin_memory=(device == 'cuda')
    )
    
    # Calculate input dimension
    sample_csi, _ = train_dataset[0]
    input_dim = sample_csi.numel()
    num_classes = train_dataset.num_classes
    
    logger.info(f"Input dimension: {input_dim}")
    logger.info(f"Number of classes: {num_classes}")
    
    # Create model
    logger.info(f"Creating {args.model_type} model...")
    if args.model_type == 'lightweight':
        model = LightweightFallModel(input_dim, num_classes)
    else:
        model = FallDetectionModel(input_dim, num_classes)
    
    model = model.to(device)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Total parameters: {total_params:,}")
    logger.info(f"Trainable parameters: {trainable_params:,}")
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='max', factor=0.5, patience=5
    )
    
    # TensorBoard writer
    writer = SummaryWriter(output_dir / 'logs')
    
    # Training loop
    best_val_acc = 0.0
    patience_counter = 0
    history = {
        'train_loss': [], 'train_acc': [],
        'val_loss': [], 'val_acc': [],
        'lr': []
    }
    
    logger.info("Starting training...")
    
    for epoch in range(args.epochs):
        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device
        )
        
        # Validate
        val_loss, val_acc, per_class_acc = validate(
            model, val_loader, criterion, device
        )
        
        # Update scheduler
        scheduler.step(val_acc)
        current_lr = optimizer.param_groups[0]['lr']
        
        # Record history
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['lr'].append(current_lr)
        
        # TensorBoard logging
        writer.add_scalar('Loss/train', train_loss, epoch)
        writer.add_scalar('Loss/val', val_loss, epoch)
        writer.add_scalar('Accuracy/train', train_acc, epoch)
        writer.add_scalar('Accuracy/val', val_acc, epoch)
        writer.add_scalar('Learning_Rate', current_lr, epoch)
        
        for cls, acc in per_class_acc.items():
            writer.add_scalar(f'PerClassAcc/{cls}', acc, epoch)
        
        # Print progress
        logger.info(
            f"Epoch {epoch+1}/{args.epochs} - "
            f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}, "
            f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}"
        )
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), weights_dir / 'best_model.pt')
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_acc': val_acc,
                'train_acc': train_acc,
                'per_class_acc': per_class_acc
            }, weights_dir / 'best_model_checkpoint.pt')
            logger.info(f"  → Saved best model with val_acc: {val_acc:.4f}")
            patience_counter = 0
        else:
            patience_counter += 1
        
        # Early stopping
        if patience_counter >= args.patience:
            logger.info(f"Early stopping at epoch {epoch+1}")
            break
    
    writer.close()
    
    # Save training history
    with open(output_dir / 'training_history.json', 'w') as f:
        json.dump(history, f, indent=2)
    
    # Load best model and test
    logger.info("\nEvaluating on test set...")
    model.load_state_dict(torch.load(weights_dir / 'best_model.pt'))
    test_loss, test_acc, test_per_class = validate(
        model, test_loader, criterion, device
    )
    
    logger.info(f"Test Accuracy: {test_acc:.4f}")
    logger.info(f"Per-class accuracy: {test_per_class}")
    
    # Save final results
    results = {
        'best_val_acc': best_val_acc,
        'test_acc': test_acc,
        'test_per_class_acc': test_per_class,
        'total_params': total_params,
        'model_type': args.model_type,
        'epochs_trained': len(history['train_loss']),
        'final_lr': history['lr'][-1] if history['lr'] else args.lr
    }
    
    with open(output_dir / 'results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save model config for deployment
    model_config = {
        'model_type': args.model_type,
        'input_dim': input_dim,
        'num_classes': num_classes,
        'window_size': train_dataset.metadata.get('window_size', 100),
        'activity_map': train_dataset.metadata.get('activity_map', {})
    }
    
    with open(weights_dir / 'model_config.json', 'w') as f:
        json.dump(model_config, f, indent=2)
    
    logger.info(f"\n✅ Training complete!")
    logger.info(f"   Output directory: {output_dir}")
    logger.info(f"   Best validation accuracy: {best_val_acc:.4f}")
    logger.info(f"   Test accuracy: {test_acc:.4f}")
    
    return 0


if __name__ == "__main__":
    exit(main())
