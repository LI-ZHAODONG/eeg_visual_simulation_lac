import argparse
import json
from pathlib import Path

import matplotlib
import mne

matplotlib.use("Agg")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def infer_recording_name(ica_path):
    name = ica_path.name
    if name.endswith("-ica.fif"):
        return name[: -len("-ica.fif")]
    return ica_path.stem


def preserve_user_path(path_like):
    path = Path(path_like).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def rebuild_cleaning_raw(vhdr_path, preprocess_summary):
    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True, verbose=False)
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

    to_drop = [ch for ch in ["photosensor", "optical", "ecg", "resp"] if ch in raw.ch_names]
    if to_drop:
        raw.drop_channels(to_drop)

    preprocessing = preprocess_summary.get("preprocessing", {})
    bad_channels = preprocessing.get("bad_channels", [])
    raw.info["bads"] = list(bad_channels)
    if raw.info["bads"]:
        raw.interpolate_bads(reset_bads=False, verbose=False)

    notch_freqs = preprocessing.get("notch_freqs_applied_hz")
    if notch_freqs is None:
        notch_freq = preprocessing.get("notch_freq_hz", 60.0)
        notch_freqs = [notch_freq]
    notch_freqs = [
        float(freq)
        for freq in notch_freqs
        if 0 < float(freq) < raw.info["sfreq"] / 2.0
    ]
    if notch_freqs:
        raw.notch_filter(freqs=notch_freqs, verbose=False)

    return raw


def get_kept_components(review_payload):
    component_decisions = review_payload.get("component_decisions", {})
    kept = []
    rejected = []

    for key, value in component_decisions.items():
        comp_idx = int(key)
        keep = value.get("keep")
        if keep is True:
            kept.append(comp_idx)
        elif keep is False:
            rejected.append(comp_idx)

    return sorted(kept), sorted(rejected)


def pick_best_channel(ch_names):
    for ch in ["Oz", "O1", "O2", "POz", "Pz", "Cz"]:
        if ch in ch_names:
            return ch
    return ch_names[0]


def save_qc_figures(raw_before, raw_after, out_dir, recording):
    picks_eeg = mne.pick_types(raw_after.info, eeg=True, exclude=[])
    if len(picks_eeg) == 0:
        return {}

    start = 100.0
    duration = 10.0

    browser_raw = raw_before.plot(
        picks=picks_eeg,
        n_channels=min(32, len(picks_eeg)),
        start=start,
        duration=duration,
        scalings=dict(eeg=20e-6),
        remove_dc=True,
        show=False,
        block=False,
    )
    raw_path = out_dir / f"{recording}-raw_cleaning_reference_10s.png"
    browser_raw.figure.savefig(raw_path, dpi=300)

    browser_clean = raw_after.plot(
        picks=picks_eeg,
        n_channels=min(32, len(picks_eeg)),
        start=start,
        duration=duration,
        scalings=dict(eeg=20e-6),
        remove_dc=True,
        show=False,
        block=False,
    )
    clean_path = out_dir / f"{recording}-cleaned_10s.png"
    browser_clean.figure.savefig(clean_path, dpi=300)

    psd_raw = raw_before.copy().pick(picks_eeg).compute_psd(fmin=1, fmax=100)
    fig_psd_raw = psd_raw.plot(show=False)
    psd_raw_path = out_dir / f"{recording}-psd_before_reviewed_ica.png"
    fig_psd_raw.savefig(psd_raw_path, dpi=300)

    psd_clean = raw_after.copy().pick(picks_eeg).compute_psd(fmin=1, fmax=100)
    fig_psd_clean = psd_clean.plot(show=False)
    psd_clean_path = out_dir / f"{recording}-psd_after_reviewed_ica.png"
    fig_psd_clean.savefig(psd_clean_path, dpi=300)

    return {
        "raw_10s": str(raw_path),
        "clean_10s": str(clean_path),
        "psd_before": str(psd_raw_path),
        "psd_after": str(psd_clean_path),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Apply reviewed ICA decisions to reconstruct cleaned EEG."
    )
    parser.add_argument("--vhdr", type=Path, required=True, help="Path to the raw .vhdr file.")
    parser.add_argument(
        "--ica-path",
        type=Path,
        required=True,
        help="Path to the saved ICA .fif file.",
    )
    parser.add_argument(
        "--review-json",
        type=Path,
        default=None,
        help="Path to the ICA review JSON. Defaults next to the ICA file.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Path to preprocess summary JSON. Defaults next to the ICA file.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to the ICA file directory.",
    )
    parser.add_argument(
        "--epoch-tmin",
        type=float,
        default=-0.5,
        help="Epoch start for cleaned sensor-space data.",
    )
    parser.add_argument(
        "--epoch-tmax",
        type=float,
        default=3.5,
        help="Epoch end for cleaned sensor-space data.",
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
    args = parser.parse_args()

    vhdr_path = preserve_user_path(args.vhdr)
    ica_path = args.ica_path.resolve()
    if not vhdr_path.exists():
        raise FileNotFoundError(f"Cannot find VHDR file: {vhdr_path}")
    if not ica_path.exists():
        raise FileNotFoundError(f"Cannot find ICA file: {ica_path}")

    out_dir = (args.out_dir or ica_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    recording = infer_recording_name(ica_path)
    review_json = (args.review_json or (out_dir / f"{recording}-ica_component_review.json")).resolve()
    summary_json = (args.summary_json or (out_dir / f"{recording}-preprocess_summary.json")).resolve()

    if not review_json.exists():
        raise FileNotFoundError(f"Cannot find review JSON: {review_json}")
    if not summary_json.exists():
        raise FileNotFoundError(f"Cannot find preprocess summary JSON: {summary_json}")

    review_payload = load_json(review_json)
    summary_payload = load_json(summary_json)

    kept_components, rejected_components = get_kept_components(review_payload)
    if not kept_components and not rejected_components:
        raise RuntimeError(
            "No ICA decisions found. Mark components in the review JSON before applying ICA."
        )

    print(f"Loading raw BrainVision file: {vhdr_path}")
    raw = rebuild_cleaning_raw(vhdr_path, summary_payload)
    raw_before = raw.copy()

    print(f"Loading ICA: {ica_path}")
    ica = mne.preprocessing.read_ica(ica_path, verbose=False)

    ica.exclude = sorted(rejected_components)


    print(f"Explicitly kept components: {kept_components}")
    print(f"Explicitly rejected components: {rejected_components}")
    print(f"Excluding components: {ica.exclude}")
    clean_raw = ica.apply(raw.copy())

    events, event_id = mne.events_from_annotations(clean_raw, verbose=False)
    epochs = mne.Epochs(
        clean_raw,
        events,
        event_id=event_id,
        tmin=args.epoch_tmin,
        tmax=args.epoch_tmax,
        baseline=(args.baseline_start, args.baseline_end),
        preload=True,
        reject_by_annotation=True,
        verbose=False,
    )

    clean_raw_path = out_dir / f"{recording}-clean_raw.fif"
    epochs_path = out_dir / f"{recording}-final-epo.fif"
    clean_raw.save(clean_raw_path, overwrite=True)
    epochs.save(epochs_path, overwrite=True)

    qc_paths = save_qc_figures(raw_before, clean_raw, out_dir, recording)

    apply_summary = {
        "recording": recording,
        "vhdr_path": str(vhdr_path),
        "ica_path": str(ica_path),
        "review_json": str(review_json),
        "preprocess_summary_json": str(summary_json),
        "kept_components": kept_components,
        "excluded_components": list(ica.exclude),
        "epoch_window_s": [args.epoch_tmin, args.epoch_tmax],
        "baseline_s": [args.baseline_start, args.baseline_end],
        "event_id": event_id,
        "n_epochs": int(len(epochs)),
        "outputs": {
            "clean_raw_fif": str(clean_raw_path),
            "epochs_fif": str(epochs_path),
            **qc_paths,
        },
        "suggested_visual_channel": pick_best_channel(clean_raw.ch_names),
    }
    apply_summary_path = out_dir / f"{recording}-apply_reviewed_ica_summary.json"
    write_json(apply_summary_path, apply_summary)

    print(f"Saved cleaned raw: {clean_raw_path}")
    print(f"Saved cleaned epochs: {epochs_path}")
    print(f"Saved apply summary: {apply_summary_path}")


if __name__ == "__main__":
    main()
