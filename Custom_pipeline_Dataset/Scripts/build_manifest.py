#!/usr/bin/env python3
"""Build phase2_manifest.json listing all valid Custom Pipeline subjects."""
import json
import os
import sys
from pathlib import Path

# Accept outputs_dir and phase2_dir as arguments, or derive from script location
SCRIPTS_DIR  = Path(__file__).resolve().parent
PROJECT_DIR  = SCRIPTS_DIR.parent.parent
OUTPUTS_DIR  = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_DIR / "Custom_pipeline_Dataset" / "outputs"
PHASE2_DIR   = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUTS_DIR / "group_level"

manifest_path = PHASE2_DIR / "phase2_manifest.json"
PHASE2_DIR.mkdir(parents=True, exist_ok=True)

subjects = []
for i in range(1, 32):
    sub_id  = f"sub-{i:02d}"
    base    = f"{sub_id}_ses-01_task-visual_eeg"
    out_dir = OUTPUTS_DIR / sub_id
    files = {
        "subject":             sub_id,
        "out_dir":             str(out_dir),
        "epochs_fif":          str(out_dir / f"{base}-final-epo.fif"),
        "band_power_summary":  str(out_dir / f"{base}-band_power_summary.json"),
        "alpha_by_condition":  str(out_dir / f"{base}-alpha_by_condition.npz"),
        "gamma_by_condition":  str(out_dir / f"{base}-gamma_by_condition.npz"),
        "retinotopy_summary":  str(out_dir / "retinotopy_summary.json"),
        "orientation_summary": str(out_dir / "orientation_tuning_summary.json"),
        "ersp_npy":            str(out_dir / f"{base}-component_ersp.npy"),
        "ersp_event_codes":    str(out_dir / f"{base}-component_ersp_event_codes.npy"),
        "ersp_freqs":          str(out_dir / f"{base}-component_ersp_freqs.npy"),
        "ersp_times":          str(out_dir / f"{base}-component_ersp_times.npy"),
    }
    required = [Path(files[k]) for k in (
        "epochs_fif", "band_power_summary", "alpha_by_condition", "gamma_by_condition"
    )]
    if all(p.exists() for p in required):
        files["has_retinotopy"] = Path(files["retinotopy_summary"]).exists()
        files["has_orientation"] = Path(files["orientation_summary"]).exists()
        files["has_ersp"] = all(
            Path(files[k]).exists()
            for k in ("ersp_npy", "ersp_event_codes", "ersp_freqs", "ersp_times")
        )
        subjects.append(files)

manifest = {
    "n_subjects":      len(subjects),
    "subjects":        subjects,
    "group_output_dir": str(PHASE2_DIR),
}
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Saved manifest: {manifest_path}")
print(f"Valid subjects found: {len(subjects)}")
for s in subjects:
    print(f"  - {s['subject']}")
