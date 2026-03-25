#!/bin/bash

# --- HARDCODED ABSOLUTE PATHS ---
PROJECT_DIR="/Volumes/personal/EEG/eeg_visual_simulation_lac"
BIDS_DIR="/Volumes/personal/EEG/ds006547"
THRESHOLD="0.60"

echo "=================================================="
echo " 🚀 STARTING FULL PHASE 1 AUTOMATION 🚀 "
echo "=================================================="

cd "$PROJECT_DIR" || { echo "❌ ERROR: Could not find the project folder at $PROJECT_DIR"; exit 1; }

# Activate the virtual environment so python3 resolves to the project venv
source "${PROJECT_DIR}/eeg-env/bin/activate"

for i in {01..31}; do
    SUB_ID=$(printf "sub-%02d" $i)
    BASE_NAME="${SUB_ID}_ses-01_task-visual_eeg"

    RAW_VHDR="${BIDS_DIR}/${SUB_ID}/ses-01/eeg/${BASE_NAME}.vhdr"
    OUT_DIR="${PROJECT_DIR}/Dataset/outputs/${SUB_ID}"

    ICA_PATH="${OUT_DIR}/${BASE_NAME}-ica.fif"
    REVIEW_JSON="${OUT_DIR}/${BASE_NAME}-ica_component_review.json"
    REFINED_REVIEW_JSON="${OUT_DIR}/${BASE_NAME}-ica_component_review-refined.json"
    EPOCHS_PATH="${OUT_DIR}/${BASE_NAME}-final-epo.fif"

    ALPHA_COND="${OUT_DIR}/${BASE_NAME}-alpha_by_condition.npz"
    GAMMA_COND="${OUT_DIR}/${BASE_NAME}-gamma_by_condition.npz"
    BAND_SUMMARY="${OUT_DIR}/${BASE_NAME}-band_power_summary.json"

    ERSP_NPY="${OUT_DIR}/${BASE_NAME}-component_ersp.npy"
    ERSP_EVENTS="${OUT_DIR}/${BASE_NAME}-component_ersp_event_codes.npy"
    ERSP_FREQS="${OUT_DIR}/${BASE_NAME}-component_ersp_freqs.npy"
    ERSP_TIMES="${OUT_DIR}/${BASE_NAME}-component_ersp_times.npy"

    echo ""
    echo "=================================================="
    echo " Processing ${SUB_ID}..."
    echo "=================================================="

    if [ ! -f "$RAW_VHDR" ]; then
        echo "❌ ERROR: Raw VHDR file not found for ${SUB_ID}. Skipping."
        continue
    fi

    mkdir -p "$OUT_DIR"

    # Step 1: Preprocess raw data and fit ICA
    echo "🔧 [Step 1] Preprocessing raw EEG and fitting ICA..."
    python3 Dataset/Scripts/preprocess.py \
      --vhdr "$RAW_VHDR" \
      --out-dir "$OUT_DIR"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 1 for ${SUB_ID}. Skipping."
        continue
    fi

    if [ ! -f "$ICA_PATH" ]; then
        echo "❌ ERROR: ICA file not found after preprocessing for ${SUB_ID}. Skipping."
        continue
    fi

    # Step 2: Run automated ICA inspection
    echo "🧠 [Step 2] Running mne-icalabel..."
    python3 Dataset/Scripts/auto_inspect_ica.py \
      --ica-path "$ICA_PATH" \
      --vhdr "$RAW_VHDR" \
      --threshold "$THRESHOLD"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 2 for ${SUB_ID}. Skipping."
        continue
    fi

    if [ ! -f "$REVIEW_JSON" ]; then
        echo "❌ ERROR: Review JSON not found for ${SUB_ID}. Skipping."
        continue
    fi

    # Step 2.5: Refine the ICA review JSON
    echo "🛠️ [Step 2.5] Refining borderline ICA decisions..."
    python3 Dataset/Scripts/refine_ica_review.py \
      --review-json "$REVIEW_JSON" \
      --out-json "$REFINED_REVIEW_JSON"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 2.5 for ${SUB_ID}. Skipping."
        continue
    fi

    if [ ! -f "$REFINED_REVIEW_JSON" ]; then
        echo "❌ ERROR: Refined review JSON not found for ${SUB_ID}. Skipping."
        continue
    fi

    # Step 3: Apply ICA using refined JSON
    echo "🧹 [Step 3] Applying ICA exclusions from refined review..."
    python3 Dataset/Scripts/apply_reviewed_ica.py \
      --ica-path "$ICA_PATH" \
      --vhdr "$RAW_VHDR" \
      --review-json "$REFINED_REVIEW_JSON"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 3 for ${SUB_ID}. Skipping."
        continue
    fi

    if [ ! -f "$EPOCHS_PATH" ]; then
        echo "❌ ERROR: Epochs file not found for ${SUB_ID}. Skipping remaining steps."
        continue
    fi

    # Step 4: Extract Band Power
    echo "⚡ [Step 4] Extracting Alpha/Gamma Power..."
    python3 Dataset/Scripts/extract_band_power.py --epochs-path "$EPOCHS_PATH"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 4 for ${SUB_ID}. Skipping."
        continue
    fi

    # Step 5: Retinotopy
    echo "👁️  [Step 5] Building Retinotopy Summaries..."
    python3 Dataset/Scripts/condition_analysis.py \
      --alpha-by-condition "$ALPHA_COND" \
      --gamma-by-condition "$GAMMA_COND" \
      --band-power-summary "$BAND_SUMMARY"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 5 for ${SUB_ID}. Skipping."
        continue
    fi

    # Step 6: Orientation tuning
    echo "📐 [Step 6] Building Orientation Summaries..."
    python3 Dataset/Scripts/orientation_tuning_analysis.py \
      --alpha-by-condition "$ALPHA_COND" \
      --gamma-by-condition "$GAMMA_COND" \
      --band-power-summary "$BAND_SUMMARY"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 6 for ${SUB_ID}. Skipping."
        continue
    fi

    # Step 7: ERSP extraction
    echo "🌊 [Step 7] Extracting Single-Trial ERSPs..."
    python3 Dataset/Scripts/extract_component_ersp.py \
      --vhdr "$RAW_VHDR" \
      --ica-path "$ICA_PATH"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 7 for ${SUB_ID}. Skipping."
        continue
    fi

    # Step 8: ERSP stats
    echo "📊 [Step 8] Computing ERSP Statistics..."
    python3 Dataset/Scripts/orientation_ersp_stats.py \
      --ersp-npy "$ERSP_NPY" \
      --event-codes-npy "$ERSP_EVENTS" \
      --freqs-npy "$ERSP_FREQS" \
      --times-npy "$ERSP_TIMES"
    if [ $? -ne 0 ]; then
        echo "❌ ERROR on Step 8 for ${SUB_ID}. Skipping."
        continue
    fi

    echo "✅ SUCCESS: Phase 1 fully completed for ${SUB_ID}!"
done

echo ""
echo "=================================================="
echo " 🎉 ALL SUBJECTS FINISHED PHASE 1 PROCESSING! 🎉 "
echo "=================================================="