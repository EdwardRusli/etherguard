"""
ONNX Export — Convert trained PyTorch model to ONNX for edge deployment.

Usage:
    python export_onnx.py --model ../data/models/model_best.pth \
                          --output ../data/models/etherguard.onnx
"""

import argparse
import torch
import numpy as np

from architecture import get_model, CLASSES


def export_to_onnx(model_path: str, output_path: str,
                   n_features: int = 10, n_freq: int = 33, n_time: int = 5):
    """Export a trained model to ONNX format."""
    device = torch.device('cpu')  # Export on CPU for compatibility

    # Load checkpoint
    checkpoint = torch.load(model_path, map_location=device)

    # Recreate model
    model = get_model(n_freq=n_freq, n_features=n_features, n_classes=len(CLASSES))
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    # Dummy input matching expected shape
    dummy_input = torch.randn(1, n_features, n_freq, n_time)

    # Export
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=11,
        do_constant_folding=True,
        input_names=['spectrogram'],
        output_names=['prediction'],
        dynamic_axes={
            'spectrogram': {0: 'batch_size'},
            'prediction': {0: 'batch_size'},
        },
    )

    # Verify
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)

    # File size
    import os
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n[export] Saved to {output_path} ({size_mb:.1f} MB)")
    print(f"[export] Input:  spectrogram ({n_features}, {n_freq}, {n_time})")
    print(f"[export] Output: prediction ({len(CLASSES)},) → {CLASSES}")


def main():
    parser = argparse.ArgumentParser(description='Export model to ONNX')
    parser.add_argument('--model', required=True, help='Path to model_best.pth')
    parser.add_argument('--output', default='../data/models/etherguard.onnx')
    parser.add_argument('--n-features', type=int, default=10)
    parser.add_argument('--n-freq', type=int, default=33)
    parser.add_argument('--n-time', type=int, default=5)
    args = parser.parse_args()

    export_to_onnx(
        args.model, args.output,
        n_features=args.n_features,
        n_freq=args.n_freq,
        n_time=args.n_time,
    )


if __name__ == '__main__':
    main()
