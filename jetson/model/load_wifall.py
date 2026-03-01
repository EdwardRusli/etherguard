"""
WiFall Dataset Loader — Download, preprocess, and convert WiFall CSI data
from HuggingFace into spectrograms for training.

WiFall dataset structure:
    ID0/fall.csv, ID0/jump.csv, ID0/sit.csv, ID0/stand.csv, ID0/walk.csv
    ID1/fall.csv, ...
    Each CSV: 60 seconds at ~100Hz, 52 subcarriers (104 values)

Usage:
    cd jetson/model/

    # Download + preprocess + train in one step:
    python load_wifall.py --download --train --epochs 30

    # Or step by step:
    python load_wifall.py --download                    # download dataset
    python load_wifall.py --preprocess                  # convert to spectrograms
    python load_wifall.py --train --epochs 30           # train model
"""

import argparse
import csv
import json
import os
import sys
import numpy as np
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from preprocessing.filters import filter_csi
from preprocessing.pca import fit_pca
from preprocessing.spectrogram import process_csi_to_spectrograms


# WiFall action → our class mapping
# WiFall has: fall, jump, sit, stand, walk
# We map to: 0=fall, 1=walk, 2=sit, 3=idle
ACTION_MAP = {
    'fall': 0,
    'jump': 1,   # map jump → walk (both are active movement)
    'sit': 2,
    'stand': 3,  # map stand → idle
    'walk': 1,
}

CLASS_NAMES = ['fall', 'walk', 'sit', 'idle']

DATA_DIR = Path('../../data/wifall')
PROCESSED_DIR = Path('../../data/processed')


def download_wifall(data_dir: Path):
    """Download WiFall dataset from HuggingFace."""
    print("\n=== Downloading WiFall Dataset ===")
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="RS2002/WiFall",
            repo_type="dataset",
            local_dir=str(data_dir),
        )
        print(f"[download] Saved to {data_dir}")
    except ImportError:
        print("Install huggingface_hub: pip install huggingface_hub")
        print("Then run: huggingface-cli download RS2002/WiFall --repo-type dataset "
              f"--local-dir {data_dir}")
        sys.exit(1)


def load_wifall_csv(csv_path: Path) -> np.ndarray:
    """
    Load a single WiFall CSV file and extract CSI amplitudes.
    Returns (n_samples, 52) amplitude array.
    """
    amplitudes = []

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse the CSI data field
                csi_str = row.get('data', '')
                if not csi_str:
                    continue

                # Handle both plain list and JSON-formatted strings
                csi_str = csi_str.strip().strip('"').strip("'")
                if csi_str.startswith('['):
                    csi_raw = json.loads(csi_str)
                else:
                    csi_raw = [float(x) for x in csi_str.split(',')]

                if len(csi_raw) < 104:
                    continue

                # WiFall format: a[2i] + a[2i+1]j (real + imag*j)
                n_sub = len(csi_raw) // 2
                amplitude = np.zeros(n_sub)
                for i in range(n_sub):
                    real_part = csi_raw[2 * i]
                    imag_part = csi_raw[2 * i + 1]
                    amplitude[i] = np.sqrt(real_part**2 + imag_part**2)

                amplitudes.append(amplitude)
            except (ValueError, json.JSONDecodeError, KeyError):
                continue

    if not amplitudes:
        return np.array([])

    return np.array(amplitudes)


def preprocess_wifall(data_dir: Path, output_dir: Path,
                      fs: float = 100.0, window_sec: float = 2.0,
                      cutoff: float = 20.0, pca_components: int = 10):
    """Convert all WiFall CSVs into labeled spectrograms."""
    print("\n=== Preprocessing WiFall Dataset ===")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_spectrograms = []
    all_labels = []
    pca_model = None

    # Find all person directories
    person_dirs = sorted([d for d in data_dir.iterdir()
                         if d.is_dir() and d.name.startswith('ID')])

    if not person_dirs:
        # Try looking for CSV files directly or in subdirectories
        person_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])

    if not person_dirs:
        print(f"[!] No person directories found in {data_dir}")
        print(f"    Contents: {list(data_dir.iterdir())}")
        return

    print(f"[preprocess] Found {len(person_dirs)} person directories")

    for person_dir in person_dirs:
        csv_files = list(person_dir.glob('*.csv'))
        if not csv_files:
            continue

        print(f"\n  {person_dir.name}: {len(csv_files)} files")

        for csv_file in csv_files:
            action = csv_file.stem.lower()
            if action not in ACTION_MAP:
                print(f"    Skipping unknown action: {action}")
                continue

            label = ACTION_MAP[action]

            # Load CSI data
            amplitude = load_wifall_csv(csv_file)
            if len(amplitude) == 0:
                print(f"    {csv_file.name}: empty, skipping")
                continue

            print(f"    {csv_file.name}: {len(amplitude)} frames, "
                  f"{amplitude.shape[1]} subcarriers → class={CLASS_NAMES[label]}")

            # Filter
            filtered = filter_csi(amplitude, fs=fs, cutoff=cutoff)

            # PCA (fit on first file, apply to rest)
            if pca_model is None:
                pca_model, reduced, _ = fit_pca(filtered, n_components=pca_components)
            else:
                from preprocessing.pca import apply_pca
                reduced = apply_pca(pca_model, filtered, n_components=pca_components)

            # Spectrograms
            specs = process_csi_to_spectrograms(
                reduced, fs=fs, window_sec=window_sec
            )

            if len(specs) == 0:
                print(f"    → Not enough data for spectrograms")
                continue

            # Add labels for each window
            labels = np.full(len(specs), label, dtype=np.int64)
            all_spectrograms.append(specs)
            all_labels.append(labels)

            print(f"    → {len(specs)} spectrograms")

    if not all_spectrograms:
        print("[!] No spectrograms generated. Check data format.")
        return

    # Combine all
    spectrograms = np.concatenate(all_spectrograms, axis=0)
    labels = np.concatenate(all_labels, axis=0)

    # Shuffle
    perm = np.random.RandomState(42).permutation(len(labels))
    spectrograms = spectrograms[perm]
    labels = labels[perm]

    # Save
    np.save(output_dir / 'spectrograms.npy', spectrograms)
    np.save(output_dir / 'labels.npy', labels)

    # Print stats
    print(f"\n=== Dataset Ready ===")
    print(f"Total: {len(labels)} samples, shape={spectrograms.shape}")
    for i, name in enumerate(CLASS_NAMES):
        count = (labels == i).sum()
        print(f"  {name}: {count} ({count/len(labels):.0%})")
    print(f"Saved to {output_dir}/")


def train_on_wifall(output_dir: Path, epochs: int = 50,
                    batch_size: int = 32, lr: float = 1e-3):
    """Train the model on preprocessed WiFall data."""
    import torch
    from dataset import load_dataset, create_dataloaders
    from architecture import get_model, CLASSES
    from train import train, evaluate
    import torch.nn as nn

    print("\n=== Training on WiFall ===")

    spec_path = output_dir / 'spectrograms.npy'
    label_path = output_dir / 'labels.npy'

    if not spec_path.exists():
        print(f"[!] {spec_path} not found. Run --preprocess first.")
        return

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[train] Device: {device}")

    dataset = load_dataset(str(spec_path), str(label_path))
    train_loader, val_loader, test_loader = create_dataloaders(
        dataset, batch_size=batch_size
    )

    sample_x, _ = dataset[0]
    n_features, n_freq, n_time = sample_x.shape
    print(f"[train] Input: ({n_features}, {n_freq}, {n_time})")

    model = get_model(n_freq=n_freq, n_features=n_features, n_classes=len(CLASS_NAMES))
    model = model.to(device)

    best_path = train(
        model, train_loader, val_loader, device,
        epochs=epochs, lr=lr, save_dir=str(output_dir / 'models'),
    )

    # Final test evaluation
    print("\n=== Test Evaluation ===")
    checkpoint = torch.load(best_path, map_location=device)
    model.load_state_dict(checkpoint['model_state_dict'])
    test_loss, test_acc = evaluate(
        model, test_loader, nn.CrossEntropyLoss(), device
    )
    print(f"Test Loss: {test_loss:.4f}, Test Accuracy: {test_acc:.1%}")


def main():
    parser = argparse.ArgumentParser(description='WiFall dataset pipeline')
    parser.add_argument('--download', action='store_true', help='Download dataset')
    parser.add_argument('--preprocess', action='store_true', help='Preprocess to spectrograms')
    parser.add_argument('--train', action='store_true', help='Train model')
    parser.add_argument('--all', action='store_true', help='Download + preprocess + train')
    parser.add_argument('--data-dir', default=str(DATA_DIR))
    parser.add_argument('--output-dir', default=str(PROCESSED_DIR))
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--fs', type=float, default=100.0)
    parser.add_argument('--window-sec', type=float, default=2.0)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    if args.all:
        args.download = args.preprocess = args.train = True

    if args.download:
        download_wifall(data_dir)

    if args.preprocess:
        preprocess_wifall(data_dir, output_dir, fs=args.fs, window_sec=args.window_sec)

    if args.train:
        train_on_wifall(output_dir, epochs=args.epochs,
                        batch_size=args.batch_size, lr=args.lr)

    if not (args.download or args.preprocess or args.train):
        print("Specify --download, --preprocess, --train, or --all")


if __name__ == '__main__':
    main()
