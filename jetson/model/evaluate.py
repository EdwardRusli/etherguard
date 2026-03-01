"""
Evaluation — Detailed metrics, confusion matrix, and per-class analysis.

Usage:
    python evaluate.py --model ../data/models/model_best.pth \
                       --specs ../data/processed/spectrograms.npy \
                       --labels ../data/processed/labels.npy
"""

import argparse
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix

from architecture import CSIFallDetector, get_model, CLASSES
from dataset import load_dataset, generate_synthetic_dataset, create_dataloaders


def evaluate_model(model, test_loader, device):
    """Run inference on test set and collect all predictions."""
    model.eval()
    all_preds = []
    all_labels = []
    all_probs = []

    with torch.no_grad():
        for batch_x, batch_y in test_loader:
            batch_x = batch_x.to(device)
            outputs = model(batch_x)
            probs = torch.softmax(outputs, dim=1)
            _, predicted = outputs.max(1)

            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(batch_y.numpy())
            all_probs.extend(probs.cpu().numpy())

    return np.array(all_preds), np.array(all_labels), np.array(all_probs)


def print_report(preds, labels, class_names):
    """Print classification report and confusion matrix."""
    print("\n=== Classification Report ===")
    print(classification_report(labels, preds, target_names=class_names, digits=3))

    print("=== Confusion Matrix ===")
    cm = confusion_matrix(labels, preds)
    # Header
    print(f"{'':>10}", end='')
    for name in class_names:
        print(f"{name:>8}", end='')
    print(f"{'recall':>10}")
    print("-" * (10 + 8 * len(class_names) + 10))

    for i, name in enumerate(class_names):
        print(f"{name:>10}", end='')
        for j in range(len(class_names)):
            print(f"{cm[i, j]:>8}", end='')
        # Row recall
        row_sum = cm[i].sum()
        recall = cm[i, i] / row_sum if row_sum > 0 else 0
        print(f"{recall:>9.1%}")

    # Overall accuracy
    acc = np.trace(cm) / cm.sum()
    print(f"\nOverall Accuracy: {acc:.1%}")

    # Fall-specific metrics
    fall_idx = class_names.index('fall') if 'fall' in class_names else 0
    fall_tp = cm[fall_idx, fall_idx]
    fall_fn = cm[fall_idx].sum() - fall_tp
    fall_fp = cm[:, fall_idx].sum() - fall_tp
    fall_recall = fall_tp / (fall_tp + fall_fn) if (fall_tp + fall_fn) > 0 else 0
    fall_precision = fall_tp / (fall_tp + fall_fp) if (fall_tp + fall_fp) > 0 else 0
    fpr = fall_fp / (cm.sum() - cm[fall_idx].sum()) if cm.sum() > cm[fall_idx].sum() else 0

    print(f"\n=== Fall Detection Metrics ===")
    print(f"Fall Recall:        {fall_recall:.1%}  (target: ≥95%)")
    print(f"Fall Precision:     {fall_precision:.1%}")
    print(f"False Positive Rate: {fpr:.1%}  (target: <5%)")


def main():
    parser = argparse.ArgumentParser(description='Evaluate fall detection model')
    parser.add_argument('--model', required=True, help='Path to model_best.pth')
    parser.add_argument('--specs', help='Path to spectrograms.npy')
    parser.add_argument('--labels', help='Path to labels.npy')
    parser.add_argument('--synthetic', action='store_true')
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Load data
    if args.synthetic:
        dataset = generate_synthetic_dataset(n_samples=400)
    else:
        dataset = load_dataset(args.specs, args.labels)

    _, _, test_loader = create_dataloaders(dataset, batch_size=args.batch_size)

    # Get dimensions
    sample_x, _ = dataset[0]
    n_features, n_freq, n_time = sample_x.shape

    # Load model
    model = get_model(n_freq=n_freq, n_features=n_features, n_classes=len(CLASSES))
    checkpoint = torch.load(args.model, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)

    print(f"Loaded model from epoch {checkpoint['epoch']} "
          f"(val_acc={checkpoint.get('val_acc', 'N/A')})")

    # Evaluate
    preds, labels, probs = evaluate_model(model, test_loader, device)
    print_report(preds, labels, CLASSES)


if __name__ == '__main__':
    main()
