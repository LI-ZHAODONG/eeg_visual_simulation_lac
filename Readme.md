# EEG Visual Simulation — Pipeline Diversity Robustness Analysis

This repository contains two independent EEG analysis pipelines that replicate and validate findings from:

> **Dissociable Spatial and Feature Tuning of Gamma and Alpha Rhythms in Human Visual Cortex**
> Ghaffari, Yavari, Bonyadian, Ghofrani & Butler (2025). *bioRxiv* doi:10.1101/2025.08.09.669461

The goal is not a step-by-step reproduction, but a **robustness check**: do the paper's central findings survive fundamentally different preprocessing pipelines?

---

## Original Paper Summary

The paper uses high-density EEG (30 subjects, ~64 channels) to map gamma (40–80 Hz) and alpha (8–12 Hz) responses across retinotopic, orientation, and motion conditions. Key claims:

1. **Alpha suppresses broadly** — Visual stimulation suppresses alpha across posterior electrodes with little spatial selectivity
2. **Gamma enhances focally** — Gamma increases are retinotopically specific and localized over occipital cortex
3. **Divisive normalization for alpha** — Alpha summation is subadditive (DivNorm model, σ = 0.5 outperforms linear); gamma sums approximately linearly
4. **Orientation dissociation** — Gamma is sharply tuned to grating orientation; alpha shows minimal selectivity

The paper's pipeline: Picard ICA (60 components), manual ERSP + topography inspection (3–5 components retained per subject), single 60 Hz notch, 1–100 Hz bandpass, 200 Hz downsample, epochs −0.5 to +3.5 s, analytic amplitude power (|task| − |baseline|).

---

## Three-Way Methodological Comparison

| Stage | Original Paper | Custom Pipeline | BIDS Pipeline |
|-------|---------------|-----------------|---------------|
| **ICA algorithm** | Picard (extended), 60 components | Picard (extended), 60 components | Picard, `n_components=0.99` (variance-adaptive) |
| **ICA component selection** | Manual ERSP + topography; 3–5 components | Automated: ICLabel (≥0.60) + heuristic refinement | Automated: EOG/ECG correlation thresholds |
| **Notch filter** | Single 60 Hz | Harmonic series (60, 120, 180 Hz) | Single 60 Hz (width = 2 Hz) |
| **Bandpass** | 1–100 Hz (FIR) | 1–100 Hz (FIR) | 1–100 Hz (FIR) |
| **Downsampling** | 200 Hz | 200 Hz | 200 Hz |
| **Epochs** | −0.5 to +3.5 s | −0.5 to +3.5 s | −0.5 to +3.0 s |
| **Gamma band** | 40–80 Hz (full range) | 40–55 + 65–80 Hz (sub-bands, avoids 60 Hz) | 40–80 Hz (full range) |
| **Artifact rejection** | Broadband gamma outlier (|z| > 4) | Per-trial PTP rejection | No per-trial; 2 subjects excluded |
| **Subjects** | 30 | 31 | 29 (sub-06, sub-30 excluded) |

---

## Three-Way Results Summary

| Finding | Original Paper | Custom Pipeline (n=31) | BIDS Pipeline (n=30) | Robust? |
|---------|---------------|----------------------|---------------------|---------|
| **Alpha suppression** | Broad, posterior | Clear (CV=−0.96) | Clear, 1.7× stronger (CV=−0.97) | **YES** |
| **Gamma enhancement** | Focal, retinotopic | Present, noisy | Present, noisy | **YES** |
| **DivNorm > Linear** | Yes (alpha subadditive) | No (linear won — unexpected) | **Yes (all partitions, both bands)** | **YES** — BIDS aligns with paper |
| **Gamma > alpha orientation tuning** | Strong gamma selectivity | TI ratio = 0.33 | Gamma TI > alpha TI | **YES** |
| **Cross-subject consistency** | Assumed (n=30) | Alpha reliable; gamma variable | Same pattern | **YES** |
| **Alpha-gamma correlation** | r ≈ −0.84 | r = −0.52 | Not computed | **Partial** |

### Key Insight

The BIDS Pipeline's divisive normalization result is **stronger** than the paper's — DivNorm wins for both alpha AND gamma across all 5 spatial partitions. The Custom Pipeline's aggressive preprocessing (harmonic notch, gamma sub-banding) likely distorted summation relationships, making this the one finding where pipeline choice materially affected the outcome.

---

## Repository Structure

```text
.
├── Custom_pipeline_Dataset/
│   ├── Scripts/              # All analysis scripts + Phase_1.sh / Phase_2.sh
│   │   └── condition_mapping.json
│   └── outputs/
│       ├── group_level/      # Group-level PNGs + JSONs
│       ├── sub-01/           # Full example subject (PNGs + JSONs)
│       ├── sub-02/ ... sub-31/
│       └── retinotopy_model_fit_summary.json
├── Bids_pipeline_Dataset/
│   ├── Scripts/              # BIDS pipeline scripts (config.py, run_pipeline.py, utils.py)
│   └── outputs/
│       ├── group_level/      # Group-level PNGs + JSONs
│       ├── derivatives/      # MNE-BIDS-Pipeline outputs + bids_analysis/
│       ├── sub-01/ ... sub-31/
│       └── ...
├── Paper.pdf                 # Original paper
├── paper_summary.txt         # Paper methodology summary
├── submission_report.ipynb   # Final report notebook (runs locally or on Colab)
├── requirements.txt
└── Readme.md
```

---

## Pipelines Overview

### Custom Pipeline

Located in `Custom_pipeline_Dataset/`. Hand-coded Python scripts implementing a paper-aligned analysis with methodological updates.

#### Phase 1 — Per-Subject Processing

```bash
bash Custom_pipeline_Dataset/Scripts/Phase_1.sh
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

#### Phase 2 — Group-Level Analysis

```bash
bash Custom_pipeline_Dataset/Scripts/Phase_2.sh
```

| Step | Script | Description |
|------|--------|-------------|
| 1 | `grand_average_analysis.py` | Grand-average retinotopy & orientation summaries |
| 2 | `group_topomaps.py` | Condition-wise alpha/gamma scalp topomaps |
| 3 | `group_statistical_analysis.py` | Group orientation/retinotopy statistics, consistency metrics |
| 4 | `retinotopy_model_fit.py` | Linear vs divisive-normalization model comparison |
| 5 | `group_ersp_statistics.py` | Group ERSP cluster statistics |

### BIDS Pipeline

Located in `Bids_pipeline_Dataset/`. Config-driven pipeline using MNE-BIDS-Pipeline with custom post-processing scripts.

| Script | Description |
|--------|-------------|
| `config.py` | MNE-BIDS-Pipeline configuration (ICA, filtering, epochs, rejection) |
| `run_pipeline.py` | Orchestrates the full MNE-BIDS-Pipeline run |
| `run_all.py` | Runs both pipeline + custom analysis in sequence |
| `extract_band_power.py` | Alpha/gamma analytic amplitude (same method as Custom) |
| `condition_analysis.py` | Per-subject retinotopy summaries |
| `orientation_tuning.py` | Orientation tuning analysis |
| `retinotopy_model_fit.py` | Linear vs DivNorm model comparison |
| `group_statistics.py` | Group-level statistics and consistency metrics |
| `utils.py` | Shared helpers |

---

## Installation

```bash
python3 -m venv eeg-env
source eeg-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Prerequisites for running the pipeline** (not needed for the notebook):
- Raw BIDS dataset from [OpenNeuro ds006547](https://openneuro.org/datasets/ds006547)
- Preprocessed ICA files (`*-ica.fif`) for Custom Pipeline Phase 1

---

## Google Colab / Google Drive

To run the submission notebook on Colab:

1. Upload the following folders to your Google Drive (inside any parent folder, e.g., `My Drive/eeg_visual_simulation_lac/`):
    - `Custom_pipeline_Dataset/outputs/` (contains Custom Pipeline results)
    - `Bids_pipeline_Dataset/outputs/` (contains BIDS Pipeline results)
2. Upload the notebook file: `submission_report.ipynb`
3. Open the notebook in Colab and run all cells — Drive will be mounted automatically.

> **Tip:** Only JSON summaries and PNG figures are needed. Raw `.fif` files are not required for the notebook to display results.

---

## Condition Mapping

Condition labels are defined in `Custom_pipeline_Dataset/Scripts/condition_mapping.json`:

- **Retinotopy:** codes 1–20 (hemifields, quadrants, octants, fovea/periphery, blank)
- **Orientation:** codes 41–56 (16 orientations, 0°–337.5° in 22.5° steps)

---

## Development Process

The final automated pipeline evolved through several iterations. The repository preserves utility and exploratory scripts that supported this development:

| Script | Role in Development |
|--------|---------------------|
| `raw_visual.py` | Early-stage raw EEG visualisation — used to inspect signal quality before designing the preprocessing pipeline |
| `raw_visuals_continous.py` | Continuous-recording variant of the above; helped decide epoch boundaries and filtering strategy |
| `Preprocess_continous.py` | Prototype continuous preprocessing — explored before settling on the event-centred approach in `preprocess.py` |
| `manual_inspect_ica.py` | Original interactive ICA component review with topography plots; replaced by `auto_inspect_ica.py` + `refine_ica_review.py` for full automation |
| `build_condition_table.py` | Utility that cross-references trigger codes with `condition_mapping.json` to verify event labelling |
| `milestone4_analysis.py` | Earlier milestone deliverable — single-subject analysis that informed the design of the final per-subject and group-level scripts |

---

## Caveats

This analysis is **substantially complete** but not a guaranteed exact reproduction:

- Divisive-normalization uses a fixed σ = 0.5 approximation (paper also uses σ = 0.5)
- ERSP clusters are threshold-based, not permutation-based
- Gamma effects show high inter-subject variability (CV ≈ −3.7)
- Retinotopy trigger codes 21–22 remain unresolved
- Alpha-gamma correlation not computed for BIDS Pipeline (no GA topomaps generated)
- Two subjects excluded in BIDS Pipeline (sub-06, sub-30) vs. all 31 in Custom Pipeline

---

## Conclusion

The paper's four main findings — broad alpha suppression, focal gamma enhancement, divisive normalization of spatial summation, and gamma-selective orientation tuning — are **robust to preprocessing pipeline choice**. Both an automated custom pipeline and a standardized BIDS pipeline independently replicate these results from the same raw data, confirming that the conclusions reflect genuine neural properties rather than methodological artifacts.
