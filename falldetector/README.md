# WiFi CSI Fall Detector

A room-calibratable fall detection system using WiFi Channel State Information (CSI).

## Overview

This system uses WiFi CSI data collected from an ESP32 to detect falls in real-time. It features:

- **Room-specific calibration** - Train models for each room/environment
- **Real-time detection** - Live fall detection with confidence scores
- **Easy setup** - Guided calibration process

## Architecture

```
┌─────────────┐      USB Serial       ┌──────────────┐
│   ESP32     │ ───────────────────►  │  Jetson/PC   │
│ (CSI Collector)│   CSI Packets      │  (Detection) │
└─────────────┘     115200 baud       └──────────────┘
```

## Quick Start

### 1. Flash ESP32 Firmware

```bash
# Open Arduino IDE and flash:
esp32-firmware/csi_collector.ino

# Update WiFi credentials in the firmware:
const char* ROUTER_SSID = "YOUR_WIFI_SSID";
const char* ROUTER_PASSWORD = "YOUR_WIFI_PASSWORD";
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Calibrate a Room

```bash
# Connect ESP32 and run calibration
python wifi_fall_detector.py calibrate --room living_room --port /dev/ttyUSB0

# Follow prompts to collect data for:
# - Falls (onto soft surface)
# - Walking
# - Sitting
# - Standing
```

### 4. Train Model

```bash
# Train a room-specific model
python wifi_fall_detector.py train --room living_room --epochs 50
```

### 5. Run Detection

```bash
# Start real-time detection
python wifi_fall_detector.py detect --room living_room --port /dev/ttyUSB0
```

## Project Structure

```
wifi-fall-detector/
├── esp32-firmware/
│   └── csi_collector.ino      # ESP32 firmware
├── calibration/
│   ├── collect_data.py        # Data collection
│   └── train_model.py         # Model training
├── detection/
│   └── detect.py              # Real-time detection
├── models/
│   └── model.py               # Model architecture
├── utils/
│   ├── config.py              # Configuration
│   ├── serial_reader.py       # Serial communication
│   └── room_manager.py        # Room management
├── data/
│   └── rooms/                 # Room data storage
│       └── living_room/
│           ├── class_0.npy    # Fall data
│           ├── class_1.npy    # Walk data
│           ├── class_2.npy    # Sit data
│           ├── class_3.npy    # Stand data
│           └── metadata.json
├── models/
│   └── living_room/           # Trained models
│       ├── best_model.pt
│       └── model_config.json
├── wifi_fall_detector.py      # Main entry point
└── requirements.txt
```

## Commands

### Calibrate

Collect calibration data for a room:

```bash
python wifi_fall_detector.py calibrate --room <room_name> --port <serial_port>

Options:
  --room       Room name/identifier (required)
  --port       Serial port (default: /dev/ttyUSB0)
  --baud       Baud rate (default: 115200)
  --append     Add to existing data
```

### Train

Train a model for a room:

```bash
python wifi_fall_detector.py train --room <room_name>

Options:
  --room       Room name (required)
  --epochs     Training epochs (default: 100)
  --batch-size Batch size (default: 32)
  --device     Device: cpu/cuda/auto (default: auto)
  --no-augment Disable data augmentation
```

### Detect

Run real-time detection:

```bash
python wifi_fall_detector.py detect --room <room_name> --port <serial_port>

Options:
  --room       Room name (required)
  --port       Serial port (default: /dev/ttyUSB0)
  --model      Custom model path
  --threshold  Fall detection threshold (default: 0.5)
```

### List Rooms

View all configured rooms:

```bash
python wifi_fall_detector.py list
```

## How It Works

### CSI Data Flow

1. **ESP32** receives WiFi packets from router
2. **CSI extraction** captures channel state (amplitude + phase)
3. **Serial transmission** sends 104-value packets to PC
4. **Windowing** collects 100 packets for each prediction
5. **CNN inference** classifies activity (fall/walk/sit/stand)

### Why Room Calibration?

WiFi CSI is **environment-dependent**:
- Room size affects multipath patterns
- Furniture changes signal reflections
- Router position changes signal geometry

Each room has unique CSI characteristics, so models are trained **per-room** for best accuracy.

### Calibration Process

For each activity (fall, walk, sit, stand):
1. User performs ~10 repetitions
2. System collects 100+ CSI windows
3. Data saved for training

Total calibration time: **~5-10 minutes**

## Hardware Requirements

- **ESP32** (NodeMCU, TTGO, or similar)
- **WiFi Router** (any standard router)
- **PC/Jetson Nano** for inference
- **USB cable** for ESP32 connection

## Troubleshooting

### No data from ESP32

1. Check ESP32 is connected and powered
2. Verify correct serial port: `ls /dev/ttyUSB*`
3. Check permissions: `sudo chmod 666 /dev/ttyUSB0`
4. Ensure WiFi credentials are correct in firmware

### Poor detection accuracy

1. Collect more calibration data
2. Ensure ESP32 position is consistent
3. Perform actions naturally during calibration
4. Retrain with more epochs

### Connection errors

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in
```

## Model Details

- **Architecture**: 1D CNN with 3 conv layers
- **Input**: 100 x 104 (window x subcarriers)
- **Output**: 4 classes (fall, walk, sit, stand)
- **Parameters**: ~25,000 (very lightweight)
- **Inference**: ~10-15ms on CPU

## License

MIT License
