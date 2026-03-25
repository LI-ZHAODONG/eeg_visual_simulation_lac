# MNE-BIDS-Pipeline Migration Plan

## Overview

Replace the current custom 9-script pipeline (Phase_1.sh + Phase_2.sh) with
[MNE-BIDS-Pipeline](https://mne.tools/mne-bids-pipeline/), a standardized,
config-driven processing framework that operates directly on BIDS-formatted data.

**Why this is the right move:**
- The dataset (ds006547) is already fully BIDS-compliant
- One config file replaces ~2000 lines of custom Python + Bash
- Better reproducibility (declarative config vs imperative scripts)
- Still satisfies the professor's "different pipeline" requirement
- Adds automated reporting (HTML reports per subject + group)

---

## Current Pipeline vs MNE-BIDS-Pipeline

| Current Custom Pipeline | MNE-BIDS-Pipeline Equivalent | Notes |
|---|---|---|
| `preprocess.py` (bad channels, notch, bandpass, resample, ICA fit) | Built-in: `find_bad_channels`, `filter`, `resample`, `run_ica` steps | Configured via settings, not code |
| `auto_inspect_ica.py` + `refine_ica_review.py` | Built-in: `ica_reject_components` with ICLabel supported | `ica_reject` config options |
| `apply_reviewed_ica.py` | Built-in: applies ICA automatically after labeling | Automatic |
| `extract_band_power.py` (Hilbert alpha/gamma) | **Custom step needed** | Pipeline does TFR but not Hilbert band power |
| `condition_analysis.py` (retinotopy) | **Custom step needed** | Condition-specific analysis is project-specific |
| `orientation_tuning_analysis.py` | **Custom step needed** | Project-specific analysis |
| `extract_component_ersp.py` (Morlet ERSP) | Built-in: `time_frequency` step (Morlet wavelets) | Configurable freq range, baseline |
| `orientation_ersp_stats.py` | **Custom step needed** | Specific statistical tests |
| `grand_average_analysis.py` | Built-in: `group_average_sensors` step | Automatic |
| `group_topomaps.py` | Built-in: generates topomaps in reports | Automatic reports |
| `group_statistical_analysis.py` | Partially built-in: `group_average_sensors` | Custom stats still needed |
| `retinotopy_model_fit.py` | **Custom step needed** | Model fitting is project-specific |

---

## Architecture: What Replaces What

### Before (Custom Pipeline)

```
Phase_1.sh                  # Bash orchestrator
├── preprocess.py           # Filtering, bad channels, ICA fit
├── auto_inspect_ica.py     # ICLabel classification
├── refine_ica_review.py    # Heuristic refinement
├── apply_reviewed_ica.py   # Apply ICA exclusions
├── extract_band_power.py   # Alpha/gamma Hilbert power
├── condition_analysis.py   # Retinotopy analysis
├── orientation_tuning_analysis.py  # Orientation tuning
├── extract_component_ersp.py       # Morlet ERSP
└── orientation_ersp_stats.py       # ERSP statistics

Phase_2.sh                  # Group-level orchestrator
├── grand_average_analysis.py
├── group_topomaps.py
├── group_statistical_analysis.py
├── retinotopy_model_fit.py
└── group_ersp_statistics.py
```

### After (MNE-BIDS-Pipeline + Custom Analysis)

```
config.py                   # Single config file controls entire preprocessing
run_pipeline.py             # Simple launcher script

bids_analysis/              # Post-pipeline analysis scripts
├── extract_band_power.py   # Alpha/gamma from cleaned epochs
├── condition_analysis.py   # Retinotopy summaries
├── orientation_tuning.py   # Orientation tuning analysis
├── retinotopy_model_fit.py # Linear vs DivNorm model
├── group_statistics.py     # Group-level stats
└── run_all.py              # Run all custom analyses
```

---

## Step-by-Step Migration Plan

### Phase A: Setup (Day 1)

1. **Install packages:**
   ```bash
   pip install mne-bids-pipeline mne-bids mne-icalabel
   ```

2. **Verify BIDS dataset:**
   ```bash
   # Already at /Volumes/personal/EEG/ds006547
   # Already BIDS 1.9.0 compliant with BrainVision files
   ```

3. **Create `config.py`** — the single configuration file that defines the entire
   preprocessing pipeline (see below for full config)

4. **Test on one subject:**
   ```bash
   mne_bids_pipeline --config config.py --subject 01 --steps preprocessing
   ```

### Phase B: Full Preprocessing (Day 1-2)

5. **Run preprocessing for all subjects:**
   ```bash
   mne_bids_pipeline --config config.py --steps preprocessing
   ```
   This single command replaces Steps 1-3 of Phase_1.sh:
   - Bad channel detection + interpolation
   - Filtering (notch + bandpass)
   - Resampling
   - ICA fit + automatic component rejection

6. **Run sensor-level analysis:**
   ```bash
   mne_bids_pipeline --config config.py --steps sensor
   ```
   This generates:
   - Evoked responses per condition
   - Contrasts between conditions
   - Group averages

7. **Run time-frequency analysis:**
   ```bash
   mne_bids_pipeline --config config.py --steps sensor/time_frequency
   ```
   This replaces `extract_component_ersp.py` (Step 7 of Phase_1.sh)

### Phase C: Custom Analysis Scripts (Day 2-3)

8. **Create custom analysis scripts** that read the pipeline's clean epochs
   and compute project-specific metrics:
   - Alpha (8-13 Hz) and gamma (40-80 Hz) band power via Hilbert
   - Retinotopy condition summaries
   - Orientation tuning indices
   - Linear vs divisive normalization model fitting
   - Group-level statistics

9. **Run custom analyses:**
   ```bash
   python bids_analysis/run_all.py
   ```

### Phase D: Reporting (Day 3)

10. **Generate pipeline reports:**
    ```bash
    mne_bids_pipeline --config config.py --steps preprocessing,sensor --gen-report
    ```
    This creates HTML reports with:
    - Per-subject preprocessing QC (bad channels, ICA components, PSD)
    - Evoked responses
    - Topomaps
    - Group averages

11. **Update submission notebook** to reference pipeline outputs

---

## Key Configuration Decisions

| Parameter | Value | Rationale |
|---|---|---|
| `ch_types` | `["eeg"]` | EEG-only dataset |
| `task` | `"visual"` | Matches BIDS task name |
| `sessions` | `["01"]` | Single session per subject |
| `eeg_reference` | `"average"` | Common average reference |
| `l_freq` | `1.0` | High-pass at 1 Hz (same as current) |
| `h_freq` | `100.0` | Low-pass at 100 Hz (same as current) |
| `notch_freq` | `60` | Power line frequency (from sidecar JSON) |
| `resample_sfreq` | `200` | Downsample to 200 Hz (same as current) |
| `ica_method` | `"picard"` | Same ICA variant as current pipeline |
| `ica_n_components` | `0.99` | Variance-based (more robust than fixed 60) |
| `ica_reject_components` | `"auto"` with ICLabel | Automatic component rejection |
| `epochs_tmin` | `-0.5` | 500 ms pre-stimulus baseline |
| `epochs_tmax` | `3.0` | 3 s post-stimulus |
| `baseline` | `(-0.5, 0)` | Pre-stimulus baseline |
| `time_frequency_freqs` | `4-100 Hz` | Full TFR range (same as current ERSP) |

---

## What You Gain

1. **Standardized processing** — same pipeline used by hundreds of MNE labs worldwide
2. **Automatic HTML reports** — no need to manually create QC figures
3. **Parallel processing** — MNE-BIDS-Pipeline supports `--n-jobs` for multi-core
4. **Reproducibility** — config file is the complete specification
5. **Professor alignment** — using a well-known community pipeline strengthens the
   "different pipeline" argument even further
6. **Less code to maintain** — config.py (~80 lines) vs custom scripts (~2000 lines)

## What You Keep (Custom Analysis)

The pipeline handles preprocessing and basic sensor-level analysis. You still need
custom scripts for:

1. **Hilbert-based band power extraction** (alpha/gamma task vs baseline)
2. **Retinotopy condition analysis** (mapping trigger codes 1-20 to spatial conditions)
3. **Orientation tuning analysis** (trigger codes 41-56, tuning indices)
4. **Divisive normalization model fitting** (linear vs DivNorm comparison)
5. **Group-level ERSP statistics** (cluster-based testing)

These custom scripts read the pipeline's cleaned epochs (`*-epo.fif`) and operate
on them — much simpler than the current approach since preprocessing is already done.

---

## File Structure After Migration

```
eeg_visual_simulation_lac/
├── requirements.txt               # Python dependencies
├── submission_report.ipynb        # Final report notebook
├── Custom_pipeline_Dataset/
│   ├── Scripts/                   # Custom pipeline scripts + Phase_1.sh / Phase_2.sh
│   └── outputs/                   # Custom pipeline outputs
├── Bids_pipeline_Dataset/
│   ├── Scripts/                   # BIDS pipeline scripts (config.py, run_pipeline.py, utils.py)
│   └── outputs/
│       ├── group_level/           # Group-level results
│       ├── sub-01/ ... sub-31/    # Per-subject results
│       └── derivatives/
│           └── bids_analysis/     # Post-pipeline analysis outputs
└── MNE_BIDS_PIPELINE_PLAN.md
```

---

## Timeline Estimate

| Phase | Duration | Description |
|---|---|---|
| A: Setup | 1-2 hours | Install, config, test on sub-01 |
| B: Full preprocessing | 4-8 hours | All 31 subjects (automated, unattended) |
| C: Custom analysis | 4-6 hours | Adapt 5 analysis scripts to read pipeline output |
| D: Reporting | 1-2 hours | Generate reports, update notebook |
| **Total** | **~1-2 days** | Mostly automated processing time |

---

## Risk Mitigation

- **Original pipeline preserved:** All existing scripts remain in `Custom_pipeline_Dataset/Scripts/`
- **Original outputs preserved:** All existing outputs remain in `Custom_pipeline_Dataset/outputs/`
- **Git branch:** Work on `exp-002` branch (already created)
- **Fallback:** If pipeline fails for specific subjects, clean epochs can be generated
  from original scripts and placed in derivatives manually
