#!/bin/bash
# Quick Start Script for WiFall Fall Detection System
# This script downloads the dataset and trains the model in one go

set -e

echo "========================================"
echo "  WiFall Fall Detection - Quick Start"
echo "========================================"
echo ""

# Configuration
DATA_DIR="./data/wifall"
OUTPUT_DIR="./output"
MODEL_TYPE="lightweight"
EPOCHS=50
BATCH_SIZE=32

# Check Python version
echo "Checking Python environment..."
python3 --version

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install datasets torch numpy scipy matplotlib tqdm -q

# Step 1: Download and process WiFall dataset
echo ""
echo "Step 1: Downloading WiFall dataset from HuggingFace..."
if [ -d "$DATA_DIR" ]; then
    echo "  Data directory already exists. Skipping download."
    echo "  Delete $DATA_DIR to re-download."
else
    python3 load_wifall_dataset.py \
        --output "$DATA_DIR" \
        --window-size 100 \
        --hop-size 50 \
        --visualize
fi

# Check if data was downloaded
if [ ! -f "$DATA_DIR/train_csi.npy" ]; then
    echo "Error: Dataset not found. Download may have failed."
    exit 1
fi

# Step 2: Train the model
echo ""
echo "Step 2: Training fall detection model..."
python3 train_wifall_model.py \
    --data "$DATA_DIR" \
    --output "$OUTPUT_DIR" \
    --model-type "$MODEL_TYPE" \
    --epochs "$EPOCHS" \
    --batch-size "$BATCH_SIZE" \
    --augment

# Step 3: Find the trained model
LATEST_OUTPUT=$(ls -td "$OUTPUT_DIR"/train_* 2>/dev/null | head -1)

if [ -z "$LATEST_OUTPUT" ]; then
    echo "Error: Training output not found."
    exit 1
fi

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Files created:"
echo "  - Dataset: $DATA_DIR/"
echo "  - Model: $LATEST_OUTPUT/weights/best_model.pt"
echo "  - Config: $LATEST_OUTPUT/weights/model_config.json"
echo ""
echo "Next steps:"
echo "  1. Copy the model to your Jetson Nano"
echo "  2. Run the real-time detection:"
echo "     python -m processing.realtime_detector --model-path $LATEST_OUTPUT/weights/best_model.pt"
echo ""
