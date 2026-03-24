import argparse
import json
from collections import Counter
from pathlib import Path

import mne
import numpy as np


def _zscore(values):
    values = np.asarray(values, dtype=float)
    std = values.std(ddof=0)
    if std == 0:
        return np.zeros_like(values)
    return (values - values.mean()) / std


def infer_subject_from_vhdr(vhdr_path):
    stem_parts = vhdr_path.stem.split("_")
    subject = next((part for part in stem_parts if part.startswith("sub-")), None)
    session = next((part for part in stem_parts if part.startswith("ses-")), "ses-01")
    recording = vhdr_path.stem
    return subject or "sub-unknown", session, recording


def preserve_user_path(path_like):
    path = Path(path_like).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path

def build_notch_frequency_list(base_freq: float, max_freq: float, sfreq: float):
    """Build harmonic notch frequencies below Nyquist up to the requested ceiling."""
    if base_freq <= 0:
        return []
    nyquist = sfreq / 2.0
    upper = min(max_freq, nyquist - 1e-6)
    if upper < base_freq:
        return []
    n_harmonics = int(np.floor(upper / base_freq))
    return [round(base_freq * idx, 6) for idx in range(1, n_harmonics + 1)]


def detect_bad_channels(raw, l_freq=10.0, h_freq=100.0, z_thresh=1.0):
    eeg_picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(eeg_picks) == 0:
        raise RuntimeError("No EEG channels found for bad-channel detection.")

    raw_for_detection = raw.copy().pick(eeg_picks)
    raw_for_detection.filter(l_freq=l_freq, h_freq=h_freq, fir_design="firwin")

    data = raw_for_detection.get_data()
    diffs = np.diff(data, axis=1)
    ssd = np.sum(diffs ** 2, axis=1)
    zscores = _zscore(ssd)

    bads = [
        raw_for_detection.ch_names[idx]
        for idx, score in enumerate(zscores)
        if score > z_thresh
    ]

    return {
        "bads": bads,
        "channels": raw_for_detection.ch_names,
        "ssd": ssd.tolist(),
        "zscore": zscores.tolist(),
        "filter_band_hz": [l_freq, h_freq],
        "threshold": z_thresh,
    }


def extract_events(raw):
    events, event_id = mne.events_from_annotations(raw, verbose=False)
    if len(events) == 0:
        raise RuntimeError("No events were found in annotations.")
    return events, event_id


def build_ica_training_raw(raw, events, tmin, tmax):
    epochs = mne.Epochs(
        raw,
        events,
        event_id=None,
        tmin=tmin,
        tmax=tmax,
        baseline=None,
        preload=True,
        reject_by_annotation=True,
        verbose=False,
    )
    if len(epochs) == 0:
        raise RuntimeError("ICA training epochs are empty.")

    data = epochs.get_data(copy=True)
    n_epochs, n_channels, n_times = data.shape
    concatenated = np.transpose(data, (1, 0, 2)).reshape(n_channels, n_epochs * n_times)

    info = epochs.info.copy()
    info["bads"] = list(raw.info["bads"])
    training_raw = mne.io.RawArray(concatenated, info, verbose=False)
    training_raw.set_montage(raw.get_montage(), on_missing="ignore")
    return training_raw, epochs


def fit_ica(training_raw, method, n_components, max_iter, random_state):
    eeg_picks = mne.pick_types(training_raw.info, eeg=True, exclude="bads")
    usable_components = len(eeg_picks)
    if usable_components == 0:
        raise RuntimeError("No usable EEG channels were found for ICA fitting.")

    actual_n_components = min(n_components, usable_components)
    if actual_n_components != n_components:
        print(
            "Requested ICA components exceeded usable EEG channels; "
            f"using {actual_n_components} instead of {n_components}."
        )

    fit_kwargs = dict(
        n_components=actual_n_components,
        method=method,
        max_iter=max_iter,
        random_state=random_state,
    )
    if method == "picard":
        fit_kwargs["fit_params"] = {"ortho": False, "extended": True}

    ica = mne.preprocessing.ICA(**fit_kwargs)   
    ica.fit(training_raw, verbose=False)
    return ica, actual_n_components


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Paper-aligned EEG preprocessing and ICA fitting."
    )
    parser.add_argument("--vhdr", type=Path, required=True, help="Path to the .vhdr file.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to Dataset/outputs/<subject>.",
    )
    parser.add_argument(
        "--notch-freq",
        type=float,
        default=60.0,
        help="Line-noise notch frequency in Hz.",
    )
    parser.add_argument(
    "--notch-max-freq",
    type=float,
    default=180.0,
    help="Highest harmonic frequency to notch in Hz.",
    )

    parser.add_argument(
        "--ica-l-freq",
        type=float,
        default=1.0,
        help="Low cutoff for ICA training copy.",
    )
    parser.add_argument(
        "--ica-h-freq",
        type=float,
        default=100.0,
        help="High cutoff for ICA training copy.",
    )
    parser.add_argument(
        "--ssd-l-freq",
        type=float,
        default=10.0,
        help="Low cutoff for SSD bad-channel detection copy.",
    )
    parser.add_argument(
        "--ssd-h-freq",
        type=float,
        default=100.0,
        help="High cutoff for SSD bad-channel detection copy.",
    )
    parser.add_argument(
        "--bad-z-thresh",
        type=float,
        default=1.0,
        help="Z-score threshold for bad-channel SSD detection.",
    )
    parser.add_argument(
        "--resample-sfreq",
        type=float,
        default=200.0,
        help="Sampling rate for ICA training data.",
    )
    parser.add_argument(
        "--ica-tmin",
        type=float,
        default=-1.0,
        help="Epoch start in seconds for ICA training.",
    )
    parser.add_argument(
        "--ica-tmax",
        type=float,
        default=4.0,
        help="Epoch end in seconds for ICA training.",
    )
    parser.add_argument(
        "--ica-method",
        type=str,
        default="picard",
        choices=["picard", "fastica", "infomax"],
        help="ICA method.",
    )
    parser.add_argument(
        "--n-components",
        type=int,
        default=60,
        help="Number of ICA components.",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=500,
        help="Maximum ICA iterations.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=97,
        help="Random state for ICA reproducibility.",
    )
    args = parser.parse_args()

    vhdr_path = preserve_user_path(args.vhdr)
    if not vhdr_path.exists():
        raise FileNotFoundError(f"Cannot find VHDR file: {vhdr_path}")

    subject, session, recording = infer_subject_from_vhdr(vhdr_path)
    project_root = Path(__file__).resolve().parents[2]
    out_dir = args.out_dir or (project_root / "Dataset" / "outputs" / subject)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading raw BrainVision file: {vhdr_path}")
    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True, verbose=False)
    # Set correct channel types for non-EEG channels
    channel_type_map = {}
    for ch in raw.ch_names:
        ch_lower = ch.lower()
        if ch_lower == "ecg":
            channel_type_map[ch] = "ecg"
        elif ch_lower == "resp":
            channel_type_map[ch] = "resp"
        elif ch_lower in {"photosensor", "optical"}:
            channel_type_map[ch] = "misc"

    if channel_type_map:
        raw.set_channel_types(channel_type_map, verbose=False)

    # Keep only EEG channels for this pipeline
    non_eeg_to_drop = [ch for ch in ["photosensor", "optical", "ecg", "resp"] if ch in raw.ch_names]
    if non_eeg_to_drop:
        raw.drop_channels(non_eeg_to_drop)

    print("Interpolating bad channels.")

    detection = detect_bad_channels(
        raw,
        l_freq=args.ssd_l_freq,
        h_freq=args.ssd_h_freq,
        z_thresh=args.bad_z_thresh,
    )
    raw.info["bads"] = detection["bads"]
    if raw.info["bads"]:
        raw.interpolate_bads(reset_bads=False, verbose=False)

    notch_freqs = build_notch_frequency_list(
        args.notch_freq,
        args.notch_max_freq,
        raw.info["sfreq"],
    )
    if notch_freqs:
        raw.notch_filter(freqs=notch_freqs, verbose=False)

    ica_raw = raw.copy()
    ica_raw.filter(
        l_freq=args.ica_l_freq,
        h_freq=args.ica_h_freq,
        fir_design="firwin",
        verbose=False,
    )
    ica_raw.resample(args.resample_sfreq, verbose=False)

    events, event_id = extract_events(ica_raw)
    training_raw, training_epochs = build_ica_training_raw(
        ica_raw,
        events,
        tmin=args.ica_tmin,
        tmax=args.ica_tmax,
    )

    print(
        "Fitting ICA on concatenated event-centered epochs "
        f"({len(training_epochs)} epochs, {training_raw.info['sfreq']} Hz)."
    )
    ica, actual_n_components = fit_ica(
        training_raw=training_raw,
        method=args.ica_method,
        n_components=args.n_components,
        max_iter=args.max_iter,
        random_state=args.random_state,
    )

    ica_path = out_dir / f"{recording}-ica.fif"
    ica.save(ica_path, overwrite=True)

    review_path = out_dir / f"{recording}-ica_component_review.json"
    review_template = {
        "subject": subject,
        "session": session,
        "recording": recording,
        "notes": "Fill in manual ICA decisions after reviewing topographies and ERSPs.",
        "kept_components": [],
        "rejected_components": [],
        "labels": {},
    }
    if not review_path.exists():
        write_json(review_path, review_template)

    bad_channels_path = out_dir / f"{recording}-bad_channels.json"
    write_json(
        bad_channels_path,
        {
            "subject": subject,
            "session": session,
            "recording": recording,
            **detection,
        },
    )

    event_counts = Counter(events[:, 2].tolist())
    summary = {
        "subject": subject,
        "session": session,
        "recording": recording,
        "vhdr_path": str(vhdr_path),
        "outputs": {
            "ica_fif": str(ica_path),
            "bad_channels_json": str(bad_channels_path),
            "component_review_json": str(review_path),
        },
        "preprocessing": {
            "bad_channel_detection_band_hz": [args.ssd_l_freq, args.ssd_h_freq],
            "bad_channel_z_threshold": args.bad_z_thresh,
            "bad_channels": detection["bads"],
        "notch_freq_hz": args.notch_freq,
        "notch_max_freq_hz": args.notch_max_freq,
        "notch_freqs_applied_hz": notch_freqs,
            "ica_filter_band_hz": [args.ica_l_freq, args.ica_h_freq],
            "ica_training_resample_hz": args.resample_sfreq,
            "ica_epoch_window_s": [args.ica_tmin, args.ica_tmax],
            "ica_method": args.ica_method,
            "n_components_requested": args.n_components,
            "n_components_used": actual_n_components,
            "max_iter": args.max_iter,
            "random_state": args.random_state,
        },
        "events": {
            "n_events": int(len(events)),
            "event_id": event_id,
            "event_counts": {str(code): count for code, count in sorted(event_counts.items())},
        },
    }
    summary_path = out_dir / f"{recording}-preprocess_summary.json"
    write_json(summary_path, summary)

    print(f"Saved ICA model: {ica_path}")
    print(f"Saved bad-channel log: {bad_channels_path}")
    print(f"Saved component review template: {review_path}")
    print(f"Saved preprocess summary: {summary_path}")


if __name__ == "__main__":
    main()
