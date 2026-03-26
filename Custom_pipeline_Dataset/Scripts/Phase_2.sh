#!/bin/bash

# --- Paths (relative to this script's location) ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUTS_DIR="${PROJECT_DIR}/Custom_pipeline_Dataset/outputs"
PHASE2_DIR="${OUTPUTS_DIR}/group_level"

MANIFEST_JSON="${PHASE2_DIR}/phase2_manifest.json"

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

python3 - <<EOF
import json
from pathlib import Path

outputs_dir = Path("$OUTPUTS_DIR")
phase2_dir = Path("$PHASE2_DIR")
manifest_path = Path("$MANIFEST_JSON")

subjects = []

for i in range(1, 32):
    sub_id = f"sub-{i:02d}"
    base = f"{sub_id}_ses-01_task-visual_eeg"
    out_dir = outputs_dir / sub_id

    files = {
        "subject": sub_id,
        "out_dir": str(out_dir),
        "epochs_fif": str(out_dir / f"{base}-final-epo.fif"),
        "band_power_summary": str(out_dir / f"{base}-band_power_summary.json"),
        "alpha_by_condition": str(out_dir / f"{base}-alpha_by_condition.npz"),
        "gamma_by_condition": str(out_dir / f"{base}-gamma_by_condition.npz"),
        "retinotopy_summary": str(out_dir / "retinotopy_summary.json"),
        "orientation_summary": str(out_dir / "orientation_tuning_summary.json"),
        "ersp_npy": str(out_dir / f"{base}-component_ersp.npy"),
        "ersp_event_codes": str(out_dir / f"{base}-component_ersp_event_codes.npy"),
        "ersp_freqs": str(out_dir / f"{base}-component_ersp_freqs.npy"),
        "ersp_times": str(out_dir / f"{base}-component_ersp_times.npy"),
    }

    required = [
        Path(files["epochs_fif"]),
        Path(files["band_power_summary"]),
        Path(files["alpha_by_condition"]),
        Path(files["gamma_by_condition"]),
    ]

    if all(p.exists() for p in required):
        files["has_retinotopy"] = Path(files["retinotopy_summary"]).exists()
        files["has_orientation"] = Path(files["orientation_summary"]).exists()
        files["has_ersp"] = all(
            Path(files[k]).exists()
            for k in ["ersp_npy", "ersp_event_codes", "ersp_freqs", "ersp_times"]
        )
        subjects.append(files)

manifest = {
    "n_subjects": len(subjects),
    "subjects": subjects,
    "group_output_dir": str(phase2_dir),
}

manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Saved manifest: {manifest_path}")
print(f"Valid subjects found: {len(subjects)}")
for s in subjects:
    print(f"  - {s['subject']}")
EOF

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

echo ""
echo "=================================================="
echo " 🎉 PHASE 2 COMPLETED 🎉 "
echo "=================================================="