# Project TODO: Align The EEG Pipeline With The Paper

This document tracks what has already been rebuilt in the repository and what still needs work to match the paper more closely.

Reference paper:
`Dissociable Spatial and Feature Tuning of Gamma and Alpha Rhythms in Human Visual Cortex`

## Main Goal

The goal of this project is to reproduce the paper's central dissociation:

- gamma enhancement is spatially and feature tuned
- alpha suppression is broader and less feature selective
- gamma summation is closer to linear
- alpha summation is more consistent with divisive normalization

## What Is Rebuilt

### Core preprocessing

Done:

- [Dataset/Scripts/preprocess.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/preprocess.py)
  - bad-channel detection using `10-100 Hz` SSD z-scores
  - interpolation of bad channels
  - `60 Hz` notch filtering
  - ICA-prep filtering at `1-100 Hz`
  - resampling to `200 Hz`
  - event-centered ICA training epochs
  - ICA fitting and saved summaries

### ICA review and application

Done:

- [Dataset/Scripts/manual_inspect_ica.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/manual_inspect_ica.py)
  - generates ICA review figures
  - creates/updates a component review JSON

- [Dataset/Scripts/apply_reviewed_ica.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/apply_reviewed_ica.py)
  - applies reviewed ICA decisions
  - reconstructs cleaned sensor-space EEG
  - saves cleaned raw and epochs
  - saves QC outputs

### Sensor-space alpha/gamma extraction

Done:

- [Dataset/Scripts/extract_band_power.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/extract_band_power.py)
  - alpha `8-13 Hz`
  - gamma `40-80 Hz`
  - analytic amplitude via Hilbert transform
  - `|task| - |baseline|` using `0-3 s` vs `-0.5-0 s`
  - saves per-trial, per-condition, and mean outputs

### Condition mapping

Done:

- [Dataset/Scripts/condition_mapping.json](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/condition_mapping.json)
  - retinotopy mapping for codes `1-20`
  - unresolved retinotopy codes `21-22`
  - orientation mapping for codes `41-56`
  - orientation and drift-direction groupings inferred from the paper figures

### Subject-level summary analyses

Done:

- [Dataset/Scripts/condition_analysis.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/condition_analysis.py)
  - retinotopy alpha/gamma summaries
  - alpha-vs-gamma scatter and residuals

- [Dataset/Scripts/orientation_tuning_analysis.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/orientation_tuning_analysis.py)
  - trigger-level orientation summaries
  - grouped orientation and direction summaries
  - alpha-vs-gamma scatter plots
  - pairwise Welch t-test heatmaps

### ERSP extraction and orientation statistics

Done:

- [Dataset/Scripts/extract_component_ersp.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/extract_component_ersp.py)
  - extracts retained ICA source epochs
  - computes Morlet ERSPs `4-100 Hz`
  - crops to `-1.0 to 4.0 s`
  - baseline-corrects each trial using `-0.5 to 0 s`

- [Dataset/Scripts/orientation_ersp_stats.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/orientation_ersp_stats.py)
  - broadband outlier rejection using `80-100 Hz`, `0-3 s`, `|z| > 4`
  - Gaussian smoothing
  - pixelwise ANOVA across triggers `41-56`
  - thresholded cluster mask at `p < 0.01`
  - cluster-averaged trigger summaries
  - frequency-frequency correlation matrix

### Group-level analyses

Done:

- [Dataset/Scripts/grand_average_analysis.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/grand_average_analysis.py)
  - aggregates subject-level retinotopy summaries
  - aggregates orientation trigger responses

- [Dataset/Scripts/group_topomaps.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/group_topomaps.py)
  - rebuilds condition-wise grand-average alpha/gamma topomaps

- [Dataset/Scripts/retinotopy_model_fit.py](/Volumes/personal/EEG/eeg_visual_simulation_lac/Dataset/Scripts/retinotopy_model_fit.py)
  - compares linear vs divisive-style retinotopy summation
  - includes blank-corrected alpha comparison

## What Still Does Not Fully Match The Paper

### 1. Exact statistical fidelity

Still needed:

- permutation-based cluster testing instead of the current simple thresholded clustering
- confirmation that the ANOVA structure matches the paper's exact repeated-measures implementation
- confirmation that the pairwise tests match the authors' exact grouping procedure

### 2. Exact divisive-normalization model

Still needed:

- verify the precise DivNorm formula used in the paper
- confirm whether the current fixed-sigma approximation is mathematically identical to the original analysis

Current state:

- the repo now has a paper-aligned approximation
- it should not yet be described as an exact reimplementation of the model fit

### 3. Retinotopy code completeness

Still needed:

- resolve the meaning of trigger codes `21` and `22`
- confirm the exact original event table from raw data or experiment code

Current state:

- the figure-supported retinotopy mapping covers `1-20`
- `21-22` remain unresolved on purpose

### 4. Full paper figure replication

Still needed:

- exact panel layout matching the paper figures
- exact text labels, axis limits, and figure styling
- direct reproduction of all figure panels from a fresh rerun

Current state:

- the repo now generates many paper-style outputs
- it is closer in analysis logic than in visual exactness

### 5. Group-level ERSP pooling across subjects

Still needed:

- pooled multi-subject ERSP statistics
- subject-level alignment and aggregation strategy for component-space ERSPs

Current state:

- ERSP statistics are implemented at the subject-analysis stage
- full across-subject ERSP aggregation is not yet rebuilt

### 6. Exact electrode/topomap fidelity

Still needed:

- verify that the montage used for rebuilt topomaps matches the original study setup exactly

Current state:

- rebuilt topomaps use channel-name-based montage reconstruction
- this is reasonable, but may not be pixel-identical to the paper

## Recommended Next Priorities

### Highest priority

1. Validate the rebuilt pipeline on one real subject from start to finish.
2. Confirm trigger codes `21` and `22`.
3. Verify the divisive-normalization formula against the original analysis or supplement.
4. Decide whether thresholded cluster masks are sufficient for your course/project, or whether you need permutation-based clusters.

### Medium priority

1. Add pooled across-subject ERSP aggregation.
2. Tighten figure formatting to look more like the paper.
3. Add coverage checks so missing subject outputs are reported more explicitly.

### Lower priority

1. Clean the repo for publication.
2. Remove local environment artifacts and temporary files.
3. Finalize README and usage docs once the pipeline is stable.

## Practical Reality Check

Right now the repo is in a much stronger place than it was:

- the core pipeline is rebuilt
- several previously broken paper-facing scripts are now working Python
- condition mapping is mostly recovered from the paper figures
- subject-level and group-level outputs can now be regenerated in a structured way

But the repo should still be described as:

- **paper-aligned and substantially rebuilt**

Not yet as:

- **guaranteed exact reproduction of the published analysis**

## Definition Of "Good Enough"

The project is close enough to the paper for a strong class/research presentation when:

- one subject can be run end-to-end with the rebuilt scripts
- the outputs qualitatively resemble the paper
- gamma vs alpha dissociation is visible
- retinotopy and orientation groupings are documented and defensible
- model-fit conclusions are presented as approximate unless formula fidelity is confirmed

The project is fully paper-matched only when:

- event mappings are fully confirmed
- the DivNorm model is verified
- cluster statistics are method-matched
- group-level ERSP analyses are reproduced from source
