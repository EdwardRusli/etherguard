"""
Visualize spectrograms from the preprocessing pipeline.

Usage:
    python visualize.py --input ../data/processed/spectrograms.npy
    python visualize.py --input ../data/processed/spectrograms.npy --window 5
"""

import argparse
import numpy as np
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description='Visualize CSI spectrograms')
    parser.add_argument('-i', '--input', required=True, help='Path to spectrograms.npy')
    parser.add_argument('-w', '--window', type=int, default=0,
                        help='Which window index to show (default: 0)')
    parser.add_argument('--all', action='store_true',
                        help='Show a grid of all windows (first feature only)')
    args = parser.parse_args()

    specs = np.load(args.input)
    print(f"Loaded: {specs.shape}")
    print(f"  {specs.shape[0]} windows, {specs.shape[1]} freq bins, "
          f"{specs.shape[2]} time steps, {specs.shape[3]} features")

    if args.all:
        # Grid view of all windows (first PCA component)
        n = specs.shape[0]
        cols = min(5, n)
        rows = (n + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(3 * cols, 3 * rows))
        if rows == 1:
            axes = [axes] if cols == 1 else axes
        else:
            axes = axes.flatten()

        for i in range(n):
            axes[i].imshow(specs[i, :, :, 0], aspect='auto', origin='lower', cmap='hot')
            axes[i].set_title(f'Window {i}', fontsize=9)
            axes[i].set_xlabel('Time')
            axes[i].set_ylabel('Freq')

        # Hide empty subplots
        for i in range(n, len(axes)):
            axes[i].axis('off')

        plt.suptitle('CSI Spectrograms — All Windows (Feature 0)', fontsize=13)
        plt.tight_layout()
        plt.savefig('spectrograms_grid.png', dpi=150)
        print("Saved: spectrograms_grid.png")
        plt.show()

    else:
        # Single window, show all features
        idx = args.window
        if idx >= specs.shape[0]:
            print(f"Window {idx} out of range (max: {specs.shape[0] - 1})")
            return

        n_feat = specs.shape[3]
        cols = min(4, n_feat)
        rows = (n_feat + cols - 1) // cols
        fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows))
        if n_feat == 1:
            axes = [axes]
        else:
            axes = np.atleast_1d(axes).flatten()

        for f in range(n_feat):
            axes[f].imshow(specs[idx, :, :, f], aspect='auto', origin='lower', cmap='hot')
            axes[f].set_title(f'PCA Component {f}', fontsize=9)
            axes[f].set_xlabel('Time')
            axes[f].set_ylabel('Freq')

        for f in range(n_feat, len(axes)):
            axes[f].axis('off')

        plt.suptitle(f'CSI Spectrogram — Window {idx}', fontsize=13)
        plt.tight_layout()
        plt.savefig(f'spectrogram_w{idx}.png', dpi=150)
        print(f"Saved: spectrogram_w{idx}.png")
        plt.show()


if __name__ == '__main__':
    main()
