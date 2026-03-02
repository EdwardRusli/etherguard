#!/usr/bin/env python3
"""
Train Fall Detection Model

Trains a room-specific model from collected calibration data.

Usage:
    python train_model.py --room living_room --epochs 50
    python train_model.py --room living_room --fine-tune --pretrained base_model.pt
"""

import sys
import os
import time
import argparse
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, Optional

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import ROOMS_DIR, MODELS_DIR, CSIConfig, TrainingConfig, ModelConfig
from models.model import create_model, count_parameters


class FallDetectionDataset(Dataset):
    """PyTorch Dataset for fall detection"""
    
    def __init__(
        self,
        room_dir: Path,
        split: str = "train",
        train_ratio: float = 0.8,
        augment: bool = False
    ):
        self.room_dir = Path(room_dir)
        self.augment = augment and (split == "train")
        
        # Load data
        self.windows = []
        self.labels = []
        
        for class_idx in range(4):
            filepath = self.room_dir / f"class_{class_idx}.npy"
            if filepath.exists():
                data = np.load(filepath)
                self.windows.extend(data)
                self.labels.extend([class_idx] * len(data))
        
        self.windows = np.array(self.windows, dtype=np.float32)
        self.labels = np.array(self.labels, dtype=np.int64)
        
        # Shuffle
        indices = np.random.permutation(len(self.windows))
        self.windows = self.windows[indices]
        self.labels = self.labels[indices]
        
        # Split
        n_train = int(len(self.windows) * train_ratio)
        if split == "train":
            self.windows = self.windows[:n_train]
            self.labels = self.labels[:n_train]
        else:
            self.windows = self.windows[n_train:]
            self.labels = self.labels[n_train:]
        
        # Normalize
        self._compute_normalization()
        
        print(f"  {split}: {len(self.windows)} samples")
        print(f"    Class distribution: {np.bincount(self.labels)}")
    
    def _compute_normalization(self):
        """Compute normalization statistics"""
        self.mean = self.windows.mean()
        self.std = self.windows.std() + 1e-8
    
    def __len__(self):
        return len(self.windows)
    
    def __getitem__(self, idx):
        window = self.windows[idx].copy()
        label = self.labels[idx]
        
        # Normalize
        window = (window - self.mean) / self.std
        
        # Augmentation
        if self.augment:
            window = self._augment(window)
        
        return torch.from_numpy(window), label
    
    def _augment(self, window: np.ndarray) -> np.ndarray:
        """Apply data augmentation"""
        # Random noise
        if np.random.random() < 0.3:
            noise = np.random.normal(0, 0.05, window.shape)
            window = window + noise
        
        # Random scaling
        if np.random.random() < 0.3:
            scale = np.random.uniform(0.9, 1.1)
            window = window * scale
        
        # Time shift
        if np.random.random() < 0.2:
            shift = np.random.randint(-5, 5)
            window = np.roll(window, shift, axis=0)
        
        return window


class Trainer:
    """Model trainer"""
    
    def __init__(
        self,
        room_name: str,
        model_type: str = "lightweight",
        device: str = "auto",
        training_config: TrainingConfig = None,
        model_config: ModelConfig = None
    ):
        self.room_name = room_name
        self.room_dir = ROOMS_DIR / room_name
        self.output_dir = MODELS_DIR / room_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Configs
        self.training_config = training_config or TrainingConfig()
        self.model_config = model_config or ModelConfig()
        
        # Device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        print(f"\nTraining Configuration:")
        print(f"  Device: {self.device}")
        print(f"  Model: {model_type}")
        print(f"  Epochs: {self.training_config.epochs}")
        print(f"  Batch size: {self.training_config.batch_size}")
        print(f"  Learning rate: {self.training_config.learning_rate}")
        
        # Create model
        self.model = create_model(
            model_type=model_type,
            num_classes=self.model_config.num_classes
        ).to(self.device)
        
        print(f"  Parameters: {count_parameters(self.model):,}")
        
        # Loss and optimizer
        self.criterion = nn.CrossEntropyLoss()
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.training_config.learning_rate,
            weight_decay=self.training_config.weight_decay
        )
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode='max', factor=0.5, patience=5
        )
        
        # Training state
        self.best_acc = 0.0
        self.patience_counter = 0
        self.history = {
            "train_loss": [],
            "train_acc": [],
            "val_loss": [],
            "val_acc": []
        }
    
    def load_data(self):
        """Load training and validation data"""
        print(f"\nLoading data from {self.room_dir}...")
        
        self.train_dataset = FallDetectionDataset(
            self.room_dir, split="train",
            augment=self.training_config.augmentation
        )
        self.val_dataset = FallDetectionDataset(
            self.room_dir, split="val",
            augment=False
        )
        
        self.train_loader = DataLoader(
            self.train_dataset,
            batch_size=self.training_config.batch_size,
            shuffle=True
        )
        self.val_loader = DataLoader(
            self.val_dataset,
            batch_size=self.training_config.batch_size
        )
    
    def train_epoch(self) -> Tuple[float, float]:
        """Train one epoch"""
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        
        for batch_idx, (data, labels) in enumerate(self.train_loader):
            data = data.to(self.device)
            labels = labels.to(self.device)
            
            self.optimizer.zero_grad()
            outputs = self.model(data)
            loss = self.criterion(outputs, labels)
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()
        
        avg_loss = total_loss / len(self.train_loader)
        accuracy = correct / total
        return avg_loss, accuracy
    
    def validate(self) -> Tuple[float, float, Dict]:
        """Validate model"""
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        class_correct = [0] * 4
        class_total = [0] * 4
        
        with torch.no_grad():
            for data, labels in self.val_loader:
                data = data.to(self.device)
                labels = labels.to(self.device)
                
                outputs = self.model(data)
                loss = self.criterion(outputs, labels)
                
                total_loss += loss.item()
                _, predicted = outputs.max(1)
                total += labels.size(0)
                correct += predicted.eq(labels).sum().item()
                
                # Per-class accuracy
                for label, pred in zip(labels, predicted):
                    class_total[label.item()] += 1
                    if label == pred:
                        class_correct[label.item()] += 1
        
        avg_loss = total_loss / len(self.val_loader)
        accuracy = correct / total
        
        per_class_acc = {
            i: class_correct[i] / max(class_total[i], 1)
            for i in range(4)
        }
        
        return avg_loss, accuracy, per_class_acc
    
    def train(self):
        """Full training loop"""
        print(f"\nStarting training...")
        
        for epoch in range(self.training_config.epochs):
            # Train
            train_loss, train_acc = self.train_epoch()
            
            # Validate
            val_loss, val_acc, per_class = self.validate()
            
            # Update scheduler
            self.scheduler.step(val_acc)
            
            # Record history
            self.history["train_loss"].append(train_loss)
            self.history["train_acc"].append(train_acc)
            self.history["val_loss"].append(val_loss)
            self.history["val_acc"].append(val_acc)
            
            # Print progress
            print(f"Epoch {epoch+1:3d}/{self.training_config.epochs}: "
                  f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.2%} | "
                  f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.2%}")
            
            # Save best model
            if val_acc > self.best_acc:
                self.best_acc = val_acc
                self.save_model("best_model.pt")
                print(f"  → New best model! Acc: {val_acc:.2%}")
                self.patience_counter = 0
            else:
                self.patience_counter += 1
            
            # Early stopping
            if self.patience_counter >= self.training_config.patience:
                print(f"\nEarly stopping at epoch {epoch+1}")
                break
        
        print(f"\nTraining complete!")
        print(f"Best validation accuracy: {self.best_acc:.2%}")
        
        # Save final model and history
        self.save_model("final_model.pt")
        self.save_history()
        
        return self.best_acc
    
    def save_model(self, filename: str):
        """Save model weights"""
        path = self.output_dir / filename
        torch.save(self.model.state_dict(), path)
    
    def save_history(self):
        """Save training history"""
        history_path = self.output_dir / "training_history.json"
        with open(history_path, "w") as f:
            json.dump(self.history, f, indent=2)
        
        # Save config
        config = {
            "room_name": self.room_name,
            "model_type": "lightweight",
            "window_size": 100,
            "subcarriers": 104,
            "num_classes": 4,
            "best_val_acc": self.best_acc,
            "timestamp": datetime.now().isoformat()
        }
        config_path = self.output_dir / "model_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    
    def load_pretrained(self, model_path: str):
        """Load pretrained weights for fine-tuning"""
        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        print(f"Loaded pretrained weights from {model_path}")


def main():
    parser = argparse.ArgumentParser(description="Train fall detection model")
    parser.add_argument("--room", type=str, required=True, help="Room name")
    parser.add_argument("--model-type", type=str, default="lightweight", help="Model architecture")
    parser.add_argument("--epochs", type=int, default=100, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--device", type=str, default="auto", help="Device (cpu/cuda/auto)")
    parser.add_argument("--fine-tune", action="store_true", help="Fine-tune from pretrained")
    parser.add_argument("--pretrained", type=str, default=None, help="Pretrained model path")
    parser.add_argument("--no-augment", action="store_true", help="Disable augmentation")
    args = parser.parse_args()
    
    # Create configs
    training_config = TrainingConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        augmentation=not args.no_augment
    )
    
    # Create trainer
    trainer = Trainer(
        room_name=args.room,
        model_type=args.model_type,
        device=args.device,
        training_config=training_config
    )
    
    # Load pretrained if fine-tuning
    if args.fine_tune and args.pretrained:
        trainer.load_pretrained(args.pretrained)
    
    # Load data and train
    trainer.load_data()
    best_acc = trainer.train()
    
    return 0 if best_acc > 0.7 else 1


if __name__ == "__main__":
    exit(main())
