# Phase 2: Statistical Quantification Pipeline

After all subject-level analyses are complete, run these scripts in order to generate group-level statistics and validation metrics.

---

## Prerequisites

- All subjects must have completed these files:
  - `*-alpha_by_condition.npz`
  - `*-gamma_by_condition.npz`
  - `*-band_power_summary.json`
  - `*-orientation_ersp_stats.json` (if available)

---

## Command Sequence

### Step 1: Run Grand Average (existing script)

```bash
python Dataset/Scripts/grand_average_analysis.py \
  --outputs-dir Dataset/outputs \
  --mapping Dataset/Scripts/condition_mapping.json
```

**Outputs:**
- `grand_average_summary.json` - aggregated summaries
- Figure files for group topomaps

---

### Step 2: Run Group Topomaps (existing script)

```bash
python Dataset/Scripts/group_topomaps.py \
  --outputs-dir Dataset/outputs \
  --mapping Dataset/Scripts/condition_mapping.json
```

**Outputs:**
- `group_topomap_summary.json` - channel-space mappings
- PNG figures of group topographies

---

### Step 3: Run Retinotopy Model Fit (existing script)

```bash
python Dataset/Scripts/retinotopy_model_fit.py \
  --outputs-dir Dataset/outputs \
  --mapping Dataset/Scripts/condition_mapping.json
```

**Outputs:**
- `retinotopy_model_fit_summary.json` - linear vs divisive model comparison
- PNG figures comparing models

---

### Step 4: NEW - Run Statistical Quantification

```bash
python Dataset/Scripts/group_statistical_analysis.py \
  --outputs-dir Dataset/outputs \
  --mapping Dataset/Scripts/condition_mapping.json
```

**Outputs:**
- `group_retinotopy_statistics.json` - Alpha/gamma by condition (mean ± SEM)
- `group_orientation_statistics.json` - Tuning indices and comparisons
- `group_model_fit_comparison.json` - Model predictions vs observed

**What this computes:**
- Quantitative alpha/gamma tables for all retinotopy conditions
- Orientation tuning selectivity indices (gamma vs alpha)
- Linear summation predictions
- Divisive normalization predictions
- Error metrics for each model

---

### Step 5: NEW - Run ERSP/Cluster Aggregation

```bash
python Dataset/Scripts/group_ersp_statistics.py \
  --outputs-dir Dataset/outputs
```

**Outputs:**
- `group_ersp_cluster_statistics.json` - Cluster stats per subject
- `group_consistency_metrics.json` - Cross-subject reliability

**What this computes:**
- ERSP cluster effect sizes
- Cross-subject consistency metrics (coefficient of variation)
- Reliability assessment

---

## Output JSON Structure

### `group_retinotopy_statistics.json`

```json
{
  "summary_table": [
    {
      "condition": "full",
      "alpha_mean": -0.215,
      "alpha_sem": 0.042,
      "gamma_mean": 0.185,
      "gamma_sem": 0.031,
      "n_subjects": 30
    },
    ...
  ]
}
```

Use for: Building quantitative tables and comparison plots

---

### `group_orientation_statistics.json`

```json
{
  "orientation_codes": [41, 42, ..., 56],
  "alpha_by_code": {"41": [...], ...},
  "gamma_by_code": {"41": [...], ...},
  "gamma_tuning_index": 0.642,
  "alpha_tuning_index": 0.185,
  "tuning_index_ratio_gamma_to_alpha": 3.47
}
```

Use for: Tuning curve plots and dissociation claims

---

### `group_model_fit_comparison.json`

```json
{
  "linear_summation": {
    "alpha_prediction": -0.185,
    "gamma_prediction": 0.156,
    "alpha_error": 0.030,
    "gamma_error": 0.029
  },
  "divisive_normalization": {
    "alpha_prediction": -0.210,
    "gamma_prediction": 0.172,
    "alpha_error": 0.005,
    "gamma_error": 0.013,
    "sigma": 0.5
  },
  "model_comparison": {
    "linear_total_error": 0.059,
    "divnorm_total_error": 0.018,
    "divnorm_advantage": "yes"
  }
}
```

Use for: Model comparison plots and validation

---

### `group_consistency_metrics.json`

```json
{
  "alpha_effect_mean": -0.215,
  "alpha_effect_std": 0.087,
  "alpha_reliability_cv": 0.404,
  "gamma_effect_mean": 0.158,
  "gamma_effect_std": 0.053,
  "gamma_reliability_cv": 0.335,
  "n_subjects_with_alpha_data": 30,
  "n_subjects_with_gamma_data": 30
}
```

Use for: Assessing effect consistency and reliability

---

## Next: Integration into Report

Once all Phase 2 scripts complete, these JSON files will be loaded in the notebook to:

1. Create **quantitative comparison tables** with error bars
2. Plot **model predictions vs observations**
3. Test **alpha/gamma dissociation** with statistics
4. Validate **paper claims** with numerical evidence
5. Generate **figures with annotations** (p-values, effect sizes)

---

## Troubleshooting

**No output files generated:**
- Check that subject directories exist: `Dataset/outputs/sub-01`, `sub-02`, etc.
- Verify files exist: `*-alpha_by_condition.npz`, `*-gamma_by_condition.npz`

**Error: "No subjects found":**
- Run at least 1-2 subjects through the full pipeline first

**JSON files are empty:**
- Check subject output directory structure
- Verify filenames match expected patterns

---

## Verification Checklist

After all Phase 2 scripts complete:

- [ ] `group_retinotopy_statistics.json` created
- [ ] `group_orientation_statistics.json` created
- [ ] `group_model_fit_comparison.json` created
- [ ] `group_ersp_cluster_statistics.json` created
- [ ] `group_consistency_metrics.json` created
- [ ] All files contain data (not empty)
- [ ] Model comparison shows divnorm advantage (if alpha is subadditive)

Once verified, proceed to **Phase 3: Report Integration**

---
