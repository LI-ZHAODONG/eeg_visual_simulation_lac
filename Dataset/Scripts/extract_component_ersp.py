import argparse
import json
from pathlib import Path

import mne
import numpy as np


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


def rebuild_ica_prep_raw(vhdr_path, preprocess_summary):
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

    band = preprocessing.get("ica_filter_band_hz", [1.0, 100.0])
    raw.filter(l_freq=band[0], h_freq=band[1], fir_design="firwin", verbose=False)

    sfreq = preprocessing.get("ica_training_resample_hz", 200.0)
    raw.resample(sfreq, verbose=False)
    raw.set_eeg_reference("average", projection=False, verbose=False)
    return raw


def get_kept_components(review_payload):
    decisions = review_payload.get("component_decisions", {})
    kept = []
    for key, value in decisions.items():
        if value.get("keep") is True:
            kept.append(int(key))
    return sorted(kept)


def baseline_correct_log_power(power, times, baseline):
    baseline_mask = (times >= baseline[0]) & (times < baseline[1])
    if not baseline_mask.any():
        raise RuntimeError(f"No samples found in baseline window {baseline}.")

    log_power = np.log10(np.maximum(power, np.finfo(float).eps))
    baseline_mean = log_power[..., baseline_mask].mean(axis=-1, keepdims=True)
    return log_power - baseline_mean


def main():
    parser = argparse.ArgumentParser(
        description="Extract single-trial component ERSPs from retained ICA components."
    )
    parser.add_argument("--vhdr", type=Path, required=True, help="Path to the raw .vhdr file.")
    parser.add_argument("--ica-path", type=Path, required=True, help="Path to the ICA .fif file.")
    parser.add_argument(
        "--review-json",
        type=Path,
        default=None,
        help="Path to ICA review JSON. Defaults next to the ICA file.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Path to preprocess summary JSON. Defaults next to the ICA file.",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--epoch-tmin",
        type=float,
        default=-1.6,
        help="Buffered epoch start before cropping.",
    )
    parser.add_argument(
        "--epoch-tmax",
        type=float,
        default=4.6,
        help="Buffered epoch end before cropping.",
    )
    parser.add_argument(
        "--crop-tmin",
        type=float,
        default=-1.0,
        help="Start of cropped analysis window.",
    )
    parser.add_argument(
        "--crop-tmax",
        type=float,
        default=4.0,
        help="End of cropped analysis window.",
    )
    parser.add_argument(
        "--baseline-start",
        type=float,
        default=-0.5,
        help="Baseline start time for trial-wise log-power correction.",
    )
    parser.add_argument(
        "--baseline-end",
        type=float,
        default=0.0,
        help="Baseline end time for trial-wise log-power correction.",
    )
    parser.add_argument(
        "--fmin",
        type=float,
        default=4.0,
        help="Lowest frequency for ERSP analysis.",
    )
    parser.add_argument(
        "--fmax",
        type=float,
        default=100.0,
        help="Highest frequency for ERSP analysis.",
    )
    parser.add_argument(
        "--fstep",
        type=float,
        default=2.0,
        help="Frequency spacing for ERSP analysis.",
    )
    parser.add_argument(
        "--n-cycles-factor",
        type=float,
        default=0.25,
        help="Number of Morlet cycles as factor * frequency.",
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
    preprocess_summary = load_json(summary_json)
    kept_components = get_kept_components(review_payload)
    if not kept_components:
        raise RuntimeError("No kept ICA components found in the review JSON.")

    print(f"Rebuilding ICA-prep raw: {vhdr_path}")
    raw = rebuild_ica_prep_raw(vhdr_path, preprocess_summary)

    print(f"Loading ICA: {ica_path}")
    ica = mne.preprocessing.read_ica(ica_path, verbose=False)
    source_raw = ica.get_sources(raw)
    source_raw.pick(kept_components)

    events, event_id = mne.events_from_annotations(source_raw, verbose=False)
    if len(events) == 0:
        raise RuntimeError("No events found for ERSP extraction.")

    source_epochs = mne.Epochs(
        source_raw,
        events,
        event_id=event_id,
        tmin=args.epoch_tmin,
        tmax=args.epoch_tmax,
        baseline=None,
        preload=True,
        reject_by_annotation=True,
        verbose=False,
    )
    if len(source_epochs) == 0:
        raise RuntimeError("Source epochs are empty.")

    freqs = np.arange(args.fmin, args.fmax + args.fstep, args.fstep)
    n_cycles = np.maximum(freqs * args.n_cycles_factor, 2.0)

    print(
        f"Computing Morlet TFR for {len(kept_components)} kept components, "
        f"{len(freqs)} frequencies, {len(source_epochs)} epochs."
    )
    source_picks = list(range(len(source_epochs.ch_names)))
    power = mne.time_frequency.tfr_morlet(
        source_epochs,
        picks=source_picks,
        freqs=freqs,
        n_cycles=n_cycles,
        use_fft=True,
        return_itc=False,
        average=False,
        output="power",
        verbose=False,
    )
    power.crop(tmin=args.crop_tmin, tmax=args.crop_tmax)

    corrected = baseline_correct_log_power(
        power.data,
        power.times,
        baseline=(args.baseline_start, args.baseline_end),
    )
    import matplotlib.pyplot as plt

    for comp_i, comp_idx in enumerate(kept_components):
        fig, ax = plt.subplots(figsize=(8, 4))
        im = ax.imshow(
            corrected[:, comp_i, :, :].mean(axis=0),
            aspect="auto",
            origin="lower",
            extent=[power.times[0], power.times[-1], power.freqs[0], power.freqs[-1]],
        )
        ax.set_title(f"{recording} ICA {comp_idx:02d} ERSP")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Frequency (Hz)")
        plt.colorbar(im, ax=ax, label="Log power change")
        fig.tight_layout()

        fig_path = out_dir / f"{recording}-ica_ersp_ic{comp_idx:02d}.png"
        fig.savefig(fig_path, dpi=300)
        plt.close(fig)
        
    ersp_path = out_dir / f"{recording}-component_ersp.npy"
    event_codes_path = out_dir / f"{recording}-component_ersp_event_codes.npy"
    kept_components_path = out_dir / f"{recording}-component_ersp_kept_components.npy"
    freqs_path = out_dir / f"{recording}-component_ersp_freqs.npy"
    times_path = out_dir / f"{recording}-component_ersp_times.npy"

    np.save(ersp_path, corrected)
    np.save(event_codes_path, source_epochs.events[:, 2])
    np.save(kept_components_path, np.array(kept_components, dtype=int))
    np.save(freqs_path, power.freqs)
    np.save(times_path, power.times)

    summary = {
        "recording": recording,
        "vhdr_path": str(vhdr_path),
        "ica_path": str(ica_path),
        "review_json": str(review_json),
        "preprocess_summary_json": str(summary_json),
        "kept_components": kept_components,
        "n_epochs": int(len(source_epochs)),
        "n_components": int(len(kept_components)),
        "freq_range_hz": [args.fmin, args.fmax],
        "freq_step_hz": args.fstep,
        "analysis_window_s": [args.crop_tmin, args.crop_tmax],
        "buffered_epoch_window_s": [args.epoch_tmin, args.epoch_tmax],
        "baseline_window_s": [args.baseline_start, args.baseline_end],
        "output_shape": list(corrected.shape),
        "outputs": {
            "ersp_npy": str(ersp_path),
            "event_codes_npy": str(event_codes_path),
            "kept_components_npy": str(kept_components_path),
            "freqs_npy": str(freqs_path),
            "times_npy": str(times_path),
        },
    }
    summary_path = out_dir / f"{recording}-component_ersp_summary.json"
    write_json(summary_path, summary)

    print(f"Saved ERSP array: {ersp_path}")
    print(f"Saved ERSP summary: {summary_path}")


if __name__ == "__main__":
    main()
