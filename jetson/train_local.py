"""
EtherGuard — Local Training Script
====================================
Trains a binary fall-detector (fall / not_fall) from NPZ windows.

Features are automatically reduced to prevent overfitting on small datasets:
  - Subcarriers are binned into groups of 4 (64 → 16 bins)
  - 4 statistics per bin: mean, std, energy, range
  - Plus 4 global features
  - Total: 16×4 + 4 = 68 features (was 454 before)

Usage:
    python train_local.py
"""

import sys
import json
import time
import argparse
import numpy as np
import joblib
from pathlib import Path
from datetime import datetime
from scipy.signal import butter, filtfilt
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix

TRAINING_DIR = Path(__file__).parent.parent / 'data' / 'training'
MODEL_DIR    = Path(__file__).parent.parent / 'data' / 'models'
CLASSES      = ['not_fall', 'fall']

# Subcarrier binning: group N adjacent subcarriers into 1
BIN_SIZE     = 4   # 64 subs → 16 bins


def bandpass(data: np.ndarray, fs: float, lowcut=0.3, highcut=None, order=4):
    """Bandpass filter. highcut auto-set to 0.4 × Nyquist."""
    nyq = fs / 2.0
    if highcut is None:
        highcut = nyq * 0.8
    low  = max(lowcut / nyq, 0.01)
    high = min(highcut / nyq, 0.99)
    if low >= high:
        return data
    b, a = butter(order, [low, high], btype='band')
    return filtfilt(b, a, data, axis=0)


def bin_subcarriers(window: np.ndarray) -> np.ndarray:
    """(T, n_sub) → (T, n_bins) by averaging groups of BIN_SIZE."""
    T, n_sub = window.shape
    n_bins = n_sub // BIN_SIZE
    if n_bins == 0:
        return window
    trimmed = window[:, :n_bins * BIN_SIZE]
    return trimmed.reshape(T, n_bins, BIN_SIZE).mean(axis=2)


def estimate_fs(windows: np.ndarray) -> float:
    """Rough estimate of sampling rate from window size.
    We assume windows were collected with 2s target duration."""
    T = windows.shape[1]
    return T / 2.0   # 2-second windows assumed


def extract_features(window: np.ndarray, fs: float) -> np.ndarray:
    """window: (T, n_sub) → 1-D feature vector (compact)."""
    # 1. Filter
    try:
        filtered = bandpass(window, fs=fs)
    except Exception:
        filtered = window

    # 2. Bin subcarriers
    binned = bin_subcarriers(filtered)

    # 3. Per-bin statistics (4 stats × n_bins)
    mean   = binned.mean(axis=0)
    std    = binned.std(axis=0)
    energy = (binned ** 2).sum(axis=0)
    rng    = binned.max(axis=0) - binned.min(axis=0)

    # 4. Global features
    global_feats = np.array([
        mean.mean(), std.mean(), energy.sum(), rng.mean()
    ], dtype=np.float32)

    return np.concatenate([mean, std, energy, rng, global_feats]).astype(np.float32)


def load_dataset():
    npz_files = sorted(TRAINING_DIR.glob('*.npz'))
    if not npz_files:
        print(f"[ERROR] No NPZ files in {TRAINING_DIR}")
        print("        Run collect.py first.")
        sys.exit(1)

    X_all, y_all = [], []
    counts = {}
    fs_est = None

    for npz in npz_files:
        data    = np.load(npz, allow_pickle=True)
        windows = data['X']
        label   = str(data['label'])
        if label not in CLASSES:
            print(f"  [WARN] Unknown label '{label}' in {npz.name}, skipping")
            continue

        if fs_est is None:
            fs_est = estimate_fs(windows)

        idx   = CLASSES.index(label)
        feats = np.array([extract_features(w, fs=fs_est) for w in windows])
        X_all.append(feats)
        y_all.extend([idx] * len(windows))
        counts[label] = counts.get(label, 0) + len(windows)
        print(f"  {len(windows):4d} windows [{label:8s}] ← {npz.name}")

    if not X_all:
        print("[ERROR] No valid data.")
        sys.exit(1)

    X = np.vstack(X_all).astype(np.float32)
    y = np.array(y_all, dtype=np.int32)
    print(f"\n  Dataset: {X.shape[0]} samples × {X.shape[1]} features")
    print(f"  Estimated CSI rate: {fs_est:.0f} Hz")
    for l, c in counts.items():
        print(f"    {l:10s}: {c}")
    return X, y, fs_est


def main():
    ap = argparse.ArgumentParser(description='EtherGuard Training')
    ap.add_argument('--trees', type=int, default=150)
    ap.add_argument('--depth', type=int, default=10)
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--jobs',  type=int, default=-1)
    args = ap.parse_args()

    print("\n" + "=" * 60)
    print("  EtherGuard — Training Binary Fall Detector")
    print("=" * 60)

    print("\n[1/4] Loading & extracting features...")
    t0 = time.time()
    X, y, fs_est = load_dataset()
    print(f"      {time.time()-t0:.1f}s")

    if len(np.unique(y)) < 2:
        print("[ERROR] Need 2 classes. Collect both labels.")
        sys.exit(1)

    # Reduce folds if too few samples
    min_class = min(np.bincount(y))
    folds = min(args.folds, min_class)
    if folds < 2:
        print("[ERROR] Need at least 2 samples per class for CV.")
        sys.exit(1)

    print(f"\n[2/4] Scaling...")
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    print(f"\n[3/4] {folds}-fold CV...")
    clf = RandomForestClassifier(
        n_estimators=args.trees, max_depth=args.depth,
        min_samples_leaf=3, n_jobs=args.jobs,
        random_state=42, class_weight='balanced',
    )
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    scores = cross_val_score(clf, Xs, y, cv=cv, scoring='f1_weighted', n_jobs=1)
    print(f"  F1 scores: {scores.round(3)}")
    print(f"  Mean F1:   {scores.mean():.3f} ± {scores.std():.3f}")

    print("\n[4/4] Final training...")
    t1 = time.time()
    clf.fit(Xs, y)
    print(f"      {time.time()-t1:.1f}s")

    y_pred = clf.predict(Xs)
    print("\n  Train-set report:")
    print(classification_report(y, y_pred, target_names=CLASSES, digits=3))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path  = MODEL_DIR / 'rf_model.pkl'
    scaler_path = MODEL_DIR / 'scaler.pkl'
    meta_path   = MODEL_DIR / 'meta.json'

    joblib.dump(clf,    model_path)
    joblib.dump(scaler, scaler_path)

    n_feats = X.shape[1]
    n_bins  = (n_feats - 4) // 4

    meta = {
        'classes':       CLASSES,
        'n_subcarrier_bins': int(n_bins),
        'bin_size':       BIN_SIZE,
        'n_features':     int(n_feats),
        'trees':          args.trees,
        'max_depth':      args.depth,
        'cv_f1_mean':     float(scores.mean()),
        'cv_f1_std':      float(scores.std()),
        'train_samples':  int(len(y)),
        'trained_at':     datetime.now().isoformat(),
        'fs':             float(fs_est),
    }
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print("\n" + "=" * 60)
    print(f"  Model  → {model_path}")
    print(f"  Scaler → {scaler_path}")
    print(f"  Meta   → {meta_path}")
    print(f"  CV F1: {scores.mean():.3f}")
    if scores.mean() >= 0.70:
        print("  ✓ Model looks usable. Run: python detect.py")
    else:
        print("  ⚠ F1 < 0.70. Tips:")
        print("    - Collect more data (more rounds or longer rounds)")
        print("    - Make falls more distinct (bigger motion)")
        print("    - Keep 'not_fall' varied (sit, walk, stand)")
    print("=" * 60)


if __name__ == '__main__':
    main()
