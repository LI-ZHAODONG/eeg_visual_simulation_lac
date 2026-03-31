# -*- coding: utf-8 -*-
"""
MNE-BIDS-Pipeline configuration for the Visual EEG Study (ds006547).

This config replaces the custom preprocessing pipeline (Phase_1.sh) with a
standardized MNE-BIDS-Pipeline approach.  The dataset is already BIDS 1.9.0
compliant (BrainVision format, 64-channel EEG, 500 Hz sampling).

Reference paper
---------------
Dissociable Spatial and Feature Tuning of Gamma and Alpha Rhythms in Human
Visual Cortex — Ghaffari, Yavari, Bonyadian, Ghofrani & Butler

Usage
-----
    cd Bids_pipeline_Dataset/Scripts

    # Test on one subject
    mne_bids_pipeline --config config.py --subject 01 --steps preprocessing

    # Run all subjects (or use run_pipeline.py wrapper)
    python run_pipeline.py --steps preprocessing,sensor

    # Generate HTML reports
    python run_pipeline.py --steps preprocessing,sensor --report
"""

from pathlib import Path

# ==============================================================================
# GENERAL SETTINGS
# ==============================================================================

# Path to the BIDS dataset root (OpenNeuro ds006547)
# Override with BIDS_ROOT environment variable if needed
import os
_config_dir = Path(__file__).resolve().parent          # Bids_pipeline_Dataset/Scripts/
_dataset_dir = _config_dir.parent                      # Bids_pipeline_Dataset/
_project_dir = _dataset_dir.parent                     # eeg_visual_simulation_lac/
bids_root = Path(os.environ.get("BIDS_ROOT", _project_dir.parent / "ds006547"))

# Where the pipeline writes its derivatives
deriv_root = _dataset_dir / "outputs" / "derivatives"

# Subjects to process (all 31)
subjects = [f"{i:02d}" for i in range(1, 32)]

# sub-30 excluded from group analysis
exclude_subjects = ["30"]

# Sessions
sessions = ["01"]

# Task name (must match BIDS task entity: task-visual)
task = "visual"

# Data type
data_type = "eeg"
ch_types = ["eeg"]

# Interactive mode off for batch processing
interactive = False

# ==============================================================================
# PREPROCESSING — BREAK / BAD SEGMENTS
# ==============================================================================

# Find and annotate bad segments automatically
find_breaks = True

# ==============================================================================
# PREPROCESSING — BAD CHANNEL DETECTION
# ==============================================================================

# Use automated bad channel detection
find_flat_channels_meg = False  # EEG only
find_noisy_channels_meg = False  # EEG only

# ==============================================================================
# PREPROCESSING — FILTERING
# ==============================================================================

# Bandpass filter (same philosophy as current pipeline: 1–100 Hz)
l_freq = 1.0    # High-pass at 1 Hz — removes DC drift
h_freq = 100.0  # Low-pass at 100 Hz — anti-aliasing before resample

# Notch filter: power line at 60 Hz (from sidecar JSON: PowerLineFrequency=60)
# Pipeline will auto-detect from BIDS sidecar, but we set explicitly
notch_freq = 60  # Will also remove harmonics (120, 180, 240 Hz) up to Nyquist; raw data is 1000 Hz so notch applied before resample

# Notch filter width
notch_widths = 2.0  # Hz — narrow notch to preserve gamma band

# ==============================================================================
# PREPROCESSING — RESAMPLING
# ==============================================================================

# Resample to 200 Hz (matches current pipeline; Nyquist = 100 Hz covers gamma)
raw_resample_sfreq = 200

# ==============================================================================
# PREPROCESSING — RE-REFERENCING
# ==============================================================================

# Original recording reference: FCz (from sidecar JSON)
# Re-reference to common average (standard for EEG analysis)
eeg_reference = "average"

# ==============================================================================
# PREPROCESSING — ICA
# ==============================================================================

# ICA algorithm: picard (matches current pipeline choice — fast, robust)
ica_algorithm = "picard"

# Keep components explaining 99% of variance
ica_n_components = 0.99

# Automatic EOG/ECG artifact rejection thresholds
# This replaces: auto_inspect_ica.py + refine_ica_review.py
ica_eog_threshold = 3.0
ica_ecg_threshold = 0.1

# ==============================================================================
# EVENT RENAMING
# ==============================================================================

# Raw events use BrainVision marker names like "Stimulus/S  1".
# Rename to meaningful condition names for epoching and analysis.
rename_events = {
    # Retinotopy conditions (codes 1-20)
    "Stimulus/S  1": "full_field",
    "Stimulus/S  2": "left_hemifield",
    "Stimulus/S  3": "right_hemifield",
    "Stimulus/S  4": "upper_hemifield",
    "Stimulus/S  5": "lower_hemifield",
    "Stimulus/S  6": "quadrant_ul",
    "Stimulus/S  7": "quadrant_ur",
    "Stimulus/S  8": "quadrant_ll",
    "Stimulus/S  9": "quadrant_lr",
    "Stimulus/S 10": "octant_1",
    "Stimulus/S 11": "octant_2",
    "Stimulus/S 12": "octant_3",
    "Stimulus/S 13": "octant_4",
    "Stimulus/S 14": "octant_5",
    "Stimulus/S 15": "octant_6",
    "Stimulus/S 16": "octant_7",
    "Stimulus/S 17": "octant_8",
    "Stimulus/S 18": "blank",
    "Stimulus/S 19": "periphery",
    "Stimulus/S 20": "fovea",
    "Stimulus/S 21": "plaid",
    "Stimulus/S 22": "opposing_grating",
    # Orientation conditions (codes 41-56: 16 orientations, 22.5° steps)
    "Stimulus/S 41": "orient_000",
    "Stimulus/S 42": "orient_023",
    "Stimulus/S 43": "orient_045",
    "Stimulus/S 44": "orient_068",
    "Stimulus/S 45": "orient_090",
    "Stimulus/S 46": "orient_113",
    "Stimulus/S 47": "orient_135",
    "Stimulus/S 48": "orient_158",
    "Stimulus/S 49": "orient_180",
    "Stimulus/S 50": "orient_203",
    "Stimulus/S 51": "orient_225",
    "Stimulus/S 52": "orient_248",
    "Stimulus/S 53": "orient_270",
    "Stimulus/S 54": "orient_293",
    "Stimulus/S 55": "orient_315",
    "Stimulus/S 56": "orient_338",
}

# Ignore the "New Segment/" marker
on_rename_missing_events = "ignore"

# ==============================================================================
# EPOCHING
# ==============================================================================

# Define all conditions from the experiment via trigger codes
# Retinotopy conditions (codes 1-20) + Orientation conditions (codes 41-56)
# The pipeline reads events from *_events.tsv (BIDS standard)

# Epoch time window
epochs_tmin = -0.5   # 500 ms pre-stimulus
epochs_tmax = 3.0    # 3 s post-stimulus (paper uses 3 s task window)

# Baseline correction
baseline = (-0.5, 0)  # Pre-stimulus baseline

# Conditions to epoch (must match renamed event names above)
conditions = [
    # Retinotopy
    "full_field",
    "left_hemifield",
    "right_hemifield",
    "upper_hemifield",
    "lower_hemifield",
    "quadrant_ul",
    "quadrant_ur",
    "quadrant_ll",
    "quadrant_lr",
    "octant_1",
    "octant_2",
    "octant_3",
    "octant_4",
    "octant_5",
    "octant_6",
    "octant_7",
    "octant_8",
    "blank",
    "periphery",
    "fovea",
    "plaid",
    "opposing_grating",
    # Orientation
    "orient_000",
    "orient_023",
    "orient_045",
    "orient_068",
    "orient_090",
    "orient_113",
    "orient_135",
    "orient_158",
    "orient_180",
    "orient_203",
    "orient_225",
    "orient_248",
    "orient_270",
    "orient_293",
    "orient_315",
    "orient_338",
]

# Disable fixed PTP rejection — ICA has already cleaned major artifacts.
reject = None

# ==============================================================================
# SENSOR-LEVEL ANALYSIS
# ==============================================================================

# Contrasts to compute (evoked differences)
contrasts = [
    ("full_field", "blank"),       # Full field vs baseline
    ("periphery", "blank"),        # Periphery vs baseline
    ("fovea", "blank"),            # Fovea vs baseline
    ("opposing_grating", "blank"), # Grating vs baseline
]

# ==============================================================================
# TIME-FREQUENCY ANALYSIS
# ==============================================================================

# Morlet wavelet TFR (replaces extract_component_ersp.py)
# Frequency range: 4–100 Hz (same as current ERSP extraction)
time_frequency_freq_min = 4
time_frequency_freq_max = 100

# Number of wavelet cycles (frequency-dependent: more cycles at higher freqs)
time_frequency_cycles = None  # Use default: freqs / 2

# TFR baseline
time_frequency_baseline = (-0.5, 0)
time_frequency_baseline_mode = "logratio"

# ==============================================================================
# GROUP ANALYSIS
# ==============================================================================

# Compute grand averages across subjects
# (replaces grand_average_analysis.py + group_topomaps.py)

# ==============================================================================
# REPORTING
# ==============================================================================

# Generate per-subject + group HTML reports

# ==============================================================================
# PERFORMANCE
# ==============================================================================

# Number of parallel jobs (-1 = use all cores)
n_jobs = 4

# Memory limit (in GB) — adjust based on your machine
memory_location = False  # Disable caching to save disk space
