# EEG Visual Task – Preprocessing

This repository contains a complete EEG preprocessing and inspection pipeline for a visual task recorded in **BrainVision** format. The focus is on **artifact handling, ICA-based cleaning, and diagnostic visualization**

The pipeline is implemented using **MNE-Python** and is designed to be reproducible and easy to inspect step-by-step.

---

## Repository Structure

```
repo-root/
├── ds006547/                          # Raw BIDS dataset
│   └── sub-01/
│       └── ses-01/
│           └── eeg/
│               └── sub-01_ses-01_task-visual_eeg.vhdr
│
├── eeg_visual_simulation_lac/
│   └── Dataset/
│       ├── Scripts/
│       │   ├── preprocess.py          # Main preprocessing + ICA + Milestone 3 plots
│       │   ├── raw_visual.py           # Raw vs clean PSD and time-series plots
│       │   └── manual_inspect_ica.py   # ICA component inspection
│       │
│       └── outputs/
│           └── sub-01/                 # All generated outputs
│
└── README.md
```

---

## Requirements

- Python ≥ 3.9
- mne
- numpy
- scipy
- matplotlib

Optional (recommended):
- python-picard (for Picard ICA)

---

## Python Environment Setup

To ensure reproducibility, all scripts are intended to be run inside a dedicated Python virtual environment.

### Create a virtual environment

From the repository root:

```bash
python3 -m venv eeg-env
```

### Activate the environment

macOS / Linux:
```bash
source eeg-env/bin/activate
```

Windows:
```bash
eeg-env\\Scripts\\activate
```

After activation, the shell prompt should display `(eeg-env)`.

---

If `python-picard` is **not installed**, change the ICA method in `preprocess.py` from `picard` to `fastica`.

---


## Installing Dependencies

All required Python packages are listed in `requirements.txt`.

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Verify installation

```bash
python -c "import mne, numpy, matplotlib; print('Environment setup successful')"
```

If Picard ICA is required:

```bash
python -c "import picard; print('Picard ICA available')"
```

If `python-picard` is not installed, change the ICA method in `preprocess.py` from `picard` to `fastica`.

---

## Scripts Overview

### 1. `preprocess.py`

This is the **main preprocessing pipeline**.

It performs the following steps:

1. Load BrainVision EEG data (`.vhdr`)
2. Detect bad channels using **SSD** (10–100 Hz)
3. Interpolate detected bad channels
4. Apply notch filtering for line noise (50 Hz or 60 Hz)
5. Run **ICA** (Picard or FastICA)
6. Automatically detect eye-related components (EOG / frontal EEG)
7. Apply ICA and generate cleaned data
8. Epoch cleaned data
9. Generate **Milestone 3 diagnostic plots**
10. Save ICA solution and band-power features

#### Run command

From the repository root:

```bash
python eeg_visual_simulation_lac/Dataset/Scripts/preprocess.py \
  --vhdr ds006547/sub-01/ses-01/eeg/sub-01_ses-01_task-visual_eeg.vhdr \
  --out_dir eeg_visual_simulation_lac/Dataset/outputs/sub-01
```

#### Outputs

- `sub-01_ses-01_task-visual_eeg-ica.fif`  
- `sub-01_ses-01_task-visual_eeg-butterfly.png`  
- `sub-01_ses-01_task-visual_eeg-erp_<channel>.png`  
- `sub-01_ses-01_task-visual_eeg-alpha_diff.npy`  
- `sub-01_ses-01_task-visual_eeg-gamma_diff.npy`

---

### 2. `raw_visual.py`

This script is used for **data quality diagnostics**.

It generates:

- Raw EEG power spectral density (PSD)
- ICA-cleaned EEG PSD
- Fixed-scale 10-second raw EEG segment
- Fixed-scale 10-second clean EEG segment

The script ensures that raw and clean plots use:
- the **same time window**
- the **same channels**
- the **same amplitude scaling**

This makes visual comparison meaningful.

---

### 3. `manual_inspect_ica.py`

Utility script for **manual ICA inspection**.

- Plots ICA component topographies
- Helps identify eye-blink, muscle, and cardiac artifacts
- Supports manual selection of components to exclude

This script is typically run **before finalizing** `ica.exclude`.

---

## Preprocessing Pipeline Summary

1. Load BrainVision EEG data
2. Detect bad channels using SSD
3. Interpolate bad channels
4. Apply notch filtering for line noise at 60 Hz
5. Run ICA
6. Identify eye-related components
7. Apply ICA to raw data
8. Epoch cleaned data
9. Generate Milestone 3 diagnostic plots
10. Save ICA solution and band-power features

---

## Milestone 3 Plots

The following plots are generated automatically:

- Raw vs Clean **Power Spectral Density (PSD)**
- ICA component topographies
- **Butterfly plot** of evoked responses
- Single-channel ERP (Oz / O1 / O2 / Pz / Cz)
- 10-second raw EEG segment
- 10-second ICA-cleaned EEG segment

These plots are intended for **diagnostic inspection**, not statistical inference.

---

## Notes

- ICA primarily removes **transient artifacts** (eye blinks, muscle bursts), so PSDs may look similar before and after ICA.
- Line noise must be handled explicitly via notch filtering.
- Raw data is never modified in-place; all processing uses copies.
- Fixed scaling is used for time-series plots to allow fair comparison.

---

# The results presented here correspond to **Subject 01** from the dataset.


## Dataset

- **Dataset ID:** ds006547
- **Subject:** sub-01
- **Session:** ses-01
- **Task:** visual
- **Data format:** BrainVision EEG (.vhdr / .eeg / .vmrk)


## Results: Subject 01

### ICA Decomposition and Artifact Identification

Independent Component Analysis (ICA) was applied to the EEG data of **Subject 01**, producing 60 independent components. Visual inspection of the ICA scalp topographies revealed several components with spatial patterns characteristic of non-neural artifacts.

Multiple components showed strong frontal dominance, consistent with **eye-blink and eye-movement artifacts**. Additional components exhibited focal activity near temporal electrodes, indicative of **muscle (EMG) artifacts**. These components were marked for exclusion and removed from the data.

The remaining components displayed distributed and physiologically plausible scalp patterns, suggesting preservation of neural activity after artifact removal.

---

### Power Spectral Density (PSD): Raw vs Cleaned EEG

Power spectral density (PSD) estimates were computed for both the raw and ICA-cleaned EEG signals in the range **1–80 Hz**.

The PSD plots show that the overall spectral profile is preserved after ICA cleaning. The characteristic 1/f power decrease remains visible, and no major suppression of physiological frequency bands (alpha, beta, gamma) is observed. This indicates that ICA removed transient artifacts without altering the underlying spectral structure of the EEG.

---

### Time-Domain Inspection: Raw vs Cleaned EEG

Ten-second EEG segments were extracted from the raw and cleaned data using identical channels, time windows, and a fixed scaling of **20 µV**.

In the raw EEG, several channels exhibit high-amplitude transient fluctuations, particularly in frontal and temporal regions. After ICA cleaning, these fluctuations are substantially reduced while the background EEG activity remains intact. This confirms effective artifact attenuation by ICA.

---

### Evoked Responses: Butterfly Plot

Event-related potentials (ERPs) were computed by averaging **456 trials** across all **63 EEG channels**. The butterfly plot shows a clear stimulus-locked response following stimulus onset, with consistent temporal structure across channels.

No large baseline drifts or residual artifacts are observed, indicating stable preprocessing and baseline correction.

---

### Single-Channel ERP (Oz)

A single-channel ERP was visualized at electrode **Oz**, a posterior site associated with visual processing. The waveform shows a clear post-stimulus response with smooth temporal dynamics and no abrupt artifact-related deflections.

This confirms that ICA cleaning preserved meaningful neural responses while removing non-neural noise.

---

## Summary

For **Subject 01**, the preprocessing and analysis pipeline successfully:

- Identified and removed eye- and muscle-related artifacts using ICA
- Preserved the spectral characteristics of the EEG
- Reduced transient artifacts in the time domain
- Produced clean and interpretable evoked responses

The results demonstrate that the implemented pipeline is effective and suitable for subsequent EEG analysis.



# -------------------------------------------------------
# Milestone 4 – Condition-Based ERP Analysis

## Objective

The objective of **Milestone 4** is to analyze and compare **event-related potentials (ERPs)** between two experimental conditions using preprocessed EEG data. This milestone builds directly on **Milestone 3**, where artifact-free epochs were generated using ICA-based preprocessing. The focus here is on identifying **temporal and spatial differences** in brain responses evoked by the two conditions.

---

## Dataset and Preprocessing Recap

- **Dataset:** ds006547  
- **Subject:** sub-01  
- **Task:** visual  
- **EEG channels:** 63  
- **Epoch time window:** −0.5 s to 3.5 s relative to stimulus onset  
- **Total epochs:** 456

All EEG data were preprocessed in **Milestone 3**, including:

- Automatic bad channel detection and interpolation  
- Line noise removal (notch filtering)  
- ICA-based artifact removal  
- Epoching of cleaned continuous data

The final preprocessed epochs used for Milestone 4 are stored in:

```
sub-01_ses-01_task-visual_eeg-final-epo.fif
```

---

## Experimental Conditions

Epochs were divided into two experimental conditions based on event codes.

### Condition A

- **Event codes:** 1–22  
- **Number of epochs:** 264

### Condition B

- **Event codes:** 41–56  
- **Number of epochs:** 192

These two conditions correspond to different stimulus categories in the visual task.

---

## ERP Computation

For each condition, ERPs were computed by averaging all epochs belonging to that condition:

- **Condition A ERP:** average of 264 trials  
- **Condition B ERP:** average of 192 trials

All ERPs were computed using identical preprocessing parameters, baseline settings, and time windows to ensure a valid comparison.

---

## Butterfly Plots (All Channels)

### Purpose

Butterfly plots were generated to visualize ERP responses across **all 63 EEG channels simultaneously** for each condition.

### Observations

- Both conditions show clear stimulus-locked responses after stimulus onset.
- ERP waveforms are smooth and consistent across channels.
- The overall temporal structure is similar for both conditions.
- Subtle amplitude differences are visible between Condition A and Condition B.

### Interpretation

The butterfly plots confirm good signal quality and demonstrate that both conditions evoke reliable neural responses suitable for further comparison.

---

## Single-Channel ERP Comparison (Oz)

### Rationale

The electrode **Oz** was selected for detailed analysis because it is located over the **visual cortex**, which is highly relevant for a visual task.

### Analysis

- ERPs at Oz were extracted for both conditions.
- The two ERPs were plotted together using identical scaling.
- A difference waveform was computed as **Condition B − Condition A**.

### Observations

- Both conditions show a clear post-stimulus positive deflection.
- Condition B consistently shows a larger amplitude than Condition A.
- The difference waveform remains positive after stimulus onset.

### Interpretation

Condition B elicits stronger visual cortical activity than Condition A, suggesting enhanced visual processing or attentional engagement.

---

## Topographic Analysis

### Time Windows

Scalp topographies were computed for three post-stimulus time windows:

- **100–200 ms**  
- **200–300 ms**  
- **300–400 ms**

These windows capture early, intermediate, and later stages of visual processing.

---

### Condition-Specific Topographies

#### Condition A

- Voltage distributions show dominant posterior scalp activity.
- Spatial patterns remain stable across time windows.
- The distribution is consistent with visual cortex activation.

#### Condition B

- Similar posterior dominance is observed.
- Overall amplitudes are higher compared to Condition A.
- Spatial patterns remain physiologically plausible.

---

### Difference Topographies (Condition B − Condition A)

### Purpose

Difference maps were computed to highlight spatial regions where the two conditions differ.

### Observations

- Strongest differences appear over posterior electrodes.
- Differences increase in magnitude in later time windows.
- Spatial patterns align with the single-channel Oz ERP results.

### Interpretation

Condition B produces stronger posterior cortical responses than Condition A, confirming condition-dependent modulation of visual processing.

---

## Summary of Findings

- Both conditions evoke clear and reliable ERPs.
- Condition B consistently shows higher amplitudes than Condition A.
- Differences are observed both temporally (ERP waveforms) and spatially (topographic maps).
- Effects are localized to brain regions associated with visual processing.

---

## Conclusion

Milestone 4 successfully demonstrates condition-specific differences in EEG responses using ERP waveforms and scalp topographies. The results are physiologically meaningful, consistent across analyses, and validate the preprocessing pipeline established in Milestone 3. The analysis confirms that the experimental conditions modulate visual cortical activity in a systematic and interpretable manner.
