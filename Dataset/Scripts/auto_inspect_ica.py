import argparse
import json
from pathlib import Path

import matplotlib
import mne
from mne_icalabel import label_components  # NEW IMPORT

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
    raw.set_eeg_reference("average", projection=False, verbose=False)
    return raw
def auto_label_components(raw, ica, threshold=0.60):
    """
    Runs ICLabel and maps the results to your pipeline's decision format.
    """
    print("Running mne-icalabel...")
    ic_labels = label_components(raw, ica, method='iclabel')
    
    labels = ic_labels["labels"]
    probabilities = ic_labels["y_pred_proba"]
    
    decisions = {}
    for idx, (label, prob) in enumerate(zip(labels, probabilities)):
        prob_pct = f"{prob * 100:.1f}%"
        
        if label == 'brain' and prob >= threshold:
            keep = True
            notes = f"Auto-kept: {label} ({prob_pct})"
        elif label in ['eye blink', 'muscle artifact', 'heart beat', 'channel noise', 'line noise', 'other'] and prob >= threshold:
            keep = False
            notes = f"Auto-rejected: {label} ({prob_pct})"
        else:
            keep = None
            notes = f"Unsure: {label} ({prob_pct}) - Did not meet auto-decision rule. Please review."

        decisions[str(idx)] = {
            "label": label,
            "keep": keep,
            "notes": notes
        }
        
    return decisions

def main():
    parser = argparse.ArgumentParser(
        description="Automatically classify and select ICA components using ICLabel."
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
        required=True,
        help="Raw BrainVision file (Required for ICLabel).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to the ICA file directory.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help="Confidence threshold (0.0 to 1.0) for auto-reject/keep. Default is 0.70.",
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

    summary = load_preprocess_summary(out_dir, recording)
    vhdr_path = preserve_user_path(args.vhdr)
    if not vhdr_path.exists():
        raise FileNotFoundError(f"Cannot find VHDR file: {vhdr_path}")
    if summary is None:
        raise RuntimeError("A preprocess summary JSON is required to rebuild raw data.")
    
    print(f"Rebuilding raw data for ICLabel from: {vhdr_path}")
    raw = rebuild_ica_review_raw(vhdr_path, summary)

    # Run the automated labeling
    component_decisions = auto_label_components(raw, ica, threshold=args.threshold)

    # Build the JSON payload matching your exact schema
    review_json_path = out_dir / f"{recording}-ica_component_review.json"
    
    review_payload = {
        "subject": subject,
        "recording": recording,
        "notes": f"Automatically generated using mne-icalabel with a {args.threshold*100}% confidence threshold.",
        "guidance": {
            "keep_if": ["ICLabel classified as 'brain' with high confidence"],
            "reject_if": ["ICLabel classified as 'eye', 'muscle', 'channel noise', etc. with high confidence"],
        },
        "component_decisions": component_decisions,
        "generated_files": {
            "topographies": [], # Left blank to save disk space and compute time
            "properties": []
        }
    }
    
    write_json(review_json_path, review_payload)
    print(f"Saved automated review JSON: {review_json_path}")
    
    # Print a quick summary to the console
    kept = sum(1 for d in component_decisions.values() if d["keep"] is True)
    rejected = sum(1 for d in component_decisions.values() if d["keep"] is False)
    unsure = sum(1 for d in component_decisions.values() if d["keep"] is None)
    print(f"\n--- Summary ---")
    print(f"✅ Kept: {kept} | ❌ Rejected: {rejected} | ⚠️ Unsure (Needs Review): {unsure}")

if __name__ == "__main__":
    main()