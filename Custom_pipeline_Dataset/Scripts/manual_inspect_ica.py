import argparse
import json
from pathlib import Path

import matplotlib
import mne

matplotlib.use("Agg")


def infer_recording_name(ica_path):
    name = ica_path.name
    if name.endswith("-ica.fif"):
        return name[: -len("-ica.fif")]
    return ica_path.stem


def infer_subject_from_name(recording):
    for part in recording.split("_"):
        if part.startswith("sub-"):
            return part
    return "sub-unknown"


def preserve_user_path(path_like):
    path = Path(path_like).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_preprocess_summary(out_dir, recording):
    summary_path = out_dir / f"{recording}-preprocess_summary.json"
    if summary_path.exists():
        return load_json(summary_path)
    return None


def rebuild_ica_review_raw(vhdr_path, summary):
    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True, verbose=False)

    preprocessing = summary.get("preprocessing", {})
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
    return raw


def save_component_topographies(ica, out_dir, recording):
    figs = ica.plot_components(show=False)
    saved = []

    if isinstance(figs, list):
        for idx, fig in enumerate(figs):
            path = out_dir / f"{recording}-ica_components_{idx}.png"
            fig.savefig(path, dpi=300)
            saved.append(str(path))
    else:
        path = out_dir / f"{recording}-ica_components.png"
        figs.savefig(path, dpi=300)
        saved.append(str(path))

    return saved


def save_component_properties(ica, raw, out_dir, recording, picks=None):
    if picks is None:
        picks = list(range(min(ica.n_components_, 60)))

    saved = []
    for comp_idx in picks:
        figs = ica.plot_properties(raw, picks=[comp_idx], show=False)
        if not isinstance(figs, list):
            figs = [figs]
        for fig_idx, fig in enumerate(figs):
            path = out_dir / f"{recording}-ica_properties_ic{comp_idx:02d}_{fig_idx}.png"
            fig.savefig(path, dpi=300)
            saved.append(str(path))
    return saved


def ensure_review_template(path, subject, recording, n_components):
    if path.exists():
        return load_json(path)

    payload = {
        "subject": subject,
        "recording": recording,
        "notes": "Review each component using scalp map, spectrum, and time course.",
        "guidance": {
            "keep_if": [
                "posterior topography consistent with visual cortex",
                "narrowband alpha or gamma rather than broadband muscle activity",
                "time course looks physiologic rather than spiky or blink-like",
            ],
            "reject_if": [
                "frontal blink pattern",
                "lateral eye movement pattern",
                "broadband peripheral muscle activity",
                "single-channel or non-physiologic noise",
            ],
        },
        "component_decisions": {
            str(idx): {
                "label": "unreviewed",
                "keep": None,
                "notes": "",
            }
            for idx in range(n_components)
        },
    }
    write_json(path, payload)
    return payload


def main():
    parser = argparse.ArgumentParser(
        description="Generate review figures for manually selecting ICA components."
    )
    parser.add_argument(
        "--ica-path",
        type=Path,
        required=True,
        help="Path to a saved ICA .fif file.",
    )
    parser.add_argument(
        "--vhdr",
        type=Path,
        default=None,
        help="Optional raw BrainVision file for ICA property plots.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to the ICA file directory.",
    )
    parser.add_argument(
        "--max-components",
        type=int,
        default=20,
        help="How many components to render property plots for when raw data is available.",
    )
    args = parser.parse_args()

    ica_path = args.ica_path.resolve()
    if not ica_path.exists():
        raise FileNotFoundError(f"Cannot find ICA file: {ica_path}")

    out_dir = (args.out_dir or ica_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    recording = infer_recording_name(ica_path)
    subject = infer_subject_from_name(recording)

    print(f"Loading ICA: {ica_path}")
    ica = mne.preprocessing.read_ica(ica_path, verbose=False)

    topography_paths = save_component_topographies(ica, out_dir, recording)

    raw = None
    summary = load_preprocess_summary(out_dir, recording)
    if args.vhdr is not None:
        vhdr_path = preserve_user_path(args.vhdr)
        if not vhdr_path.exists():
            raise FileNotFoundError(f"Cannot find VHDR file: {vhdr_path}")
        if summary is None:
            raise RuntimeError(
                "A preprocess summary JSON is required to rebuild ICA review raw data."
            )
        print(f"Rebuilding ICA review raw from: {vhdr_path}")
        raw = rebuild_ica_review_raw(vhdr_path, summary)

    property_paths = []
    if raw is not None:
        picks = list(range(min(ica.n_components_, args.max_components)))
        property_paths = save_component_properties(ica, raw, out_dir, recording, picks=picks)

    review_json_path = out_dir / f"{recording}-ica_component_review.json"
    review_payload = ensure_review_template(
        review_json_path,
        subject=subject,
        recording=recording,
        n_components=ica.n_components_,
    )
    review_payload["generated_files"] = {
        "topographies": topography_paths,
        "properties": property_paths,
    }
    write_json(review_json_path, review_payload)

    print(f"Saved review JSON: {review_json_path}")
    print(f"Saved topography figure(s): {len(topography_paths)}")
    if raw is None:
        print("Property plots were skipped because no --vhdr file was provided.")
    else:
        print(f"Saved property figure(s): {len(property_paths)}")


if __name__ == "__main__":
    main()
