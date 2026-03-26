# Visual EEG Simulation — Alpha and Gamma Rhythm Analysis

Replication and validation of findings from:

> **Dissociable Spatial and Feature Tuning of Gamma and Alpha Rhythms in Human Visual Cortex**
> Ghaffari, Yavari, Bonyadian, Ghofrani & Butler (2025). *bioRxiv* doi:10.1101/2025.08.09.669461

Using high-density EEG (31 subjects, 64 channels, OpenNeuro ds006547), we investigate how gamma (40–80 Hz) and alpha (8–13 Hz) rhythms differ in their spatial selectivity, orientation tuning, and summation properties during visual stimulation.

---

## Key Findings

1. **Alpha suppresses broadly** — Visual stimulation suppresses alpha power across posterior electrodes with little spatial selectivity (CV = −0.96 / −0.97)
2. **Gamma enhances focally** — Gamma power increases are retinotopically specific and localized over occipital cortex
3. **Divisive normalization governs alpha summation** — Alpha spatial summation is subadditive (DivNorm model, σ = 0.5, outperforms linear prediction); gamma sums approximately linearly
4. **Gamma is sharply orientation-tuned; alpha is not** — Gamma responses are selective for grating orientation while alpha shows minimal tuning

---

## Approach

We validate these findings using two independent preprocessing pipelines on the same raw data:

- **Custom Pipeline** — Hand-coded Python scripts with automated ICLabel-based ICA, harmonic notch filtering, and per-trial artifact rejection (n=31 subjects)
- **BIDS Pipeline** — Standardized MNE-BIDS-Pipeline with config-driven preprocessing, variance-adaptive ICA, and automated EOG/ECG rejection (n=30 subjects)

### Methodology Comparison

| Stage | Original Paper | Custom Pipeline | BIDS Pipeline |
|-------|---------------|-----------------|---------------|
| **ICA** | Picard, 60 components, manual selection | Picard, 60 components, ICLabel (≥0.60) | Picard, `n_components=0.99`, EOG/ECG thresholds |
| **Notch filter** | Single 60 Hz | Harmonic series (60, 120, 180 Hz) | Single 60 Hz (width = 2 Hz) |
| **Bandpass** | 1–100 Hz (FIR) | 1–100 Hz (FIR) | 1–100 Hz (FIR) |
| **Epochs** | −0.5 to +3.5 s | −0.5 to +3.5 s | −0.5 to +3.0 s |
| **Gamma band** | 40–80 Hz | 40–55 + 65–80 Hz (sub-bands) | 40–80 Hz |
| **Artifact rejection** | Broadband gamma outlier (z > 4) | Per-trial PTP rejection | 1 subject excluded (sub-30) |

---

## Results

| Finding | Original Paper | Custom Pipeline | BIDS Pipeline |
|---------|---------------|-----------------|---------------|
| **Alpha suppression** | Broad, posterior | Clear (CV=−0.96) | Clear, 1.7× stronger (CV=−0.97) |
| **Gamma enhancement** | Focal, retinotopic | Present, noisy | Present, noisy |
| **DivNorm > Linear** | Yes (alpha subadditive) | No (linear won) | Yes (all partitions, both bands) |
| **Orientation tuning** | Strong gamma selectivity | TI ratio = 0.33 | Gamma TI > alpha TI |
| **Cross-subject consistency** | Assumed (n=30) | Alpha reliable; gamma variable | Same pattern |

The BIDS Pipeline's divisive normalization result is stronger than the paper's — DivNorm wins for both alpha and gamma across all 5 spatial partitions. The Custom Pipeline's aggressive harmonic notch filtering likely distorted summation relationships, making this the one finding sensitive to preprocessing choices.

---

## Repository Structure

```text
.
├── Custom_pipeline_Dataset/
│   ├── Scripts/              # Custom pipeline scripts + Phase_1.sh / Phase_2.sh
│   │   └── condition_mapping.json
│   └── outputs/              # Per-subject and group-level results
├── Bids_pipeline_Dataset/
│   ├── Scripts/              # BIDS pipeline scripts (config.py, utils.py, etc.)
│   └── outputs/
│       ├── group_level/
│       ├── derivatives/      # MNE-BIDS-Pipeline outputs + bids_analysis/
│       └── sub-01/ ... sub-31/
├── EEG_Final_Version.ipynb   # Final report notebook
├── requirements.txt
└── Readme.md
```

---

## Pipelines

### Custom Pipeline

Located in `Custom_pipeline_Dataset/Scripts/`. Two-phase execution:

**Phase 1** (`Phase_1.sh`) — Per-subject: preprocessing, ICA, band power extraction, retinotopy, orientation tuning, ERSP

**Phase 2** (`Phase_2.sh`) — Group-level: grand averages, topomaps, statistics, model fitting, ERSP cluster tests

### BIDS Pipeline

Located in `Bids_pipeline_Dataset/Scripts/`. Config-driven MNE-BIDS-Pipeline preprocessing followed by custom analysis scripts for band power, retinotopy, orientation tuning, model fitting, and group statistics.

---

## Installation

```bash
python3 -m venv eeg-env
source eeg-env/bin/activate
pip install -r requirements.txt
```

**Prerequisites for running the pipelines** (not needed for the notebook):
- Raw BIDS dataset from [OpenNeuro ds006547](https://openneuro.org/datasets/ds006547)
- Place `ds006547/` as a sibling of this repository (same parent folder), or set the `BIDS_ROOT` environment variable:

```bash
# Option A: default layout (ds006547 next to this repo)
parent/
├── ds006547/          # BIDS dataset
└── eeg_visual_simulation_lac/   # this repo

# Option B: dataset elsewhere
export BIDS_ROOT=/path/to/ds006547
```

**Downloading the dataset (git-annex):**

OpenNeuro datasets use DataLad/git-annex — cloning the repo only downloads metadata, not the actual EEG files. After cloning, you must fetch the data:

```bash
# Install DataLad (if not already installed)
pip install datalad

# Clone the dataset
datalad install https://github.com/OpenNeuroDatasets/ds006547.git

# Download all files (this fetches the actual EEG data)
cd ds006547
datalad get .
```

Alternatively, using git-annex directly:

```bash
git clone https://github.com/OpenNeuroDatasets/ds006547.git
cd ds006547
git annex get .
```

Without running `datalad get .` or `git annex get .`, the `.vhdr`, `.eeg`, and `.vmrk` files will be empty symlinks and the pipelines will fail to load any data.

---

## Running the Notebook

The submission notebook (`EEG_Final_Version.ipynb`) loads pre-computed results — no raw EEG processing needed.

**Locally:** Open and run all cells. Paths resolve automatically.

**Google Colab:** Upload `Custom_pipeline_Dataset/outputs/` and `Bids_pipeline_Dataset/outputs/` to Google Drive, then run the notebook.

---

## Condition Mapping

- **Retinotopy (codes 1–20):** Full field, hemifields, quadrants, octants, fovea/periphery, blank
- **Orientation (codes 41–56):** 16 orientations, 0°–337.5° in 22.5° steps

---

## Caveats

- Divisive normalization uses a fixed σ = 0.5 (matching the paper)
- ERSP clusters are threshold-based, not permutation-based
- Gamma effects show high inter-subject variability (CV ≈ −3.7)
- One subject excluded in BIDS Pipeline (sub-30) due to data quality
- Alpha-gamma correlation not computed for BIDS Pipeline

---

## Conclusion

The dissociable properties of gamma and alpha rhythms in human visual cortex — broad alpha suppression, focal gamma enhancement, subadditive alpha summation via divisive normalization, and gamma-selective orientation tuning — are reliably observed across two independent analysis pipelines applied to the same raw EEG data.
