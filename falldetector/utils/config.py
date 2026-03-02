"""
Configuration for WiFi Fall Detector System
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List

# Base paths
BASE_DIR = Path(__file__).parent.parent.absolute()
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
ROOMS_DIR = DATA_DIR / "rooms"

# Ensure directories exist
for d in [DATA_DIR, MODELS_DIR, ROOMS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class SerialConfig:
    """Serial communication settings"""
    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200
    timeout: float = 1.0


@dataclass
class CSIConfig:
    """CSI data settings"""
    subcarriers: int = 104
    window_size: int = 100
    hop_size: int = 50
    

@dataclass
class ModelConfig:
    """Model architecture settings"""
    num_classes: int = 4
    hidden_dim: int = 128
    dropout: float = 0.3


@dataclass
class TrainingConfig:
    """Training hyperparameters"""
    epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    patience: int = 15
    augmentation: bool = True


@dataclass
class ActivityConfig:
    """Activity class configuration"""
    labels: Dict[int, str] = field(default_factory=lambda: {
        0: "fall",
        1: "walk", 
        2: "sit",
        3: "stand"
    })
    
    # Aliases that map to main classes
    aliases: Dict[str, int] = field(default_factory=lambda: {
        "falling": 0,
        "jump": 0,
        "jumping": 0,
        "walking": 1,
        "run": 1,
        "running": 1,
        "sitting": 2,
        "sitdown": 2,
        "standing": 3,
        "standup": 3,
    })
    
    def get_label(self, activity: str) -> int:
        """Convert activity string to class index"""
        activity = activity.lower().strip()
        # Check direct match
        for idx, name in self.labels.items():
            if name == activity:
                return idx
        # Check aliases
        return self.aliases.get(activity, -1)


# Calibration sequence for room setup
CALIBRATION_SEQUENCE = [
    ("fall", "Perform a FALL (safely onto soft surface)", 10, 15),
    ("walk", "WALK normally around the room", 10, 20),
    ("sit", "SIT down on a chair", 10, 15),
    ("stand", "STAND up from sitting position", 10, 15),
]

# Activity display names
ACTIVITY_DISPLAY = {
    0: "🚨 FALL",
    1: "🚶 WALK",
    2: "🪑 SIT",
    3: "🧍 STAND"
}
