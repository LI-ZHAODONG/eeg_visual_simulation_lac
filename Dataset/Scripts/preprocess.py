import argparse
from pathlib import Path

import numpy as np
import mne
from mne.preprocessing import ICA


def detect_bad_channels_ssd(raw):
    """Detect bad channels with SSD (10–100 Hz) and interpolate them."""
    raw_filt = raw.copy().filter(10, 100, fir_design="firwin")
    data = raw_filt.get_data()  # (n_channels, n_samples)

    # Sum of squared differences across time
    ssd = np.sum(np.diff(data, axis=1) ** 2, axis=1)
    z = (ssd - ssd.mean()) / ssd.std()

    bads = [raw.ch_names[i] for i, zi in enumerate(z) if zi > 1.0]
    print(f"Detected bad channels (z > 1): {bads}")

    raw.info["bads"] = bads
    raw.interpolate_bads(reset_bads=True)
    return raw


def run_ica(raw, n_components=60):
    """Prepare data for ICA (1–100 Hz, 200 Hz resample) and fit Picard ICA."""
    # Filter 1–100 Hz for ICA
    ica_raw = raw.copy().filter(1, 100, fir_design="firwin")

    # Resample to 200 Hz to reduce computational load
    ica_raw.resample(200)

    # Get events from annotations
    events, event_id = mne.events_from_annotations(ica_raw)
    print(f"Found {len(events)} events, event_id mapping: {event_id}")

    # Epochs for ICA training: -1.0 to 4.0 s
    epochs = mne.Epochs(
        ica_raw,
        events,
        event_id=None,   # use all events
        tmin=-1.0,
        tmax=4.0,
        baseline=None,
        preload=True,
    )
    print(f"Epochs shape for ICA: {epochs.get_data().shape}")

    ica = ICA(
        method="picard",
        n_components=n_components,
        max_iter=500,
        fit_params=dict(extended=True),
        random_state=97,
    )
    ica.fit(epochs)
    return ica


def apply_ica_and_epoch(raw, ica, bad_components):
    """
    Apply ICA, excluding bad_components, then create final epochs
    (-0.5 to 3.5 s, baseline -0.5–0).
    """
    print(f"Excluding ICA components: {bad_components}")
    ica.exclude = bad_components
    clean_raw = ica.apply(raw.copy())

    # Final epochs for analysis
    events, event_id = mne.events_from_annotations(clean_raw)

    final_epochs = mne.Epochs(
        clean_raw,
        events,
        event_id=None,
        tmin=-0.5,
        tmax=3.5,
        baseline=(-0.5, 0.0),
        preload=True,
    )
    print(f"Final epochs shape: {final_epochs.get_data().shape}")
    return final_epochs


def compute_band_amplitude(final_epochs, fmin, fmax, label):
    """Filter into band and compute |task| - |baseline| amplitude per channel."""
    band_epochs = final_epochs.copy().filter(fmin, fmax, fir_design="firwin")
    data = band_epochs.get_data()  # (n_epochs, n_channels, n_times)

    times = band_epochs.times

    # Indices for baseline (-0.5–0) and task (0–3.0)
    baseline_mask = (times >= -0.5) & (times <= 0.0)
    task_mask = (times >= 0.0) & (times <= 3.0)

    # Rectified amplitude (absolute value)
    abs_data = np.abs(data)

    baseline_mean = abs_data[:, :, baseline_mask].mean(axis=2)
    task_mean = abs_data[:, :, task_mask].mean(axis=2)

    diff = task_mean - baseline_mean  # |task| - |baseline|
    print(f"{label} band: computed per-epoch per-channel amplitude differences.")
    return diff  # shape: (n_epochs, n_channels)


def main(vhdr_path, out_dir):
    vhdr_path = Path(vhdr_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading BrainVision file: {vhdr_path}")
    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True)

    # 1) Bad channel detection + interpolation
    raw = detect_bad_channels_ssd(raw)

    # 2) Line noise removal (60 Hz)
    raw.notch_filter(60.0)

    # 3) Run ICA
    ica = run_ica(raw)

    # 4) Automatically find eye-related components
    # Try to find EOG channels explicitly
    eog_like = [ch for ch in raw.ch_names if "EOG" in ch.upper()]

    # If there is no dedicated EOG channel, fall back to frontal EEG (Fp, AF)
    if not eog_like:
        eog_like = [
            ch for ch in raw.ch_names
            if ch.upper().startswith("FP") or ch.upper().startswith("AF")
        ]

    if eog_like:
        print("Using these channels as EOG reference:", eog_like)
        eog_inds, eog_scores = ica.find_bads_eog(raw, ch_name=eog_like)
    else:
        print("No EOG or frontal channels found, skipping auto EOG detection.")
        eog_inds, eog_scores = [], []

    print("Auto-detected EOG components:", eog_inds)

    # Optionally extend this list manually after visual inspection
    manual_bad = []  # e.g. [3, 7] once you inspect components
    bad_components = sorted(list(set(eog_inds + manual_bad)))

    # 5) Apply ICA and epoch final data
    final_epochs = apply_ica_and_epoch(raw, ica, bad_components)

    # 6) Save ICA solution (with exclude list set)
    ica_fname = out_dir / f"{vhdr_path.stem}-ica.fif"
    print(f"Saving ICA solution to {ica_fname}")
    ica.save(ica_fname,overwrite=True)

    # 7) Compute alpha and gamma amplitude differences
    alpha_diff = compute_band_amplitude(final_epochs, 8, 13, label="Alpha")
    gamma_diff = compute_band_amplitude(final_epochs, 40, 80, label="Gamma")

    # 8) Save results
    np.save(out_dir / f"{vhdr_path.stem}-alpha_diff.npy", alpha_diff)
    np.save(out_dir / f"{vhdr_path.stem}-gamma_diff.npy", gamma_diff)

    print(f"Saved alpha/gamma per-epoch per-channel arrays for {vhdr_path.stem}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vhdr",
        required=True,
        help="Path to BrainVision .vhdr file (e.g., sub-01/ses-01/eeg/sub-01_ses-01_task-visual_eeg.vhdr)",
    )
    parser.add_argument(
        "--out_dir",
        default="outputs/preproc",
        help="Directory where preprocessed outputs will be saved",
    )
    args = parser.parse_args()
    main(args.vhdr, args.out_dir)
