# EEG Visual Task Analysis

This repository contains a rebuilt EEG analysis pipeline for a visual task, aligned as closely as possible to the paper:

`Dissociable Spatial and Feature Tuning of Gamma and Alpha Rhythms in Human Visual Cortex`

The pipeline is written in Python and uses:

- `mne`
- `numpy`
- `scipy`
- `matplotlib`
- `python-picard`

The raw BrainVision/BIDS dataset is **not included** in this checkout.

## Current Status

This repo is now:

- paper-aligned in preprocessing order
- rebuilt enough to run subject-level and several group-level analyses
- capable of generating ICA, sensor-space alpha/gamma outputs, ERSP outputs, retinotopy summaries, orientation summaries, model-fit summaries, and rebuilt group topomaps
- validated far enough to run one full subject (`sub-01`) end-to-end without script errors

This repo is **not yet guaranteed to be an exact reproduction** of the paper because:

- retinotopy trigger codes `21` and `22` are still unresolved
- the current divisive-normalization implementation is an informed approximation
- ERSP cluster statistics are thresholded clusters, not permutation-based clusters
- some figure formatting still differs from the paper
- the current `sub-01` orientation ERSP result is still weaker/noisier than the paper, so ICA selection and multi-subject validation still matter

## Repository Layout

```text
.
├── Dataset/
│   ├── Scripts/
│   │   ├── preprocess.py
│   │   ├── manual_inspect_ica.py
│   │   ├── apply_reviewed_ica.py
│   │   ├── extract_band_power.py
│   │   ├── extract_component_ersp.py
│   │   ├── condition_analysis.py
│   │   ├── orientation_tuning_analysis.py
│   │   ├── orientation_ersp_stats.py
│   │   ├── grand_average_analysis.py
│   │   ├── group_topomaps.py
│   │   ├── retinotopy_model_fit.py
│   │   └── condition_mapping.json
│   └── outputs/
│       ├── sub-01/
│       ├── sub-02/
│       ├── ...
│       └── sub-31/
├── Paper.pdf
├── Readme.md
├── PROJECT_TODO.md
└── requirements.txt
```

## Installation

```bash
python3 -m venv eeg-env
source eeg-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Data Path Note

The raw dataset used during development lived outside this repo in a BIDS/git-annex checkout such as:

```text
/Volumes/personal/EEG/ds006547
```

When running BrainVision files from a git-annex dataset, pass the subject-facing `.vhdr` path, for example:

```bash
/Volumes/personal/EEG/ds006547/sub-01/ses-01/eeg/sub-01_ses-01_task-visual_eeg.vhdr
```

Do not manually replace that with the resolved `.git/annex/objects/...` path. The scripts now preserve the original `.vhdr` path so MNE can find the matching `.vmrk` and `.eeg` sidecars.

## Rebuilt Run Order

The core run order for one subject is:

### 1. Fit ICA from raw data

```bash
python Dataset/Scripts/preprocess.py \
  --vhdr /path/to/sub-01_ses-01_task-visual_eeg.vhdr
```

This step:

- detects bad channels using `10-100 Hz` SSD z-scores
- interpolates bad channels
- applies `60 Hz` notch filtering
- creates an ICA-prep copy filtered at `1-100 Hz`
- downsamples to `200 Hz`
- epochs `-1.0 to 4.0 s` for ICA training
- fits ICA and saves:
  - `*-ica.fif`
  - bad-channel JSON
  - preprocess summary JSON
  - ICA review template JSON

### 2. Review ICA components

```bash
python Dataset/Scripts/manual_inspect_ica.py \
  --ica-path Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-ica.fif \
  --vhdr /path/to/sub-01_ses-01_task-visual_eeg.vhdr
```

This step:

- saves ICA topography figures
- optionally saves ICA property plots if the raw file is supplied
- creates or updates the review JSON where components are marked `keep` or `reject`

Important behavior:

- if you mark one or more components with `"keep": true`, [apply_reviewed_ica.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/apply_reviewed_ica.py) will exclude every other ICA component
- if you want to reject only a few artifact components, set those to `"keep": false` and avoid marking a tiny keep-only subset by mistake
- for first-pass review, it is usually safer to reject only clear artifacts than to keep only one or two components

### 3. Apply reviewed ICA decisions

```bash
python Dataset/Scripts/apply_reviewed_ica.py \
  --vhdr /path/to/sub-01_ses-01_task-visual_eeg.vhdr \
  --ica-path Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-ica.fif
```

This step:

- rebuilds the cleaned sensor-space raw data
- applies reviewed ICA exclusions
- saves:
  - cleaned raw `.fif`
  - cleaned epochs `.fif`
  - PSD/QC figures
  - apply summary JSON

### 4. Extract sensor-space alpha/gamma power

```bash
python Dataset/Scripts/extract_band_power.py \
  --epochs-path Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-final-epo.fif
```

This step:

- computes alpha `8-13 Hz`
- computes gamma `40-80 Hz`
- uses analytic amplitude and `|task| - |baseline|`
- saves:
  - trial-level alpha/gamma arrays
  - mean alpha/gamma vectors
  - per-condition alpha/gamma `.npz`
  - event-code `.npy`
  - band-power summary JSON

### 5. Build subject-level retinotopy summaries

```bash
python Dataset/Scripts/condition_analysis.py \
  --alpha-by-condition Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-alpha_by_condition.npz \
  --gamma-by-condition Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-gamma_by_condition.npz \
  --band-power-summary Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-band_power_summary.json
```

This step saves:

- retinotopy alpha summary plot
- retinotopy gamma summary plot
- alpha-vs-gamma scatter and residuals

### 6. Build subject-level orientation summaries

```bash
python Dataset/Scripts/orientation_tuning_analysis.py \
  --alpha-by-condition Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-alpha_by_condition.npz \
  --gamma-by-condition Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-gamma_by_condition.npz \
  --band-power-summary Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-band_power_summary.json
```

This step saves:

- trigger-level orientation summaries
- grouped orientation and direction summaries
- alpha-vs-gamma scatter plots
- pairwise t-test heatmaps if trial-level arrays are available

### 7. Extract retained-component ERSPs

```bash
python Dataset/Scripts/extract_component_ersp.py \
  --vhdr /path/to/sub-01_ses-01_task-visual_eeg.vhdr \
  --ica-path Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-ica.fif
```

This step:

- keeps only reviewed ICA components
- computes Morlet ERSPs `4-100 Hz`
- uses buffered epochs `-1.6 to 4.6 s`
- crops to `-1.0 to 4.0 s`
- baseline-corrects each trial using `-0.5 to 0 s`

### 8. Compute ERSP orientation statistics

```bash
python Dataset/Scripts/orientation_ersp_stats.py \
  --ersp-npy Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-component_ersp.npy \
  --event-codes-npy Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-component_ersp_event_codes.npy \
  --freqs-npy Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-component_ersp_freqs.npy \
  --times-npy Dataset/outputs/sub-01/sub-01_ses-01_task-visual_eeg-component_ersp_times.npy
```

This step:

- keeps only triggers `41-56`
- rejects broadband outlier trials
- smooths ERSPs
- runs ANOVA across orientation triggers
- generates a thresholded cluster mask
- saves ERSP summary figures and a frequency-frequency correlation map

## Group-Level Scripts

Once multiple subjects have been processed, the following scripts aggregate outputs from `Dataset/outputs/sub-*`.

### Grand-average summaries

```bash
python Dataset/Scripts/grand_average_analysis.py
```

Saves:

- grand-average retinotopy summaries
- grand-average orientation trigger summaries

### Group topomaps

```bash
python Dataset/Scripts/group_topomaps.py
```

Saves rebuilt alpha/gamma condition topomaps for:

- Full Field
- Left Hemifield
- Right Hemifield
- Upper Hemifield
- Lower Hemifield
- Blank
- Periphery
- Fovea

### Retinotopy summation/model fits

```bash
python Dataset/Scripts/retinotopy_model_fit.py
```

This script compares:

- linear part summation
- blank-corrected alpha summation
- fixed-sigma divisive-style summation

across:

- left/right
- top/bottom
- quadrants
- octants
- fovea/periphery

## Condition Mapping

Condition labels are defined in:

- [condition_mapping.json](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/condition_mapping.json)

Current status:

- retinotopy mapping is supported for codes `1-20`
- codes `21-22` are still unresolved
- orientation mapping is supported for `41-56`
- orientation and drift-direction bins are inferred from the paper figures

## What Still Needs Caution

These parts are still approximate relative to the paper:

- divisive-normalization model formula
- thresholded ERSP clustering instead of permutation-based clusters
- exact group-level ERSP pooling
- exact figure layout/styling
- exact montage fidelity for rebuilt topomaps

Practical caution from current testing:

- a full `sub-01` run now completes, but the orientation ERSP maps are still somewhat sparse/noisy
- if results look biologically weak, revisit ICA component selection before trusting downstream summaries
- single-subject ERSP outputs can be unstable even when the scripts run correctly

So the repo should currently be described as:

- **paper-aligned and substantially rebuilt**

not:

- **guaranteed exact reproduction**

## Notes

- Some older scripts and outputs remain in the repo from earlier stages of the project.
- The main README file in this repo is `Readme.md` with that exact casing.
- `eeg-env` appears to be a local virtual environment and would usually not be committed.
- The paper figure images you dragged into the repo are currently untracked helper files.
- See [PROJECT_TODO.md](/Volumes/personal/EEG/eeg_visual_simulation_lac/PROJECT_TODO.md) for the current status and remaining gaps.
