#!/bin/bash

# --- Paths (relative to this script's location) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUTS_DIR="${PROJECT_DIR}/Custom_pipeline_Dataset/outputs"
PHASE2_DIR="${OUTPUTS_DIR}/group_level"

RETINO_SCRIPT="${SCRIPT_DIR}/retinotopy_model_fit.py"
GRAND_AVG_SCRIPT="${SCRIPT_DIR}/grand_average_analysis.py"
TOPOMAP_SCRIPT="${SCRIPT_DIR}/group_topomaps.py"
GROUP_STAT_SCRIPT="${SCRIPT_DIR}/group_statistical_analysis.py"
ERSP_SCRIPT="${SCRIPT_DIR}/group_ersp_statistics.py"
MAPPING_JSON="${SCRIPT_DIR}/condition_mapping.json"

echo "=================================================="
echo " 🚀 STARTING PHASE 2 GROUP-LEVEL AUTOMATION 🚀 "
echo "=================================================="

cd "$PROJECT_DIR" || { echo "❌ ERROR: Could not find the project folder at $PROJECT_DIR"; exit 1; }
source "${PROJECT_DIR}/eeg-env/bin/activate"

mkdir -p "$PHASE2_DIR"

echo "🧾 Building manifest of valid subjects..."
python3 "$SCRIPT_DIR/build_manifest.py" "$OUTPUTS_DIR" "$PHASE2_DIR"
if [ $? -ne 0 ]; then
    echo "❌ ERROR: Manifest creation failed."
    exit 1
fi

echo ""
echo "=================================================="
echo " 📊 STARTING GROUP ANALYSIS "
echo "=================================================="

# ---------- Step 1: Grand Average ----------
if [ -f "$GRAND_AVG_SCRIPT" ]; then
    echo "📈 Running grand average analysis..."
    python3 "$GRAND_AVG_SCRIPT" \
      --outputs-root "$OUTPUTS_DIR" \
      --mapping-json "$MAPPING_JSON" \
      --out-dir "$PHASE2_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on grand average analysis."; fi
else
    echo "⚠️ Grand average script not found. Skipping."
fi

# ---------- Step 2: Topomaps ----------
if [ -f "$TOPOMAP_SCRIPT" ]; then
    echo "🗺️ Running group topomaps..."
    python3 "$TOPOMAP_SCRIPT" \
      --outputs-root "$OUTPUTS_DIR" \
      --mapping-json "$MAPPING_JSON" \
      --out-dir "$PHASE2_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on group topomaps."; fi
else
    echo "⚠️ Topomap script not found. Skipping."
fi

# ---------- Step 3: Retinotopy Model Fit ----------
if [ -f "$RETINO_SCRIPT" ]; then
    echo "👁️ Running retinotopy model fit..."
    python3 "$RETINO_SCRIPT" \
      --outputs-root "$OUTPUTS_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on retinotopy model fit."; fi
else
    echo "⚠️ Retinotopy script not found. Skipping."
fi

# ---------- Step 4: Group Statistical Analysis ----------
if [ -f "$GROUP_STAT_SCRIPT" ]; then
    echo "📐 Running group statistical analysis..."
    python3 "$GROUP_STAT_SCRIPT" \
      --outputs-dir "$OUTPUTS_DIR" \
      --mapping "$MAPPING_JSON" \
      --out-dir "$PHASE2_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on group statistical analysis."; fi
else
    echo "⚠️ Group statistical analysis script not found. Skipping."
fi

# ---------- Step 5: Group ERSP Statistics ----------
if [ -f "$ERSP_SCRIPT" ]; then
    echo "🌊 Running group ERSP statistics..."
    python3 "$ERSP_SCRIPT" \
      --outputs-dir "$OUTPUTS_DIR" \
      --out-dir "$PHASE2_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on group ERSP statistics."; fi
else
    echo "⚠️ ERSP statistics script not found. Skipping."
fi

# ---------- Step 6: Group Orientation ERSP Stats ----------
GROUP_ORI_ERSP_SCRIPT="${SCRIPT_DIR}/group_orientation_ersp_stats.py"
if [ -f "$GROUP_ORI_ERSP_SCRIPT" ]; then
    echo "📐 Running group orientation ERSP statistics..."
    python3 "$GROUP_ORI_ERSP_SCRIPT" \
      --outputs-root "$OUTPUTS_DIR" \
      --out-dir "$PHASE2_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on group orientation ERSP stats."; fi
else
    echo "⚠️ Group orientation ERSP script not found. Skipping."
fi

# ---------- Step 7: Group Sensor ERSP ----------
GROUP_SENSOR_ERSP_SCRIPT="${SCRIPT_DIR}/group_sensor_ersp.py"
if [ -f "$GROUP_SENSOR_ERSP_SCRIPT" ]; then
    echo "🌊 Running group sensor ERSP summary..."
    python3 "$GROUP_SENSOR_ERSP_SCRIPT" \
      --outputs-root "$OUTPUTS_DIR" \
      --out-dir "$PHASE2_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on group sensor ERSP summary."; fi
else
    echo "⚠️ Group sensor ERSP script not found. Skipping."
fi

# ---------- Step 8: Group Sensor ANOVA ----------
GROUP_SENSOR_ANOVA_SCRIPT="${SCRIPT_DIR}/group_sensor_anova.py"
if [ -f "$GROUP_SENSOR_ANOVA_SCRIPT" ]; then
    echo "🧠 Running group sensor ANOVA mapping..."
    python3 "$GROUP_SENSOR_ANOVA_SCRIPT" \
      --outputs-root "$OUTPUTS_DIR" \
      --out-dir "$PHASE2_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on group sensor ANOVA mapping."; fi
else
    echo "⚠️ Group sensor ANOVA script not found. Skipping."
fi

# ---------- Step 9: Group Orientation/Direction Analysis ----------
GROUP_ORI_DIR_SCRIPT="${SCRIPT_DIR}/group_orientation_direction_analysis.py"
if [ -f "$GROUP_ORI_DIR_SCRIPT" ]; then
    echo "📊 Running group orientation/direction analysis..."
    python3 "$GROUP_ORI_DIR_SCRIPT" \
      --outputs-root "$OUTPUTS_DIR"
    if [ $? -ne 0 ]; then echo "❌ ERROR on group orientation/direction analysis."; fi
else
    echo "⚠️ Group orientation/direction analysis script not found. Skipping."
fi

echo ""
echo "=================================================="
echo " 🎉 PHASE 2 COMPLETED 🎉 "
echo "=================================================="
