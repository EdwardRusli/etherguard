#!/usr/bin/env python3
"""
WiFall Dataset Loader for ESP32 CSI Fall Detection

This script downloads and processes the WiFall dataset from HuggingFace.
Dataset: https://huggingface.co/datasets/RS2002/WiFall

The WiFall dataset was collected using ESP32 hardware, making it directly
compatible with the ESP32 + Jetson Nano fall detection system.

Usage:
    python load_wifall_dataset.py --output ./data/wifall
    python load_wifall_dataset.py --output ./data/wifall --visualize
"""

import os
import argparse
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CSIRecord:
    """Single CSI record from WiFall dataset"""
    type: str                    # Activity type (fall, walk, etc.)
    seq: int                     # Sequence number
    timestamp: str               # Timestamp
    target_seq: int              # Target sequence
    target: str                  # Target label
    mac: str                     # MAC address
    rssi: int                    # RSSI value
    rate: int                    # Data rate
    sig_mode: int                # Signal mode
    mcs: int                     # MCS index
    cwb: int                     # Channel bandwidth
    smoothing: int               # Smoothing flag
    not_sounding: int            # Not sounding flag
    aggregation: int             # Aggregation
    stbc: int                    # STBC
    fec_coding: int              # FEC coding
    sgi: int                     # Short GI
    noise_floor: int             # Noise floor
    ampdu_cnt: int               # AMPDU count
    channel_primary: int         # Primary channel
    channel_secondary: int       # Secondary channel
    local_timestamp: int         # Local timestamp
    ant: int                     # Antenna
    sig_len: int                 # Signal length
    rx_state: int                # RX state
    csi: np.ndarray              # CSI data array


class WiFallDataLoader:
    """
    Loader for the WiFall dataset from HuggingFace.
    
    The WiFall dataset contains WiFi CSI data collected using ESP32 for
    human fall detection. It includes activities like falls, walking,
    sitting, and standing.
    """
    
    # Activity label mapping
    ACTIVITY_MAP = {
        'fall': 0,
        'walk': 1,
        'sit': 2,
        'stand': 3,
        'bed': 0,      # Some datasets use 'bed' for fall-like
        'run': 1,
        'pickup': 3,
        'standup': 3,
        'sitdown': 2,
        'lyp': 0,      # Lying prone (fall-like)
        'lyb': 0,      # Lying back (fall-like)
        'empty': 4,    # Empty room (optional class)
        'falling': 0,  # Alternative naming
        'walking': 1,
        'sitting': 2,
        'standing': 3,
        'jump': 0,     # Jump - similar dynamics to fall
        'jumping': 0,
        # Numeric labels (some datasets use these)
        '0': 0,  # fall
        '1': 1,  # walk
        '2': 2,  # sit
        '3': 3,  # stand
    }
    
    def __init__(
        self,
        output_dir: str = "./data/wifall",
        window_size: int = 100,
        hop_size: int = 50,
        target_activities: Optional[List[str]] = None
    ):
        """
        Initialize WiFall data loader.
        
        Args:
            output_dir: Directory to save processed data
            window_size: Number of CSI samples per window
            hop_size: Stride for sliding window
            target_activities: List of activities to include (None = all)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.window_size = window_size
        self.hop_size = hop_size
        self.target_activities = target_activities
        
        # Data storage
        self.records: List[CSIRecord] = []
        self.windows: List[Dict] = []
        
        # Statistics
        self.stats = {
            'total_records': 0,
            'total_windows': 0,
            'activity_counts': {},
            'csi_shape': None
        }
    
    def download_dataset(self) -> bool:
        """
        Download WiFall dataset from HuggingFace.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            from datasets import load_dataset
            logger.info("Downloading WiFall dataset from HuggingFace...")
            
            # Load dataset
            dataset = load_dataset("RS2002/WiFall")
            logger.info(f"Dataset loaded with splits: {list(dataset.keys())}")
            
            # Process each split
            for split_name in dataset.keys():
                logger.info(f"Processing split: {split_name}")
                split_data = dataset[split_name]
                
                for idx, item in enumerate(split_data):
                    try:
                        # Debug first record to see structure
                        is_first = (idx == 0 and len(self.records) == 0)
                        record = self._parse_record(item, debug=is_first)
                        if record:
                            self.records.append(record)
                    except Exception as e:
                        logger.warning(f"Error parsing record {idx}: {e}")
                        continue
                    
                    if (idx + 1) % 1000 == 0:
                        logger.info(f"Processed {idx + 1} records...")
            
            self.stats['total_records'] = len(self.records)
            logger.info(f"Total records loaded: {len(self.records)}")
            return True
            
        except ImportError:
            logger.error("Please install the datasets library: pip install datasets")
            return False
        except Exception as e:
            logger.error(f"Error downloading dataset: {e}")
            return False
    
    def _parse_record(self, item: Dict, debug: bool = False) -> Optional[CSIRecord]:
        """
        Parse a single record from the dataset.
        
        Args:
            item: Raw record from HuggingFace dataset
            debug: If True, print debug info for first record
        
        Returns:
            CSIRecord object or None if invalid
        """
        try:
            # Debug: print available keys for first record
            if debug:
                logger.info(f"Dataset item keys: {list(item.keys())}")
                for key, value in item.items():
                    if key == 'data' or key == 'csi_data' or key == 'csi':
                        val_arr = np.array(value) if value else None
                        if isinstance(value, str):
                            # Parse string-encoded array
                            try:
                                parsed = json.loads(value)
                                logger.info(f"  {key}: string-encoded array, length={len(parsed)}")
                            except:
                                logger.info(f"  {key}: string (first 100 chars): {repr(value)[:100]}")
                        else:
                            logger.info(f"  {key} type: {type(value)}, shape: {val_arr.shape if val_arr is not None else 'None'}")
                    elif isinstance(value, (list, np.ndarray)):
                        logger.info(f"  {key}: array-like, length={len(value)}")
                    else:
                        logger.info(f"  {key}: {repr(value)[:100]}")  # Limit output
            
            # Extract CSI data - WiFall dataset uses 'data' field
            # Also try other common column names as fallback
            csi_data = item.get('data', item.get('csi_data', item.get('csi', None)))
            if csi_data is None:
                return None
            
            # Convert CSI to numpy array
            if isinstance(csi_data, str):
                # Handle string-encoded CSI data (WiFall format)
                csi_array = np.array(json.loads(csi_data), dtype=np.float32)
            elif isinstance(csi_data, list):
                csi_array = np.array(csi_data, dtype=np.float32)
            elif isinstance(csi_data, np.ndarray):
                csi_array = csi_data.astype(np.float32)
            else:
                csi_array = np.array(csi_data, dtype=np.float32)
            
            # Get activity type - WiFall dataset uses 'taget' field (misspelled 'target')
            # Note: The dataset has a typo where 'target' is spelled as 'taget'
            activity = None
            
            # Try WiFall-specific field name first (with typo)
            if 'taget' in item and item['taget'] is not None:
                val = item['taget']
                if not isinstance(val, (list, np.ndarray)):
                    val_str = str(val).lower().strip()
                    if val_str and val_str not in ['csi_data', 'csi', 'data', '']:
                        activity = val_str
            
            # Try other common field names as fallback
            if activity is None:
                for field in ['target', 'label', 'activity', 'type', 'class', 'action']:
                    if field in item and item[field] is not None:
                        val = item[field]
                        # Skip if the value looks like CSI data (array or 'csi_data' string)
                        if isinstance(val, (list, np.ndarray)):
                            continue
                        val_str = str(val).lower().strip()
                        # Skip if it's 'csi_data' or similar non-activity values
                        if val_str in ['csi_data', 'csi', 'data', 'unknown', '']:
                            continue
                        activity = val_str
                        break
            
            # If no activity found, try to infer from other fields
            if activity is None:
                # Check if there's a filename or path that contains activity info
                for field in ['file', 'filename', 'path', 'source']:
                    if field in item and item[field]:
                        fname = str(item[field]).lower()
                        for act in ['fall', 'walk', 'sit', 'stand', 'run', 'bed', 'jump']:
                            if act in fname:
                                activity = act
                                break
                        if activity:
                            break
            
            # Default to unknown if still not found
            if activity is None:
                activity = 'unknown'
            
            if debug:
                logger.info(f"  -> Detected activity: {activity}")
                logger.info(f"  -> CSI array shape: {csi_array.shape}")
            
            # Filter by target activities if specified
            if self.target_activities and activity not in self.target_activities:
                return None
            
            # Map to known activity or skip
            if activity not in self.ACTIVITY_MAP and activity not in ['fall', 'walk', 'sit', 'stand']:
                # Try fuzzy matching
                for key in self.ACTIVITY_MAP:
                    if key in activity or activity in key:
                        activity = key
                        break
            
            record = CSIRecord(
                type=activity,
                seq=item.get('seq', 0),
                timestamp=str(item.get('timestamp', '')),
                target_seq=item.get('target_seq', item.get('taget_seq', 0)),
                target=item.get('target', item.get('taget', '')),
                mac=str(item.get('mac', '')),
                rssi=item.get('rssi', 0),
                rate=item.get('rate', 0),
                sig_mode=item.get('sig_mode', 0),
                mcs=item.get('mcs', 0),
                cwb=item.get('cwb', 0),
                smoothing=item.get('smoothing', 0),
                not_sounding=item.get('not_sounding', 0),
                aggregation=item.get('aggregation', 0),
                stbc=item.get('stbc', 0),
                fec_coding=item.get('fec_coding', 0),
                sgi=item.get('sgi', 0),
                noise_floor=item.get('noise_floor', 0),
                ampdu_cnt=item.get('ampdu_cnt', 0),
                channel_primary=item.get('channel_primary', 0),
                channel_secondary=item.get('channel_secondary', 0),
                local_timestamp=item.get('local_timestamp', 0),
                ant=item.get('ant', 0),
                sig_len=item.get('sig_len', 0),
                rx_state=item.get('rx_state', 0),
                csi=csi_array
            )
            
            return record
            
        except Exception as e:
            logger.debug(f"Error parsing record: {e}")
            return None
    
    def create_windows(self):
        """
        Create sliding windows from CSI records for model training.
        
        This processes the CSI data into fixed-size windows suitable
        for the CNN-LSTM model.
        """
        logger.info("Creating sliding windows from CSI records...")
        
        # Log unique activities found
        unique_activities = set(r.type for r in self.records)
        logger.info(f"Unique activities found in records: {unique_activities}")
        
        # Group records by activity and sequence
        activity_sequences = {}
        skipped_activities = set()
        
        for record in self.records:
            activity = record.type
            
            # Check if activity is valid (in our map or starts with known prefix)
            is_valid = activity in self.ACTIVITY_MAP
            if not is_valid:
                # Try partial matching
                for key in self.ACTIVITY_MAP:
                    if key in activity or activity in key:
                        activity = key
                        is_valid = True
                        break
            
            if not is_valid:
                skipped_activities.add(activity)
                continue
                
            if activity not in activity_sequences:
                activity_sequences[activity] = []
            activity_sequences[activity].append(record)
        
        if skipped_activities:
            logger.warning(f"Skipped activities not in ACTIVITY_MAP: {skipped_activities}")
        
        logger.info(f"Grouped activities: {list(activity_sequences.keys())}")
        
        # Create windows for each activity
        for activity, records in activity_sequences.items():
            # Sort by sequence/timestamp
            records.sort(key=lambda r: (r.seq, r.local_timestamp))
            
            # Concatenate CSI data
            csi_arrays = [r.csi for r in records if r.csi is not None and len(r.csi) > 0]
            
            if not csi_arrays:
                continue
            
            # Stack into continuous array
            try:
                csi_matrix = np.vstack(csi_arrays)
            except ValueError:
                # Handle varying CSI lengths
                max_len = max(len(c) for c in csi_arrays)
                padded = []
                for csi in csi_arrays:
                    if len(csi) < max_len:
                        pad_width = max_len - len(csi)
                        csi = np.pad(csi, ((0, 0), (0, pad_width)), mode='constant')
                    padded.append(csi)
                csi_matrix = np.vstack(padded)
            
            # Create sliding windows
            num_windows = max(0, (len(csi_matrix) - self.window_size) // self.hop_size + 1)
            
            for i in range(num_windows):
                start = i * self.hop_size
                end = start + self.window_size
                
                if end <= len(csi_matrix):
                    window_data = csi_matrix[start:end]
                    
                    # Get label
                    label = self.ACTIVITY_MAP.get(activity, -1)
                    if label == -1:
                        continue
                    
                    self.windows.append({
                        'csi': window_data,
                        'label': label,
                        'activity': activity,
                        'window_idx': i
                    })
            
            # Update stats
            self.stats['activity_counts'][activity] = len(records)
        
        self.stats['total_windows'] = len(self.windows)
        self.stats['csi_shape'] = self.windows[0]['csi'].shape if self.windows else None
        
        logger.info(f"Created {len(self.windows)} windows")
        logger.info(f"Activity distribution: {self.stats['activity_counts']}")
        if self.stats['csi_shape']:
            logger.info(f"CSI shape: {self.stats['csi_shape']}")
    
    def balance_classes(self, strategy: str = 'oversample'):
        """
        Balance class distribution in windows.
        
        Args:
            strategy: 'oversample' (duplicate minority) or 'undersample' (reduce majority)
        """
        if not self.windows:
            logger.warning("No windows to balance")
            return
        
        # Count per class
        class_counts = {}
        for w in self.windows:
            label = w['label']
            class_counts[label] = class_counts.get(label, 0) + 1
        
        logger.info(f"Before balancing: {class_counts}")
        
        if strategy == 'oversample':
            # Oversample minority classes
            max_count = max(class_counts.values())
            balanced_windows = []
            
            for label in class_counts:
                class_windows = [w for w in self.windows if w['label'] == label]
                balanced_windows.extend(class_windows)
                
                # Oversample to match max count
                if len(class_windows) < max_count:
                    oversample_count = max_count - len(class_windows)
                    oversample_idx = np.random.choice(
                        len(class_windows),
                        oversample_count,
                        replace=True
                    )
                    for idx in oversample_idx:
                        balanced_windows.append(class_windows[idx].copy())
            
            self.windows = balanced_windows
            
        elif strategy == 'undersample':
            # Undersample majority classes
            min_count = min(class_counts.values())
            balanced_windows = []
            
            for label in class_counts:
                class_windows = [w for w in self.windows if w['label'] == label]
                undersample_idx = np.random.choice(
                    len(class_windows),
                    min_count,
                    replace=False
                )
                balanced_windows.extend([class_windows[i] for i in undersample_idx])
            
            self.windows = balanced_windows
        
        # Update stats
        class_counts = {}
        for w in self.windows:
            label = w['label']
            class_counts[label] = class_counts.get(label, 0) + 1
        
        logger.info(f"After balancing: {class_counts}")
    
    def split_data(
        self,
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        random_seed: int = 42
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Split data into train, validation, and test sets.
        
        Args:
            train_ratio: Ratio for training set
            val_ratio: Ratio for validation set
            test_ratio: Ratio for test set
            random_seed: Random seed for reproducibility
        
        Returns:
            Tuple of (train_windows, val_windows, test_windows)
        """
        np.random.seed(random_seed)
        
        # Shuffle windows
        indices = np.random.permutation(len(self.windows))
        shuffled = [self.windows[i] for i in indices]
        
        # Calculate split indices
        n_total = len(shuffled)
        n_train = int(n_total * train_ratio)
        n_val = int(n_total * val_ratio)
        
        train_windows = shuffled[:n_train]
        val_windows = shuffled[n_train:n_train + n_val]
        test_windows = shuffled[n_train + n_val:]
        
        logger.info(f"Split: train={len(train_windows)}, val={len(val_windows)}, test={len(test_windows)}")
        
        return train_windows, val_windows, test_windows
    
    def save_processed_data(
        self,
        train_windows: List[Dict],
        val_windows: List[Dict],
        test_windows: List[Dict]
    ):
        """
        Save processed data to numpy files for fast loading during training.
        
        Args:
            train_windows: Training windows
            val_windows: Validation windows
            test_windows: Test windows
        """
        logger.info("Saving processed data...")
        
        def save_split(windows: List[Dict], split_name: str):
            if not windows:
                return
            
            # Extract arrays
            csi_data = np.array([w['csi'] for w in windows])
            labels = np.array([w['label'] for w in windows])
            
            # Save to files
            np.save(self.output_dir / f'{split_name}_csi.npy', csi_data)
            np.save(self.output_dir / f'{split_name}_labels.npy', labels)
            
            logger.info(f"Saved {split_name}: CSI shape {csi_data.shape}, labels shape {labels.shape}")
        
        save_split(train_windows, 'train')
        save_split(val_windows, 'val')
        save_split(test_windows, 'test')
        
        # Save metadata
        metadata = {
            'window_size': self.window_size,
            'hop_size': self.hop_size,
            'activity_map': self.ACTIVITY_MAP,
            'stats': self.stats,
            'total_train': len(train_windows),
            'total_val': len(val_windows),
            'total_test': len(test_windows)
        }
        
        with open(self.output_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Data saved to {self.output_dir}")
    
    def visualize_samples(self, num_samples: int = 5):
        """
        Visualize sample CSI data for each activity class.
        
        Args:
            num_samples: Number of samples per activity to visualize
        """
        try:
            import matplotlib.pyplot as plt
            
            logger.info("Generating visualizations...")
            
            # Get unique activities
            activities = list(set(w['activity'] for w in self.windows))
            n_activities = len(activities)
            
            fig, axes = plt.subplots(n_activities, num_samples, 
                                     figsize=(3 * num_samples, 2.5 * n_activities))
            
            if n_activities == 1:
                axes = axes.reshape(1, -1)
            
            for act_idx, activity in enumerate(sorted(activities)):
                act_windows = [w for w in self.windows if w['activity'] == activity]
                samples = act_windows[:num_samples]
                
                for samp_idx, sample in enumerate(samples):
                    ax = axes[act_idx, samp_idx]
                    csi = sample['csi']
                    
                    # Plot CSI amplitude heatmap
                    im = ax.imshow(csi.T, aspect='auto', cmap='viridis')
                    ax.set_title(f'{activity} (#{samp_idx + 1})', fontsize=9)
                    ax.set_xlabel('Time Sample', fontsize=8)
                    ax.set_ylabel('Subcarrier', fontsize=8)
                    ax.tick_params(labelsize=7)
            
            plt.tight_layout()
            plt.savefig(self.output_dir / 'csi_samples.png', dpi=150)
            plt.close()
            
            logger.info(f"Saved visualization to {self.output_dir / 'csi_samples.png'}")
            
            # Also create activity distribution plot
            fig, ax = plt.subplots(figsize=(10, 5))
            activities = list(self.stats['activity_counts'].keys())
            counts = list(self.stats['activity_counts'].values())
            
            bars = ax.bar(activities, counts, color='steelblue')
            ax.set_xlabel('Activity', fontsize=12)
            ax.set_ylabel('Number of Records', fontsize=12)
            ax.set_title('WiFall Dataset Activity Distribution', fontsize=14)
            
            # Add count labels on bars
            for bar, count in zip(bars, counts):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                       str(count), ha='center', va='bottom', fontsize=10)
            
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            plt.savefig(self.output_dir / 'activity_distribution.png', dpi=150)
            plt.close()
            
            logger.info(f"Saved distribution plot to {self.output_dir / 'activity_distribution.png'}")
            
        except ImportError:
            logger.warning("matplotlib not installed, skipping visualization")
    
    def run_pipeline(self, visualize: bool = False) -> bool:
        """
        Run the complete data loading pipeline.
        
        Args:
            visualize: Whether to generate visualizations
        
        Returns:
            True if successful
        """
        # Download and load dataset
        if not self.download_dataset():
            return False
        
        # Create sliding windows
        self.create_windows()
        
        if not self.windows:
            logger.error("No windows created from dataset")
            return False
        
        # Balance classes
        self.balance_classes(strategy='oversample')
        
        # Split data
        train, val, test = self.split_data()
        
        # Save processed data
        self.save_processed_data(train, val, test)
        
        # Visualize if requested
        if visualize:
            self.visualize_samples()
        
        logger.info("Data loading pipeline complete!")
        return True


def main():
    parser = argparse.ArgumentParser(description='Load and process WiFall dataset')
    parser.add_argument('--output', type=str, default='./data/wifall',
                        help='Output directory for processed data')
    parser.add_argument('--window-size', type=int, default=100,
                        help='Window size for CSI data')
    parser.add_argument('--hop-size', type=int, default=50,
                        help='Hop size for sliding window')
    parser.add_argument('--visualize', action='store_true',
                        help='Generate visualizations')
    parser.add_argument('--activities', type=str, nargs='*',
                        help='Target activities to include (default: all)')
    args = parser.parse_args()
    
    # Create loader
    loader = WiFallDataLoader(
        output_dir=args.output,
        window_size=args.window_size,
        hop_size=args.hop_size,
        target_activities=args.activities
    )
    
    # Run pipeline
    success = loader.run_pipeline(visualize=args.visualize)
    
    if success:
        print(f"\n✅ Dataset processed successfully!")
        print(f"   Output directory: {args.output}")
        print(f"   Files created:")
        print(f"     - train_csi.npy, train_labels.npy")
        print(f"     - val_csi.npy, val_labels.npy")
        print(f"     - test_csi.npy, test_labels.npy")
        print(f"     - metadata.json")
    else:
        print("\n❌ Failed to process dataset")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
