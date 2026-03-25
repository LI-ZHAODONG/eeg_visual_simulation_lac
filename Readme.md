# EEG Visual Simulation — Dissociable Spatial & Feature Tuning

An EEG analysis pipeline replicating the methods from:

> **Dissociable Spatial and Feature Tuning of Gamma and Alpha Rhythms in Human Visual Cortex**

Built with Python, [MNE](https://mne.tools/), NumPy, SciPy, and Matplotlib.  
Dataset: [OpenNeuro ds006547](https://openneuro.org/datasets/ds006547) (31 subjects, BrainVision/BIDS format).

---

## Results Overview

All 31 subjects were processed end-to-end through two automated phases.

### Retinotopy — Spatial Tuning

| Condition | Alpha Mean | Gamma Mean |
|-----------|-----------|-----------|
| Full Field | −8.96 × 10⁻⁷ | −4.94 × 10⁻⁸ |
| Left Hemifield | −1.05 × 10⁻⁶ | — |
| Periphery | −1.10 × 10⁻⁶ | — |
| Fovea | −6.36 × 10⁻⁷ | — |
| Blank | ≈ 0 | ≈ 0 |

- Strongest alpha suppression in periphery and contralateral hemifields
- Blank condition confirms valid baseline (near-zero power change)

### Divisive Normalization vs Linear Summation

The divisive-normalization model (σ = 0.5) consistently outperforms linear summation at finer spatial scales:

| Spatial Partition | Linear MAE | DivNorm MAE | Improvement |
|-------------------|-----------|-------------|-------------|
| Left / Right | 2.34 × 10⁻⁶ | 1.19 × 10⁻⁶ | ~2× |
| Top / Bottom | 2.20 × 10⁻⁶ | 1.18 × 10⁻⁶ | ~2× |
| Quadrants | 4.15 × 10⁻⁶ | 1.06 × 10⁻⁶ | ~4× |
| Octants | 1.08 × 10⁻⁵ | 1.20 × 10⁻⁶ | **~9×** |
| Fovea / Periphery | 2.47 × 10⁻⁶ | 1.23 × 10⁻⁶ | ~2× |

### Orientation Tuning

- **Alpha tuning index:** 1.29 — strong selectivity across 16 orientations
- **Gamma tuning index:** 0.43 — moderate selectivity
- **Tuning ratio (γ/α):** 0.33 — alpha shows ~3× stronger orientation tuning than gamma
- 16 orientation bins (0°–337.5° in 22.5° steps, triggers 41–56)

### Cross-Subject Consistency (n = 31)

| Metric | Mean | Std | CV |
|--------|------|-----|-----|
| Alpha effect | −1.11 × 10⁻⁶ | 1.07 × 10⁻⁶ | −0.96 |
| Gamma effect | −1.45 × 10⁻⁷ | 5.35 × 10⁻⁷ | −3.69 |

Alpha effects are consistent (|CV| < 1); gamma effects show high inter-subject variability.

---

## Google Colab / Google Drive

The full pipeline outputs (all 31 subjects) are available on Google Drive:

**[Dataset Outputs (Google Drive)](https://drive.google.com/drive/folders/1K8gK-mCERqrjj5tTC1TM29rqIMFqF5pz?usp=sharing)**

To run `submission_report.ipynb` on Colab:

1. Open the shared folder link above
2. Right-click → *Organise* → *Add shortcut* → place it inside `My Drive/eeg_visual_simulation_lac/`
3. Open the notebook in Colab and run all cells — Drive will be mounted automatically

---

## Pipeline Architecture

### Phase 1 — Per-Subject Processing (automated)

```bash
bash Dataset/Scripts/Phase_1.sh
```

| Step | Script | Description |
|------|--------|-------------|
| 1 | `preprocess.py` | Channel typing, bad-channel detection, notch filter, 1–100 Hz bandpass, downsample to 200 Hz, ICA fit (Picard, 60 components) |
| 2 | `auto_inspect_ica.py` | Automatic ICA labelling via `mne-icalabel` (threshold 0.60) |
| 3 | `refine_ica_review.py` | Heuristic refinement of borderline ICA decisions |
| 4 | `apply_reviewed_ica.py` | Apply exclusions, save cleaned raw + epochs + PSD QC |
| 5 | `extract_band_power.py` | Alpha (8–13 Hz) and gamma (40–80 Hz) analytic amplitude; task − baseline |
| 6 | `condition_analysis.py` | Per-subject retinotopy summaries and scatter plots |
| 7 | `orientation_tuning_analysis.py` | Orientation tuning summaries, t-test heatmaps |
| 8 | `extract_component_ersp.py` | Morlet ERSP (4–100 Hz), buffered epochs, baseline-corrected |
| 9 | `orientation_ersp_stats.py` | ANOVA across orientation triggers, cluster masks |

### Phase 2 — Group-Level Analysis (automated)

```bash
bash Dataset/Scripts/Phase_2.sh
```

| Step | Script | Description |
|------|--------|-------------|
| 1 | `grand_average_analysis.py` | Grand-average retinotopy & orientation summaries |
| 2 | `group_topomaps.py` | Condition-wise alpha/gamma scalp topomaps |
| 3 | `group_statistical_analysis.py` | Group orientation/retinotopy statistics, consistency metrics |
| 4 | `retinotopy_model_fit.py` | Linear vs divisive-normalization model comparison |
| 5 | `group_ersp_statistics.py` | Group ERSP cluster statistics |

---

## Repository Layout

```text
.
├── Dataset/
│   ├── Scripts/           # All analysis scripts + Phase_1.sh / Phase_2.sh
│   │   └── condition_mapping.json
│   └── outputs/
│       ├── group_level/   # Group-level PNGs + JSONs
│       ├── sub-01/        # Full example subject (PNGs + JSONs)
│       ├── sub-02/        # JSON summaries only (PNGs on Google Drive)
│       ├── ...
│       └── sub-31/
├── submission_report.ipynb  # Colab-ready final report
├── Readme.md
└── requirements.txt
```

## Installation

```bash
python3 -m venv eeg-env
source eeg-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Prerequisites for running the pipeline** (not needed for the notebook):
- Raw BIDS dataset from [OpenNeuro ds006547](https://openneuro.org/datasets/ds006547)
- Preprocessed ICA files (`*-ica.fif`) for Phase 1

## Condition Mapping

Condition labels are defined in `Dataset/Scripts/condition_mapping.json`:

- **Retinotopy:** codes 1–20 (hemifields, quadrants, octants, fovea/periphery, blank)
- **Orientation:** codes 41–56 (16 orientations, 0°–337.5° in 22.5° steps)

## Caveats

This pipeline is **paper-aligned and substantially complete**, but not a guaranteed exact reproduction:

- Divisive-normalization uses a fixed σ = 0.5 approximation
- ERSP clusters are threshold-based, not permutation-based
- Gamma effects show high inter-subject variability (CV ≈ −3.7)
- Retinotopy trigger codes 21–22 remain unresolved
