#!/bin/bash
# BIDS Pipeline — Phase 2: Custom analysis scripts (band power, retinotopy, orientation, group stats)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=================================================="
echo " BIDS PIPELINE — PHASE 2: CUSTOM ANALYSES"
echo "=================================================="
echo "  Project : $PROJECT_DIR"
echo "=================================================="

cd "$PROJECT_DIR" || { echo "ERROR: Could not find project folder at $PROJECT_DIR"; exit 1; }
source "${PROJECT_DIR}/eeg-env/bin/activate"

echo "Running all custom analyses (band power, retinotopy, orientation, group stats)..."
python "$SCRIPT_DIR/run_all.py"
if [ $? -ne 0 ]; then
    echo "ERROR: Custom analysis pipeline failed."
    exit 1
fi

echo ""
echo "=================================================="
echo " PHASE 2 COMPLETE"
echo " Group outputs: $PROJECT_DIR/Bids_pipeline_Dataset/outputs/derivatives/bids_analysis/group_level"
echo "=================================================="
