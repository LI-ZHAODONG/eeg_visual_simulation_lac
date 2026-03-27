#!/bin/bash
# BIDS Pipeline — Phase 1: MNE-BIDS-Pipeline preprocessing

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BIDS_DIR="${BIDS_DIR:-$(cd "$PROJECT_DIR/../ds006547" 2>/dev/null && pwd || echo "$PROJECT_DIR/../ds006547")}"

echo "=================================================="
echo " BIDS PIPELINE — PHASE 1: PREPROCESSING"
echo "=================================================="
echo "  Project : $PROJECT_DIR"
echo "  BIDS    : $BIDS_DIR"
echo "=================================================="

cd "$PROJECT_DIR" || { echo "ERROR: Could not find project folder at $PROJECT_DIR"; exit 1; }
source "${PROJECT_DIR}/eeg-env/bin/activate"

if [ ! -d "$BIDS_DIR" ]; then
    echo "ERROR: BIDS dataset not found at $BIDS_DIR"
    echo "  Set the BIDS_DIR environment variable to the ds006547 path:"
    echo "    export BIDS_DIR=/path/to/ds006547"
    exit 1
fi

export BIDS_ROOT="$BIDS_DIR"

echo "Running MNE-BIDS-Pipeline preprocessing..."
python "$SCRIPT_DIR/run_pipeline.py" --steps preprocessing --n-jobs 4
if [ $? -ne 0 ]; then
    echo "ERROR: MNE-BIDS-Pipeline preprocessing failed."
    exit 1
fi

echo ""
echo "=================================================="
echo " PHASE 1 COMPLETE"
echo " Outputs: $PROJECT_DIR/Bids_pipeline_Dataset/outputs/derivatives"
echo "=================================================="
