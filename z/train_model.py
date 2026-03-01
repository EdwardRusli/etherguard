#!/usr/bin/env python3
"""
Training Script for WiFi CSI Fall Detection Model

This script trains the fall detection model using CSI datasets.
Supports multiple datasets including:
- IEEE DataPort CSI Human Activity Dataset
- ludlows/CSI-Activity-Recognition Dataset
- Custom collected CSI data
"""

import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from torch.utils.tensorboard import SummaryWriter
import json
import argparse
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CSIDataset(Dataset):
    """
    PyTorch Dataset for CSI fall detection data.
    
    Expected data format:
    - npz files containing 'csi_amplitude', 'csi_phase', and 'labels'
    - Or a directory with subdirectories for each activity class
    """
    
    ACTIVITY_MAP = {
        'fall': 0,
        'walk': 1,
        'sit': 2,
        'stand': 3,
        'bed': 0,  # Some datasets use 'bed' for fall-like activity
        'run': 1,
        'pickup': 3,
    }
    
    def __init__(
        self,
        data_path: str,
        window_size: int = 100,
        hop_size: int = 50,
        transform=None,
        balance_classes: bool = True
    ):
        """
        Initialize CSI dataset.
        
        Args:
            data_path: Path to dataset (npz file or directory)
            window_size: Number of CSI samples per window
            hop_size: Stride for sliding window
            transform: Optional transforms to apply
            balance_classes: Whether to balance class distribution
        """
        self.data_path = data_path
        self.window_size = window_size
        self.hop_size = hop_size
        self.transform = transform
        
        # Load data
        self.samples = []
        self.labels = []
        self._load_data()
        
        # Balance classes if requested
        if balance_classes:
            self._balance_classes()
        
        logger.info(f"Loaded {len(self.samples)} samples from {data_path}")
    
    def _load_data(self):
        """Load CSI data from file or directory"""
        if os.path.isfile(self.data_path):
            self._load_npz_file(self.data_path)
        elif os.path.isdir(self.data_path):
            self._load_directory(self.data_path)
        else:
            raise ValueError(f"Data path not found: {self.data_path}")
    
    def _load_npz_file(self, filepath: str):
        """Load data from NPZ file"""
        logger.info(f"Loading NPZ file: {filepath}")
        data = np.load(filepath, allow_pickle=True)
        
        # Get amplitude and phase data
        amplitude = data.get('csi_amplitude', data.get('amplitude', None))
        phase = data.get('csi_phase', data.get('phase', None))
        labels = data.get('labels', data.get('label', None))
        
        if amplitude is None or labels is None:
            raise ValueError("NPZ file must contain 'csi_amplitude' and 'labels'")
        
        # Ensure correct shape
        if len(amplitude.shape) == 2:
            amplitude = amplitude[np.newaxis, :, :]
            phase = phase[np.newaxis, :, :] if phase is not None else None
        
        # Process each recording
        for i in range(len(labels)):
            amp = amplitude[i] if len(amplitude.shape) == 3 else amplitude
            ph = phase[i] if phase is not None and len(phase.shape) == 3 else np.zeros_like(amp)
            
            # Create windows using sliding window
            num_windows = (len(amp) - self.window_size) // self.hop_size + 1
            
            for j in range(num_windows):
                start = j * self.hop_size
                end = start + self.window_size
                
                if end <= len(amp):
                    self.samples.append({
                        'amplitude': amp[start:end].astype(np.float32),
                        'phase': ph[start:end].astype(np.float32)
                    })
                    
                    # Map label to class index
                    label = labels[i] if isinstance(labels[i], (int, np.integer)) else labels[i]
                    if isinstance(label, str):
                        label = self.ACTIVITY_MAP.get(label.lower(), 0)
                    self.labels.append(int(label))
    
    def _load_directory(self, dirpath: str):
        """Load data from directory structure"""
        logger.info(f"Loading from directory: {dirpath}")
        
        for activity_name in os.listdir(dirpath):
            activity_dir = os.path.join(dirpath, activity_name)
            if not os.path.isdir(activity_dir):
                continue
            
            # Get class index
            class_idx = self.ACTIVITY_MAP.get(activity_name.lower(), -1)
            if class_idx == -1:
                logger.warning(f"Unknown activity class: {activity_name}")
                continue
            
            # Load all files in this class directory
            for filename in os.listdir(activity_dir):
                if filename.endswith('.npz'):
                    filepath = os.path.join(activity_dir, filename)
                    self._load_npz_file(filepath)
                elif filename.endswith('.csv'):
                    self._load_csv_file(os.path.join(activity_dir, filename), class_idx)
    
    def _load_csv_file(self, filepath: str, class_idx: int):
        """Load CSI data from CSV file"""
        import pandas as pd
        try:
            df = pd.read_csv(filepath)
            
            # Assuming columns are subcarriers
            amp_cols = [c for c in df.columns if 'amp' in c.lower() or 'amplitude' in c.lower()]
            if not amp_cols:
                amp_cols = df.columns[:64]  # Assume first 64 columns are CSI
            
            amplitude = df[amp_cols].values.astype(np.float32)
            phase = np.zeros_like(amplitude)
            
            # Create windows
            num_windows = (len(amplitude) - self.window_size) // self.hop_size + 1
            for j in range(num_windows):
                start = j * self.hop_size
                end = start + self.window_size
                if end <= len(amplitude):
                    self.samples.append({
                        'amplitude': amplitude[start:end],
                        'phase': phase[start:end]
                    })
                    self.labels.append(class_idx)
        except Exception as e:
            logger.error(f"Error loading CSV {filepath}: {e}")
    
    def _balance_classes(self):
        """Balance class distribution by oversampling minority classes"""
        from collections import Counter
        label_counts = Counter(self.labels)
        max_count = max(label_counts.values())
        
        balanced_samples = []
        balanced_labels = []
        
        for class_idx in label_counts:
            class_samples = [s for s, l in zip(self.samples, self.labels) if l == class_idx]
            class_labels = [l for l in self.labels if l == class_idx]
            
            # Oversample minority classes
            if len(class_samples) < max_count:
                indices = np.random.choice(
                    len(class_samples),
                    max_count - len(class_samples),
                    replace=True
                )
                class_samples.extend([class_samples[i] for i in indices])
                class_labels.extend([class_labels[i] for i in indices])
            
            balanced_samples.extend(class_samples)
            balanced_labels.extend(class_labels)
        
        self.samples = balanced_samples
        self.labels = balanced_labels
        
        logger.info(f"Balanced classes: {Counter(self.labels)}")
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int]:
        sample = self.samples[idx]
        label = self.labels[idx]
        
        # Convert to tensors
        amplitude = torch.from_numpy(sample['amplitude'])
        phase = torch.from_numpy(sample['phase'])
        
        # Apply transforms if any
        if self.transform:
            amplitude, phase = self.transform(amplitude, phase)
        
        # Stack amplitude and phase as channels
        # Shape: (2, window_size, num_subcarriers)
        x = torch.stack([amplitude, phase], dim=0)
        
        return x, label


class SpectrogramTransform:
    """Transform to convert CSI windows to spectrograms"""
    
    def __init__(self, sample_rate: float = 100.0, nperseg: int = 32, noverlap: int = 24):
        from scipy import signal
        self.sample_rate = sample_rate
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.signal = signal
    
    def __call__(self, amplitude: torch.Tensor, phase: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Convert to spectrogram"""
        # Average across subcarriers
        amp_avg = amplitude.mean(dim=1).numpy()
        
        # Generate spectrogram
        f, t, Sxx = self.signal.spectrogram(
            amp_avg,
            fs=self.sample_rate,
            nperseg=self.nperseg,
            noverlap=self.noverlap
        )
        
        # Convert to log scale and normalize
        Sxx = np.log10(Sxx + 1e-10)
        Sxx = (Sxx - Sxx.min()) / (Sxx.max() - Sxx.min() + 1e-10)
        
        return torch.from_numpy(Sxx).float(), torch.zeros(1)


def train_model(
    train_loader: DataLoader,
    val_loader: DataLoader,
    model: nn.Module,
    num_epochs: int,
    learning_rate: float,
    device: str,
    save_dir: str,
    patience: int = 10
) -> Dict:
    """
    Train the fall detection model.
    
    Args:
        train_loader: Training data loader
        val_loader: Validation data loader
        model: PyTorch model
        num_epochs: Number of training epochs
        learning_rate: Initial learning rate
        device: Device to train on
        save_dir: Directory to save model
        patience: Early stopping patience
    
    Returns:
        Training history dictionary
    """
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5, verbose=True
    )
    
    # TensorBoard writer
    writer = SummaryWriter(os.path.join(save_dir, 'logs'))
    
    # Training history
    history = {
        'train_loss': [],
        'train_acc': [],
        'val_loss': [],
        'val_acc': [],
        'learning_rate': []
    }
    
    best_val_acc = 0
    patience_counter = 0
    
    for epoch in range(num_epochs):
        # Training phase
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for batch_idx, (data, labels) in enumerate(train_loader):
            data, labels = data.to(device), labels.to(device)
            
            optimizer.zero_grad()
            
            # Forward pass
            outputs = model(data)
            if isinstance(outputs, tuple):
                outputs = outputs[0]
            
            loss = criterion(outputs, labels)
            
            # Backward pass
            loss.backward()
            optimizer.step()
            
            # Statistics
            train_loss += loss.item()
            _, predicted = outputs.max(1)
            train_total += labels.size(0)
            train_correct += predicted.eq(labels).sum().item()
        
        train_loss /= len(train_loader)
        train_acc = train_correct / train_total
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for data, labels in val_loader:
                data, labels = data.to(device), labels.to(device)
                
                outputs = model(data)
                if isinstance(outputs, tuple):
                    outputs = outputs[0]
                
                loss = criterion(outputs, labels)
                
                val_loss += loss.item()
                _, predicted = outputs.max(1)
                val_total += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()
        
        val_loss /= len(val_loader)
        val_acc = val_correct / val_total
        
        # Update learning rate
        scheduler.step(val_loss)
        current_lr = optimizer.param_groups[0]['lr']
        
        # Record history
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        history['learning_rate'].append(current_lr)
        
        # TensorBoard logging
        writer.add_scalar('Loss/train', train_loss, epoch)
        writer.add_scalar('Loss/val', val_loss, epoch)
        writer.add_scalar('Accuracy/train', train_acc, epoch)
        writer.add_scalar('Accuracy/val', val_acc, epoch)
        writer.add_scalar('Learning_Rate', current_lr, epoch)
        
        # Print progress
        logger.info(
            f"Epoch {epoch+1}/{num_epochs} - "
            f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}, "
            f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}"
        )
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), os.path.join(save_dir, 'best_model.pt'))
            logger.info(f"Saved best model with val_acc: {val_acc:.4f}")
            patience_counter = 0
        else:
            patience_counter += 1
        
        # Early stopping
        if patience_counter >= patience:
            logger.info(f"Early stopping at epoch {epoch+1}")
            break
    
    writer.close()
    
    # Save training history
    with open(os.path.join(save_dir, 'training_history.json'), 'w') as f:
        json.dump(history, f, indent=2)
    
    return history


def main():
    parser = argparse.ArgumentParser(description='Train CSI Fall Detection Model')
    parser.add_argument('--data', type=str, required=True, help='Path to dataset')
    parser.add_argument('--model-type', type=str, default='lightweight', 
                        choices=['standard', 'lightweight'])
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--window-size', type=int, default=100)
    parser.add_argument('--output', type=str, default='./output')
    parser.add_argument('--device', type=str, default='auto')
    args = parser.parse_args()
    
    # Set device
    if args.device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    else:
        device = args.device
    
    logger.info(f"Using device: {device}")
    
    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_dir = os.path.join(args.output, f'train_{timestamp}')
    os.makedirs(save_dir, exist_ok=True)
    
    # Load dataset
    dataset = CSIDataset(
        data_path=args.data,
        window_size=args.window_size,
        hop_size=args.window_size // 2
    )
    
    # Split dataset
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])
    
    # Create data loaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=4,
        pin_memory=True
    )
    
    # Create model
    model = ModelFactory.create_model(
        model_type=args.model_type,
        input_shape=(2, args.window_size, 64),
        num_classes=4,
        device=device
    )
    
    # Train model
    history = train_model(
        train_loader=train_loader,
        val_loader=val_loader,
        model=model,
        num_epochs=args.epochs,
        learning_rate=args.lr,
        device=device,
        save_dir=save_dir
    )
    
    logger.info(f"Training complete. Best val accuracy: {max(history['val_acc']):.4f}")
    logger.info(f"Model saved to: {save_dir}")


if __name__ == "__main__":
    main()
