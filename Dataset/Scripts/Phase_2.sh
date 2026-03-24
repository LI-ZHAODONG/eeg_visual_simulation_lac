#!/bin/bash

# --- ABSOLUTE PATHS ONLY ---
PROJECT_DIR="/Volumes/personal/EEG/project/eeg_visual_simulation_lac"
OUTPUTS_DIR="/Volumes/personal/EEG/project/eeg_visual_simulation_lac/Dataset/outputs"
PHASE2_DIR="/Volumes/personal/EEG/project/eeg_visual_simulation_lac/Dataset/outputs/group_level"

MANIFEST_JSON="/Volumes/personal/EEG/project/eeg_visual_simulation_lac/Dataset/outputs/group_level/phase2_manifest.json"

RETINO_SCRIPT="/Volumes/personal/EEG/project/eeg_visual_simulation_lac/Dataset/Scripts/group_retinotopy_analysis.py"
ORIENT_SCRIPT="/Volumes/personal/EEG/project/eeg_visual_simulation_lac/Dataset/Scripts/group_orientation_analysis.py"
ERSP_SCRIPT="/Volumes/personal/EEG/project/eeg_visual_simulation_lac/Dataset/Scripts/group_ersp_analysis.py"

echo "=================================================="
echo " 🚀 STARTING PHASE 2 GROUP-LEVEL AUTOMATION 🚀 "
echo "=================================================="

mkdir -p "$PHASE2_DIR"

echo "🧾 Building manifest of valid subjects..."

python - <<EOF
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

# ---------- Retinotopy ----------
if [ -f "$RETINO_SCRIPT" ]; then
    echo "👁️ Running group retinotopy..."
    python "$RETINO_SCRIPT" \
      --manifest-json "$MANIFEST_JSON" \
      --out-dir "$PHASE2_DIR"
else
    echo "⚠️ Retinotopy script not found. Skipping."
fi

# ---------- Orientation ----------
if [ -f "$ORIENT_SCRIPT" ]; then
    echo "📐 Running group orientation..."
    python "$ORIENT_SCRIPT" \
      --manifest-json "$MANIFEST_JSON" \
      --out-dir "$PHASE2_DIR"
else
    echo "⚠️ Orientation script not found. Skipping."
fi

# ---------- ERSP ----------
if [ -f "$ERSP_SCRIPT" ]; then
    echo "🌊 Running group ERSP..."
    python "$ERSP_SCRIPT" \
      --manifest-json "$MANIFEST_JSON" \
      --out-dir "$PHASE2_DIR"
else
    echo "⚠️ ERSP script not found. Skipping."
fi

echo ""
echo "=================================================="
echo " 🎉 PHASE 2 COMPLETED 🎉 "
echo "=================================================="