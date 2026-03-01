"""
WiFall Dataset Loader — Download, preprocess, and convert WiFall CSI data
from HuggingFace into spectrograms for training.

WiFall zip structure:
    data/{person_name}/{action_name}/{file}.csv
    Each CSV: 60-second sample, columns include 'data' with 104 CSI values

Usage:
    cd jetson/model/

    # Download + preprocess + train in one step:
    python load_wifall.py --all --epochs 30

    # Or step by step:
    python load_wifall.py --download                    # download + extract
    python load_wifall.py --preprocess                  # convert to spectrograms
    python load_wifall.py --train --epochs 30           # train model
"""

import argparse
import csv
import os
import sys
import zipfile
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from preprocessing.filters import filter_csi
from preprocessing.pca import fit_pca
from preprocessing.spectrogram import process_csi_to_spectrograms


# WiFall action → our class mapping
ACTION_MAP = {
    'fall': 0,
    'jump': 1,   # active movement → walk
    'sit': 2,
    'stand': 3,  # standing still → idle
    'walk': 1,
}

CLASS_NAMES = ['fall', 'walk', 'sit', 'idle']

DATA_DIR = Path('../../data/wifall')
PROCESSED_DIR = Path('../../data/processed')


def download_wifall(data_dir: Path):
    """Download and extract WiFall dataset from HuggingFace."""
    print("\n=== Downloading WiFall Dataset ===")
    data_dir.mkdir(parents=True, exist_ok=True)

    zip_path = data_dir / 'WiFall.zip'

    # Download
    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id="RS2002/WiFall",
            repo_type="dataset",
            filename="WiFall.zip",
            local_dir=str(data_dir),
        )
        print(f"[download] Downloaded to {downloaded}")
    except ImportError:
        print("Install: pip install huggingface_hub")
        sys.exit(1)

    # Extract
    zip_path = data_dir / 'WiFall.zip'
    if zip_path.exists():
        print(f"[download] Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(data_dir)
        print(f"[download] Extracted to {data_dir}")

        # Show structure
        for root, dirs, files in os.walk(data_dir):
            depth = root.replace(str(data_dir), '').count(os.sep)
            if depth < 3:
                indent = '  ' * depth
                print(f"{indent}{os.path.basename(root)}/  ({len(files)} files)")
    else:
        print(f"[!] {zip_path} not found after download")


CSI_SUBCARRIER_INDEX = range(0, 52)


def parse_csi_complex(csi_list):
    """
    Parse CSI data using WiFall's format.
    From process1.py: real=x[i*2], imag=x[i*2-1]
    """
    real_parts = []
    imag_parts = []
    for i in CSI_SUBCARRIER_INDEX:
        real_parts.append(csi_list[i * 2])
        imag_parts.append(csi_list[i * 2 - 1])
    complex_csi = np.array(real_parts) + 1j * np.array(imag_parts)
    return np.abs(complex_csi)


def load_wifall_csv(csv_path: Path) -> np.ndarray:
    """
    Load a single WiFall CSV file and extract CSI amplitudes.
    Returns (n_samples, 52) amplitude array.
    """
    try:
        df = pd.read_csv(csv_path)
        df.dropna(inplace=True)

        if 'data' not in df.columns:
            print(f"    [!] No 'data' column in {csv_path.name}")
            return np.array([])

        amplitudes = []
        for _, row in df.iterrows():
            try:
                csi_list = eval(str(row['data']))
                if len(csi_list) >= 104:
                    amp = parse_csi_complex(csi_list)
                    amplitudes.append(amp)
            except Exception:
                continue

        if not amplitudes:
            return np.array([])

        return np.array(amplitudes)

    except Exception as e:
        print(f"    [!] Error reading {csv_path.name}: {e}")
        return np.array([])


def find_data_root(data_dir: Path) -> Path:
    """Find the actual root containing person directories."""
    # Could be data_dir/data/, data_dir/WiFall/data/, etc.
    candidates = [
        data_dir / 'data',
        data_dir / 'WiFall' / 'data',
        data_dir / 'WiFall',
        data_dir,
    ]

    for candidate in candidates:
        if not candidate.exists():
            continue
        subdirs = [d for d in candidate.iterdir() if d.is_dir()]
        # Check if subdirs contain action CSVs
        for sd in subdirs:
            csvs = list(sd.rglob('*.csv'))
            if csvs:
                print(f"[preprocess] Data root found: {candidate}")
                return candidate

    return data_dir


def preprocess_wifall(data_dir: Path, output_dir: Path,
                      fs: float = 100.0, window_sec: float = 2.0,
                      cutoff: float = 20.0, pca_components: int = 10):
    """Convert all WiFall CSVs into labeled spectrograms."""
    print("\n=== Preprocessing WiFall Dataset ===")
    output_dir.mkdir(parents=True, exist_ok=True)

    data_root = find_data_root(data_dir)

    all_spectrograms = []
    all_labels = []
    pca_model = None
    n_pca_out = None
    total_files = 0
    total_windows = 0

    # Walk the directory tree to find CSV files
    person_dirs = sorted([d for d in data_root.iterdir() if d.is_dir()])

    if not person_dirs:
        print(f"[!] No directories found in {data_root}")
        print(f"    Contents: {list(data_root.iterdir())}")
        return

    print(f"[preprocess] {len(person_dirs)} person directories in {data_root}")

    for person_dir in person_dirs:
        print(f"\n  Person: {person_dir.name}")

        # CSVs might be directly under person dir, or in action subdirs
        csv_files = list(person_dir.glob('*.csv'))
        action_dirs = [d for d in person_dir.iterdir() if d.is_dir()]

        if action_dirs:
            # Structure: person/action/file.csv
            for action_dir in sorted(action_dirs):
                action = action_dir.name.lower()
                if action not in ACTION_MAP:
                    print(f"    Skipping unknown action: {action}")
                    continue
                label = ACTION_MAP[action]
                for csv_file in sorted(action_dir.glob('*.csv')):
                    amp = load_wifall_csv(csv_file)
                    if len(amp) == 0:
                        continue
                    total_files += 1
                    specs, pca_model, n_pca_out = _process_one_file(
                        csv_file, amp, label, pca_model, n_pca_out, pca_components,
                        fs, cutoff, window_sec
                    )
                    if specs is not None and len(specs) > 0:
                        all_spectrograms.append(specs)
                        all_labels.append(np.full(len(specs), label, dtype=np.int64))
                        total_windows += len(specs)

        elif csv_files:
            # Structure: person/action.csv
            for csv_file in sorted(csv_files):
                action = csv_file.stem.lower()
                if action not in ACTION_MAP:
                    continue
                label = ACTION_MAP[action]
                amp = load_wifall_csv(csv_file)
                if len(amp) == 0:
                    continue
                total_files += 1
                specs, pca_model, n_pca_out = _process_one_file(
                    csv_file, amp, label, pca_model, n_pca_out, pca_components,
                    fs, cutoff, window_sec
                )
                if specs is not None and len(specs) > 0:
                    all_spectrograms.append(specs)
                    all_labels.append(np.full(len(specs), label, dtype=np.int64))
                    total_windows += len(specs)

    if not all_spectrograms:
        print("\n[!] No spectrograms generated.")
        print("    Check the directory structure:")
        for root, dirs, files in os.walk(data_root):
            depth = root.replace(str(data_root), '').count(os.sep)
            if depth < 3:
                indent = '  ' * depth
                csv_count = len([f for f in files if f.endswith('.csv')])
                if csv_count:
                    print(f"    {indent}{os.path.basename(root)}/  ({csv_count} CSVs)")
        return

    # Combine and shuffle
    spectrograms = np.concatenate(all_spectrograms, axis=0)
    labels = np.concatenate(all_labels, axis=0)

    perm = np.random.RandomState(42).permutation(len(labels))
    spectrograms = spectrograms[perm]
    labels = labels[perm]

    # Save
    np.save(output_dir / 'spectrograms.npy', spectrograms)
    np.save(output_dir / 'labels.npy', labels)

    # Save PCA model for inference pipeline
    if pca_model is not None:
        pca_path = output_dir / 'pca_model.pkl'
        joblib.dump({'pca': pca_model, 'n_components': n_pca_out}, pca_path)
        print(f"PCA model saved to {pca_path}")

    print(f"\n=== Dataset Ready ===")
    print(f"Files processed: {total_files}")
    print(f"Total windows: {len(labels)}, shape={spectrograms.shape}")
    for i, name in enumerate(CLASS_NAMES):
        count = (labels == i).sum()
        print(f"  {name}: {count} ({count/len(labels):.0%})")
    print(f"Saved to {output_dir}/")


def _process_one_file(csv_file, amplitude, label, pca_model, n_pca_out, pca_components,
                      fs, cutoff, window_sec):
    """Process a single CSV file through the pipeline. Returns (specs, pca_model, n_pca_out)."""
    print(f"    {csv_file.name}: {len(amplitude)} frames → {CLASS_NAMES[label]}", end='')

    # Filter
    filtered = filter_csi(amplitude, fs=fs, cutoff=cutoff)

    # PCA
    if pca_model is None:
        pca_model, reduced, _ = fit_pca(filtered, n_components=pca_components)
        n_pca_out = reduced.shape[1]
    else:
        from preprocessing.pca import apply_pca
        reduced = apply_pca(pca_model, filtered, n_components=n_pca_out)

    # Spectrograms
    specs = process_csi_to_spectrograms(reduced, fs=fs, window_sec=window_sec)

    if len(specs) > 0:
        print(f" → {len(specs)} windows")
    else:
        print(f" → too short")

    return specs, pca_model, n_pca_out


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

    if not spec_path.exists() or not label_path.exists():
        print(f"[!] Missing files in {output_dir}/. Run --preprocess first.")
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
    checkpoint = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    test_loss, test_acc = evaluate(
        model, test_loader, nn.CrossEntropyLoss(), device
    )
    print(f"Test Loss: {test_loss:.4f}, Test Accuracy: {test_acc:.1%}")


def main():
    parser = argparse.ArgumentParser(description='WiFall dataset pipeline')
    parser.add_argument('--download', action='store_true', help='Download + extract')
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
