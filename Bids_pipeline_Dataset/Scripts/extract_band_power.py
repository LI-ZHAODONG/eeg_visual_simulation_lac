"""
Extract alpha and gamma band power from cleaned epochs.

Reads cleaned epochs from MNE-BIDS-Pipeline derivatives, computes Hilbert-based
analytic amplitude in alpha (8-13 Hz) and gamma (40-80 Hz, sub-banded to avoid
60 Hz line noise), and saves per-trial and per-condition power differences
(task − baseline).

This replaces: Dataset/Scripts/extract_band_power.py

Usage:
    python extract_band_power.py            # all subjects
    python extract_band_power.py --subject 01  # one subject
"""

import argparse
import sys
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (
    ALL_SUBJECTS,
    ALPHA_BAND,
    BASELINE_WINDOW,
    GAMMA_SUBBANDS,
    TASK_WINDOW,
    analytic_amplitude,
    get_custom_output_dir,
    load_pipeline_epochs,
    save_json,
)


def compute_band_difference(epochs, l_freq, h_freq, baseline, task):
    """Filter epochs to a band, compute Hilbert amplitude, return task−baseline."""
    band_epochs = epochs.copy().filter(
        l_freq=l_freq, h_freq=h_freq, fir_design="firwin", verbose=False,
    )
    data = band_epochs.get_data(copy=True)
    amp = analytic_amplitude(data)
    times = band_epochs.times

    bl_mask = (times >= baseline[0]) & (times < baseline[1])
    task_mask = (times >= task[0]) & (times < task[1])

    baseline_mean = amp[:, :, bl_mask].mean(axis=-1)
    task_mean = amp[:, :, task_mask].mean(axis=-1)
    diff = task_mean - baseline_mean

    return {"trial_diff": diff, "baseline_mean": baseline_mean, "task_mean": task_mean}


def compute_multi_band_difference(epochs, bands, baseline, task):
    """Average band power across multiple sub-bands."""
    results = [
        compute_band_difference(epochs, l, h, baseline, task) for l, h in bands
    ]
    return {
        "trial_diff": np.mean([r["trial_diff"] for r in results], axis=0),
        "baseline_mean": np.mean([r["baseline_mean"] for r in results], axis=0),
        "task_mean": np.mean([r["task_mean"] for r in results], axis=0),
    }


def compute_condition_means(trial_diff, event_names):
    """Mean power per condition name."""
    unique = sorted(set(event_names))
    return {name: trial_diff[event_names == name].mean(axis=0) for name in unique}


def process_subject(subject):
    """Extract band power for one subject."""
    print(f"\n{'='*60}")
    print(f"  Extracting band power for sub-{subject}")
    print(f"{'='*60}")

    epochs = load_pipeline_epochs(subject)
    event_codes = epochs.events[:, 2]
    # Map pipeline's internal IDs to meaningful event names
    code_to_name = {v: k for k, v in epochs.event_id.items()}
    event_names = np.array([code_to_name[c] for c in event_codes])

    # Alpha: single band 8-13 Hz
    alpha = compute_band_difference(
        epochs, ALPHA_BAND[0], ALPHA_BAND[1],
        baseline=BASELINE_WINDOW, task=TASK_WINDOW,
    )

    # Gamma: sub-banded (40-55, 65-80 Hz) to avoid 60 Hz
    gamma = compute_multi_band_difference(
        epochs, bands=GAMMA_SUBBANDS,
        baseline=BASELINE_WINDOW, task=TASK_WINDOW,
    )

    # Save outputs
    out_dir = get_custom_output_dir(subject)
    prefix = f"sub-{subject}_ses-01_task-visual"

    np.save(out_dir / f"{prefix}-alpha_trial_diff.npy", alpha["trial_diff"])
    np.save(out_dir / f"{prefix}-gamma_trial_diff.npy", gamma["trial_diff"])
    np.save(out_dir / f"{prefix}-event_codes.npy", event_codes)
    np.save(out_dir / f"{prefix}-event_names.npy", event_names)

    alpha_by_cond = compute_condition_means(alpha["trial_diff"], event_names)
    gamma_by_cond = compute_condition_means(gamma["trial_diff"], event_names)
    np.savez(out_dir / f"{prefix}-alpha_by_condition.npz", **alpha_by_cond)
    np.savez(out_dir / f"{prefix}-gamma_by_condition.npz", **gamma_by_cond)

    summary = {
        "subject": f"sub-{subject}",
        "n_epochs": int(len(epochs)),
        "n_channels": int(len(epochs.ch_names)),
        "ch_names": list(epochs.ch_names),
        "event_names": sorted(set(event_names.tolist())),
        "event_codes": sorted(set(int(c) for c in event_codes)),
        "bands": {
            "alpha": list(ALPHA_BAND),
            "gamma_subbands": [list(b) for b in GAMMA_SUBBANDS],
        },
        "windows_s": {
            "baseline": list(BASELINE_WINDOW),
            "task": list(TASK_WINDOW),
        },
    }
    save_json(out_dir / f"{prefix}-band_power_summary.json", summary)
    print(f"  Saved band power outputs to {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Extract alpha/gamma band power")
    parser.add_argument("--subject", default=None, help="Single subject ID (e.g., 01)")
    args = parser.parse_args()

    subjects = [args.subject] if args.subject else ALL_SUBJECTS

    for sub in subjects:
        try:
            process_subject(sub)
        except FileNotFoundError as e:
            print(f"  SKIP sub-{sub}: {e}")
        except Exception as e:
            print(f"  ERROR sub-{sub}: {e}")

    print("\nDone — band power extraction complete.")


if __name__ == "__main__":
    main()
