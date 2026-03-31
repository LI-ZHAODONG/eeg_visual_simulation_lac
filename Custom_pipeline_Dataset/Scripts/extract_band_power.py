import argparse
import json
from pathlib import Path

import mne
import numpy as np
from scipy.signal import hilbert

GAMMA_BAND = (40.0, 80.0)   # Full range — power line noise removed by notch filter

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def infer_recording_name(path):
    name = path.name
    if name.endswith("-final-epo.fif"):
        return name[: -len("-final-epo.fif")]
    return path.stem


def analytic_amplitude(data):
    return np.abs(hilbert(data, axis=-1))


def compute_band_difference(epochs, l_freq, h_freq, baseline, task):
    band_epochs = epochs.copy().filter(
        l_freq=l_freq,
        h_freq=h_freq,
        fir_design="firwin",
        verbose=False,
    )
    data = band_epochs.get_data(copy=True)
    amp = analytic_amplitude(data)
    power = amp ** 2
    times = band_epochs.times

    baseline_mask = (times >= baseline[0]) & (times < baseline[1])
    task_mask = (times >= task[0]) & (times < task[1])

    if not baseline_mask.any():
        raise RuntimeError(f"No samples found in baseline window {baseline}.")
    if not task_mask.any():
        raise RuntimeError(f"No samples found in task window {task}.")

    baseline_power = power[:, :, baseline_mask].mean(axis=-1)
    task_power = power[:, :, task_mask].mean(axis=-1)
    # Clip to avoid log(0); baseline_power should never be zero for EEG
    baseline_power = np.clip(baseline_power, 1e-30, None)
    task_power = np.clip(task_power, 1e-30, None)
    diff = np.log(task_power / baseline_power)

    return {
        "trial_diff": diff,
        "baseline_mean": baseline_power,
        "task_mean": task_power,
    }




def compute_condition_means(trial_diff, event_codes):
    unique_codes = sorted(set(int(code) for code in event_codes))
    per_code = {}
    for code in unique_codes:
        mask = event_codes == code
        per_code[str(code)] = trial_diff[mask].mean(axis=0)
    return per_code


def main():
    parser = argparse.ArgumentParser(
        description="Extract paper-style alpha/gamma sensor-space power differences."
    )
    parser.add_argument(
        "--epochs-path",
        type=Path,
        required=True,
        help="Path to cleaned epochs saved after reviewed ICA application.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Optional apply_reviewed_ica summary JSON path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to the epochs file directory.",
    )
    parser.add_argument(
        "--baseline-start",
        type=float,
        default=-0.5,
        help="Baseline start time in seconds.",
    )
    parser.add_argument(
        "--baseline-end",
        type=float,
        default=0.0,
        help="Baseline end time in seconds.",
    )
    parser.add_argument(
        "--task-start",
        type=float,
        default=0.0,
        help="Task window start time in seconds.",
    )
    parser.add_argument(
        "--task-end",
        type=float,
        default=3.0,
        help="Task window end time in seconds.",
    )
    args = parser.parse_args()

    epochs_path = args.epochs_path.resolve()
    if not epochs_path.exists():
        raise FileNotFoundError(f"Cannot find epochs file: {epochs_path}")

    out_dir = (args.out_dir or epochs_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    recording = infer_recording_name(epochs_path)
    summary_json = args.summary_json
    if summary_json is None:
        candidate = out_dir / f"{recording}-apply_reviewed_ica_summary.json"
        summary_json = candidate if candidate.exists() else None

    print(f"Loading cleaned epochs: {epochs_path}")
    epochs = mne.read_epochs(epochs_path, preload=True, verbose=False)
    event_codes = epochs.events[:, 2]

    baseline = (args.baseline_start, args.baseline_end)
    task = (args.task_start, args.task_end)

    alpha = compute_band_difference(epochs, 8.0, 13.0, baseline=baseline, task=task)
    gamma = compute_band_difference(
        epochs,
        l_freq=GAMMA_BAND[0],
        h_freq=GAMMA_BAND[1],
        baseline=baseline,
        task=task,
    )

    alpha_trial_path = out_dir / f"{recording}-alpha_trial_diff.npy"
    gamma_trial_path = out_dir / f"{recording}-gamma_trial_diff.npy"
    event_codes_path = out_dir / f"{recording}-event_codes.npy"
    np.save(alpha_trial_path, alpha["trial_diff"])
    np.save(gamma_trial_path, gamma["trial_diff"])
    np.save(event_codes_path, event_codes)

    alpha_mean = alpha["trial_diff"].mean(axis=0)
    gamma_mean = gamma["trial_diff"].mean(axis=0)
    alpha_mean_path = out_dir / f"{recording}-alpha_diff.npy"
    gamma_mean_path = out_dir / f"{recording}-gamma_diff.npy"
    np.save(alpha_mean_path, alpha_mean)
    np.save(gamma_mean_path, gamma_mean)

    alpha_by_condition = compute_condition_means(alpha["trial_diff"], event_codes)
    gamma_by_condition = compute_condition_means(gamma["trial_diff"], event_codes)

    alpha_condition_path = out_dir / f"{recording}-alpha_by_condition.npz"
    gamma_condition_path = out_dir / f"{recording}-gamma_by_condition.npz"
    np.savez(alpha_condition_path, **alpha_by_condition)
    np.savez(gamma_condition_path, **gamma_by_condition)

    payload = {
        "recording": recording,
        "epochs_path": str(epochs_path),
        "summary_json": str(summary_json) if summary_json is not None else None,
        "n_epochs": int(len(epochs)),
        "n_channels": int(len(epochs.ch_names)),
        "ch_names": epochs.ch_names,
        "event_codes": sorted(set(int(code) for code in event_codes)),
        "bands": {
            "alpha": [8.0, 13.0],
            "gamma": [40.0, 80.0],
            "gamma_band": list(GAMMA_BAND),
        },
        "windows_s": {
            "baseline": list(baseline),
            "task": list(task),
        },
        "outputs": {
            "alpha_trial_diff_npy": str(alpha_trial_path),
            "gamma_trial_diff_npy": str(gamma_trial_path),
            "event_codes_npy": str(event_codes_path),
            "alpha_mean_diff_npy": str(alpha_mean_path),
            "gamma_mean_diff_npy": str(gamma_mean_path),
            "alpha_by_condition_npz": str(alpha_condition_path),
            "gamma_by_condition_npz": str(gamma_condition_path),
        },
    }

    if summary_json is not None and Path(summary_json).exists():
        payload["apply_reviewed_ica_summary"] = load_json(Path(summary_json))

    summary_path = out_dir / f"{recording}-band_power_summary.json"
    write_json(summary_path, payload)

    print(f"Saved alpha trial matrix: {alpha_trial_path}")
    print(f"Saved gamma trial matrix: {gamma_trial_path}")
    print(f"Saved event codes: {event_codes_path}")
    print(f"Saved alpha mean vector: {alpha_mean_path}")
    print(f"Saved gamma mean vector: {gamma_mean_path}")
    print(f"Saved alpha by-condition matrix set: {alpha_condition_path}")
    print(f"Saved gamma by-condition matrix set: {gamma_condition_path}")
    print(f"Saved band-power summary: {summary_path}")


if __name__ == "__main__":
    main()
