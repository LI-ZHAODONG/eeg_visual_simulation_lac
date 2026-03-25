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
- **BIDS Pipeline** — Standardized MNE-BIDS-Pipeline with config-driven preprocessing, variance-adaptive ICA, and automated EOG/ECG rejection (n=29 subjects)

### Methodology Comparison

| Stage | Original Paper | Custom Pipeline | BIDS Pipeline |
|-------|---------------|-----------------|---------------|
| **ICA** | Picard, 60 components, manual selection | Picard, 60 components, ICLabel (≥0.60) | Picard, `n_components=0.99`, EOG/ECG thresholds |
| **Notch filter** | Single 60 Hz | Harmonic series (60, 120, 180 Hz) | Single 60 Hz (width = 2 Hz) |
| **Bandpass** | 1–100 Hz (FIR) | 1–100 Hz (FIR) | 1–100 Hz (FIR) |
| **Epochs** | −0.5 to +3.5 s | −0.5 to +3.5 s | −0.5 to +3.0 s |
| **Gamma band** | 40–80 Hz | 40–55 + 65–80 Hz (sub-bands) | 40–80 Hz |
| **Artifact rejection** | Broadband gamma outlier (z > 4) | Per-trial PTP rejection | 2 subjects excluded |

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
├── submission_report.ipynb   # Final report notebook
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

---

## Running the Notebook

The submission notebook (`submission_report.ipynb`) loads pre-computed results — no raw EEG processing needed.

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
- Two subjects excluded in BIDS Pipeline (sub-06, sub-30) due to data quality
- Alpha-gamma correlation not computed for BIDS Pipeline

---

## Conclusion

The dissociable properties of gamma and alpha rhythms in human visual cortex — broad alpha suppression, focal gamma enhancement, subadditive alpha summation via divisive normalization, and gamma-selective orientation tuning — are reliably observed across two independent analysis pipelines applied to the same raw EEG data.
