"""
Shared utilities for custom analysis scripts.

Reads cleaned epochs from MNE-BIDS-Pipeline derivatives and provides
helper functions for band power extraction, condition mapping, and I/O.
"""

import json
from pathlib import Path

import mne
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────

# Bids_pipeline_Dataset/Scripts/ → Bids_pipeline_Dataset/ → project_root
SCRIPTS_DIR = Path(__file__).resolve().parent
DATASET_ROOT = SCRIPTS_DIR.parent                         # Bids_pipeline_Dataset/
PROJECT_ROOT = DATASET_ROOT.parent                        # eeg_visual_simulation_lac/
BIDS_ROOT = Path("/Volumes/personal/EEG/ds006547")
DERIV_ROOT = DATASET_ROOT / "outputs" / "derivatives"
CUSTOM_OUTPUT_ROOT = DERIV_ROOT / "bids_analysis"
CONDITION_MAPPING = SCRIPTS_DIR / "condition_mapping.json"

# ──────────────────────────────────────────────────────────────────────────────
# Band definitions
# ──────────────────────────────────────────────────────────────────────────────

ALPHA_BAND = (8.0, 13.0)
GAMMA_BAND = (40.0, 80.0)
GAMMA_SUBBANDS = ((40.0, 55.0), (65.0, 80.0))  # Avoids 60 Hz line noise

# Time windows
BASELINE_WINDOW = (-0.5, 0.0)
TASK_WINDOW = (0.0, 3.0)

# Channel priority for single-channel analyses
PREFERRED_CHANNELS = ["Oz", "O1", "O2", "POz", "Pz", "Cz"]

# Mapping from original trigger codes to renamed event names
# (must match rename_events in config.py)
TRIGGER_CODE_TO_NAME = {
    1: "full_field", 2: "left_hemifield", 3: "right_hemifield",
    4: "upper_hemifield", 5: "lower_hemifield",
    6: "quadrant_ul", 7: "quadrant_ur", 8: "quadrant_ll", 9: "quadrant_lr",
    10: "octant_1", 11: "octant_2", 12: "octant_3", 13: "octant_4",
    14: "octant_5", 15: "octant_6", 16: "octant_7", 17: "octant_8",
    18: "blank", 19: "periphery", 20: "fovea",
    21: "plaid", 22: "opposing_grating",
    41: "orient_000", 42: "orient_023", 43: "orient_045", 44: "orient_068",
    45: "orient_090", 46: "orient_113", 47: "orient_135", 48: "orient_158",
    49: "orient_180", 50: "orient_203", 51: "orient_225", 52: "orient_248",
    53: "orient_270", 54: "orient_293", 55: "orient_315", 56: "orient_338",
}
NAME_TO_TRIGGER_CODE = {v: k for k, v in TRIGGER_CODE_TO_NAME.items()}

# Subject IDs
ALL_SUBJECTS = [f"{i:02d}" for i in range(1, 32)]


# ──────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ──────────────────────────────────────────────────────────────────────────────

def load_json(path):
    """Load a JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, payload):
    """Save a JSON-serialisable object."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_condition_mapping():
    """Load the condition mapping JSON."""
    return load_json(CONDITION_MAPPING)


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline output locators
# ──────────────────────────────────────────────────────────────────────────────

def get_pipeline_epochs_path(subject: str, session: str = "01") -> Path:
    """
    Return the path to cleaned epochs produced by MNE-BIDS-Pipeline.

    The pipeline stores epochs in:
        derivatives/sub-XX/ses-01/eeg/sub-XX_ses-01_task-visual_proc-clean_epo.fif
    """
    sub = f"sub-{subject}"
    ses = f"ses-{session}"
    fname = f"{sub}_{ses}_task-visual_proc-clean_epo.fif"
    return DERIV_ROOT / sub / ses / "eeg" / fname


def get_custom_output_dir(subject: str) -> Path:
    """Return the custom analysis output directory for a subject."""
    out = CUSTOM_OUTPUT_ROOT / f"sub-{subject}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def get_group_output_dir() -> Path:
    """Return the group-level output directory."""
    out = CUSTOM_OUTPUT_ROOT / "group_level"
    out.mkdir(parents=True, exist_ok=True)
    return out


def load_pipeline_epochs(subject: str, session: str = "01"):
    """
    Load cleaned epochs from MNE-BIDS-Pipeline output.

    Falls back to the original pipeline output if BIDS-pipeline derivatives
    are not yet available (allows incremental migration).
    """
    epochs_path = get_pipeline_epochs_path(subject, session)

    if epochs_path.exists():
        print(f"  Loading pipeline epochs: {epochs_path}")
        return mne.read_epochs(epochs_path, preload=True, verbose=False)

    # Fallback: original pipeline output
    fallback = (
        PROJECT_ROOT / "Custom_pipeline_Dataset" / "outputs" / f"sub-{subject}"
        / f"sub-{subject}_ses-{session}_task-visual_eeg-final-epo.fif"
    )
    if fallback.exists():
        print(f"  [fallback] Loading original epochs: {fallback}")
        return mne.read_epochs(fallback, preload=True, verbose=False)

    raise FileNotFoundError(
        f"No cleaned epochs found for sub-{subject}.\n"
        f"  Tried: {epochs_path}\n"
        f"  Tried: {fallback}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Analysis helpers
# ──────────────────────────────────────────────────────────────────────────────

def choose_channel(ch_names):
    """Pick the best occipital channel from a list."""
    for ch in PREFERRED_CHANNELS:
        if ch in ch_names:
            return ch
    return ch_names[0]


def analytic_amplitude(data):
    """Compute analytic amplitude via Hilbert transform."""
    from scipy.signal import hilbert
    return np.abs(hilbert(data, axis=-1))


def group_mean(code_map, codes):
    """Average across condition codes in a code→array map.

    Supports both old-style integer trigger codes (translated via
    TRIGGER_CODE_TO_NAME) and direct event-name keys.
    """
    keys = []
    for c in codes:
        name = TRIGGER_CODE_TO_NAME.get(c)
        if name and name in code_map:
            keys.append(name)
        elif str(c) in code_map:
            keys.append(str(c))
    if not keys:
        return None
    return np.stack([code_map[k] for k in keys], axis=0).mean(axis=0)


def mean_code_value(code_map, codes, pick_idx):
    """Single scalar mean across codes at a picked channel."""
    vec = group_mean(code_map, codes)
    if vec is None:
        return None
    return float(vec[pick_idx])
