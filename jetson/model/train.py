"""
Training Script — Train the CNN + Bi-LSTM fall detection model.

Usage:
    # Train on real data:
    python train.py --specs ../data/processed/spectrograms.npy --labels ../data/processed/labels.npy

    # Train on synthetic data (test the pipeline):
    python train.py --synthetic --epochs 20
"""

import argparse
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from pathlib import Path
from datetime import datetime

from architecture import CSIFallDetector, get_model, CLASSES
from dataset import (
    load_dataset, generate_synthetic_dataset, create_dataloaders
)


def train_one_epoch(model, loader, criterion, optimizer, device):
    """Train for one epoch. Returns average loss and accuracy."""
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for batch_x, batch_y in loader:
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)

        optimizer.zero_grad()
        outputs = model(batch_x)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * batch_x.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(batch_y).sum().item()
        total += batch_y.size(0)

    return total_loss / total, correct / total


def evaluate(model, loader, criterion, device):
    """Evaluate on val/test set. Returns loss, accuracy."""
    model.eval()
    total_loss = 0
    correct = 0
    total = 0

    with torch.no_grad():
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)

            total_loss += loss.item() * batch_x.size(0)
            _, predicted = outputs.max(1)
            correct += predicted.eq(batch_y).sum().item()
            total += batch_y.size(0)

    return total_loss / total, correct / total


def train(model, train_loader, val_loader, device, epochs=50,
          lr=1e-3, patience=10, save_dir='../data/models'):
    """Full training loop with early stopping."""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', patience=5, factor=0.5
    )

    best_val_loss = float('inf')
    patience_counter = 0
    best_model_path = save_dir / 'model_best.pth'

    print(f"\n{'Epoch':>6} | {'Train Loss':>10} | {'Train Acc':>9} | "
          f"{'Val Loss':>10} | {'Val Acc':>9} | {'LR':>8}")
    print("-" * 70)

    for epoch in range(1, epochs + 1):
        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device
        )
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)
        scheduler.step(val_loss)

        lr_now = optimizer.param_groups[0]['lr']
        print(f"{epoch:>6} | {train_loss:>10.4f} | {train_acc:>8.1%} | "
              f"{val_loss:>10.4f} | {val_acc:>8.1%} | {lr_now:>8.6f}")

        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_loss,
                'val_acc': val_acc,
                'classes': CLASSES,
            }, best_model_path)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\nEarly stopping at epoch {epoch} (no improvement for {patience} epochs)")
                break

    print(f"\nBest model saved to {best_model_path} (val_loss={best_val_loss:.4f})")
    return best_model_path


def main():
    parser = argparse.ArgumentParser(description='Train fall detection model')
    parser.add_argument('--specs', help='Path to spectrograms.npy')
    parser.add_argument('--labels', help='Path to labels.npy')
    parser.add_argument('--synthetic', action='store_true',
                        help='Use synthetic data for testing')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--patience', type=int, default=10)
    parser.add_argument('--save-dir', default='../data/models')
    args = parser.parse_args()

    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[train] Device: {device}")
    if device.type == 'cuda':
        print(f"[train] GPU: {torch.cuda.get_device_name(0)}")

    # Dataset
    if args.synthetic:
        print("[train] Using synthetic data")
        dataset = generate_synthetic_dataset(n_samples=400)
    elif args.specs and args.labels:
        dataset = load_dataset(args.specs, args.labels)
    else:
        print("Error: provide --specs and --labels, or use --synthetic")
        return

    train_loader, val_loader, test_loader = create_dataloaders(
        dataset, batch_size=args.batch_size
    )

    # Get spectrogram dimensions from data
    sample_x, _ = dataset[0]
    n_features, n_freq, n_time = sample_x.shape
    print(f"[train] Input shape: ({n_features}, {n_freq}, {n_time})")

    # Model
    model = get_model(n_freq=n_freq, n_features=n_features, n_classes=len(CLASSES))
    model = model.to(device)

    # Train
    best_path = train(
        model, train_loader, val_loader, device,
        epochs=args.epochs, lr=args.lr, patience=args.patience,
        save_dir=args.save_dir,
    )

    # Final evaluation on test set
    print("\n=== Test Set Evaluation ===")
    checkpoint = torch.load(best_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    test_loss, test_acc = evaluate(model, test_loader, nn.CrossEntropyLoss(), device)
    print(f"Test Loss: {test_loss:.4f}, Test Accuracy: {test_acc:.1%}")


if __name__ == '__main__':
    main()
