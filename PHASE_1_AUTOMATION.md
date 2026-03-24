# Phase 1 Automation: Full Pipeline for All Subjects

**The Phase 1 automation script processes all 31 subjects through a complete 8-step analysis pipeline automatically.**

## Quick Start

```bash
cd /Volumes/personal/EEG/project/eeg_visual_simulation_lac
bash Dataset/Scripts/Phase_1.sh
```

The script will process all 31 subjects sequentially, writing progress to the terminal.

## What the Script Does

### Prerequisites

Before running the automation, ensure:

1. **All subjects have preprocessed ICA files** (`*-ica.fif` in each subject's output directory)
   - Preprocessing creates these files from raw BIDS data
   - Use `preprocess.py` manually if not yet complete

2. **Raw BIDS dataset is available** at:
   ```
   /Volumes/personal/EEG/project/ds006547
   ```

3. **Virtual environment is activated** (optional but recommended):
   ```bash
   source eeg-env/bin/activate
   ```

## Step-by-Step Breakdown

### Step 1: Preprocessing (SKIPPED by default)

- Can be enabled by uncommenting in the script
- Creates ICA components from raw BrainVision data
- Output: `*-ica.fif` for each subject

### Step 2: Automatic ICA Inspection

- Runs `mne-icalabel` to classify components
- Threshold: 0.60 (configurable)
- Classifies components as: keep, reject, or unsure
- Output: `*-ica_component_review.json` with automated labels

### Step 2.5: Refine ICA Decisions

- Applies refinement heuristics to borderline components
- Improves classification reliability
- Output: `*-ica_component_review-refined.json`

### Step 3: Apply ICA Exclusions

- Uses refined ICA decisions to clean raw data
- Applies ICA-based artifact removal
- Generates cleaned raw and epochs files
- Output: `*-clean_raw.fif`, `*-final-epo.fif`

### Step 4: Extract Band Power

- Computes alpha (8-13 Hz) and gamma (40-80 Hz)
- Baseline-corrected power (`|task| - |baseline|`)
- Per-condition summaries
- Output: `*-alpha_by_condition.npz`, `*-gamma_by_condition.npz`

### Step 5: Retinotopy Analysis

- Builds spatial retinotopy summaries
- Alpha and gamma response maps
- Output: retinotopy figures and JSON files

### Step 6: Orientation Tuning Analysis

- Builds orientation-selective response summaries
- Direction selectivity analysis
- Alpha-vs-gamma comparisons
- Output: orientation tuning figures and JSON files

### Step 7: Extract Component ERSPs

- Time-frequency decomposition (Morlet wavelet)
- 4-100 Hz frequency range
- Single-trial ERSP matrices
- Output: `*-component_ersp.npy` and frequency/time axes

### Step 8: ERSP Statistics

- Orientation-selective ERSP analysis
- Cluster-based thresholding
- Statistical summaries
- Output: `*-orientation_ersp_stats.json`

## Configuration

Edit `Dataset/Scripts/Phase_1.sh` to change:

```bash
# Line 7: Change ICA decision threshold (0.60 is conservative)
THRESHOLD="0.60"

# Line 5-6: Update paths if dataset location differs
PROJECT_DIR="/Volumes/personal/EEG/project/eeg_visual_simulation_lac"
BIDS_DIR="/Volumes/personal/EEG/project/ds006547"
```

## Error Handling

The script includes comprehensive error checking:

- ✅ Checks for required files before each step
- ❌ Skips subjects if critical files are missing
- 📊 Displays progress for all steps
- 🛑 Continues with next subject on individual errors

**If a step fails for a subject:**
- Check the error message in the terminal
- The script automatically skips that subject and continues
- You can re-run the script on just that subject after fixing the issue

## Monitoring Progress

The script provides visual feedback:

```
================================================== 
 Processing sub-01...
==================================================
🧠 [Step 2] Running mne-icalabel...
...
✅ SUCCESS: Phase 1 fully completed for sub-01!
```

### Typical Timing

- Per subject: 15-45 minutes (depends on data size and system)
- All 31 subjects: 8-24 hours depending on system performance
- Consider running overnight or in a screen/tmux session

## Output Structure

After successful completion, each subject's output directory contains:

```
Dataset/outputs/sub-XX/
├── sub-XX_ses-01_task-visual_eeg-ica.fif                    (ICA model)
├── sub-XX_ses-01_task-visual_eeg-ica_component_review.json (auto labels)
├── sub-XX_ses-01_task-visual_eeg-clean_raw.fif             (cleaned data)
├── sub-XX_ses-01_task-visual_eeg-final-epo.fif             (cleaned epochs)
├── sub-XX_ses-01_task-visual_eeg-alpha_by_condition.npz    (power)
├── sub-XX_ses-01_task-visual_eeg-gamma_by_condition.npz
├── sub-XX_ses-01_task-visual_eeg-band_power_summary.json
├── sub-XX_ses-01_task-visual_eeg-component_ersp.npy        (time-freq)
├── sub-XX_ses-01_task-visual_eeg-component_ersp_freqs.npy
├── sub-XX_ses-01_task-visual_eeg-component_ersp_times.npy
├── *retinotopy*.json                                        (condition summaries)
├── *orientation*.json
└── *ersp_stats*.json                                        (statistics)
```

## Next Steps After Phase 1

After all subjects complete Phase 1, proceed to **Phase 2** for group-level analysis:

```bash
bash Dataset/Scripts/group_analysis.sh  # If available
# Or run individual group analysis scripts:
python Dataset/Scripts/grand_average_analysis.py
python Dataset/Scripts/group_topomaps.py
python Dataset/Scripts/retinotopy_model_fit.py
```

See [PHASE_2_INSTRUCTIONS.md](PHASE_2_INSTRUCTIONS.md) for details.

## Troubleshooting

### Script doesn't run

```bash
# Make script executable
chmod +x Dataset/Scripts/Phase_1.sh

# Run with bash explicitly
bash Dataset/Scripts/Phase_1.sh
```

### Missing ICA files

```bash
# Check which subjects are missing ICA files
ls -la Dataset/outputs/*/\*-ica.fif | wc -l  # Should be 31

# Don't forget to run preprocessing first if needed
python Dataset/Scripts/preprocess.py --vhdr /path/to/subject/vhdr
```

### Memory/performance issues

- Reduce the number of jobs in parallel computations (if supported)
- Edit individual script files to add `--n-jobs=1` to MNE functions
- Run during off-peak system usage

### Re-running specific subjects

```bash
# Modify the loop in Phase_1.sh
for i in 05 10 15; do  # Only subjects 05, 10, 15
    SUB_ID=$(printf "sub-%02d" $i)
    # ... rest of script
```

## Manual Alternative

If you prefer manual step-by-step control, see [Readme.md](Readme.md) for individual script invocations.
