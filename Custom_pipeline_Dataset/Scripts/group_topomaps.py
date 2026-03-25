import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np

matplotlib.use("Agg")

EXCLUDED_NON_EEG_CHANNELS = {"photosensor", "optical", "ecg", "resp"}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_npz_dict(path):
    data = np.load(path)
    return {key: data[key] for key in data.files}


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def select_topomap_channels(ch_names):
    montage = mne.channels.make_standard_montage("standard_1020")
    montage_names = set(montage.ch_names)
    keep_indices = [
        idx
        for idx, name in enumerate(ch_names)
        if name not in EXCLUDED_NON_EEG_CHANNELS and name in montage_names
    ]
    filtered_names = [ch_names[idx] for idx in keep_indices]
    return keep_indices, filtered_names


def collect_subject_maps(outputs_root, mapping):
    subjects = []
    target_conditions = [
        ("Full Field", [1]),
        ("Left Hemifield", [2]),
        ("Right Hemifield", [3]),
        ("Upper Hemifield", [4]),
        ("Lower Hemifield", [5]),
        ("Blank", [18]),
        ("Periphery", [19]),
        ("Fovea", [20]),
    ]

    for sub_dir in sorted(path for path in outputs_root.glob("sub-*") if path.is_dir()):
        band_summary_paths = sorted(sub_dir.glob("*-band_power_summary.json"))
        alpha_paths = sorted(sub_dir.glob("*-alpha_by_condition.npz"))
        gamma_paths = sorted(sub_dir.glob("*-gamma_by_condition.npz"))
        if not band_summary_paths or not alpha_paths or not gamma_paths:
            continue

        band_summary = load_json(band_summary_paths[0])
        alpha_map = load_npz_dict(alpha_paths[0])
        gamma_map = load_npz_dict(gamma_paths[0])
        ch_names = band_summary["ch_names"]
        keep_indices, filtered_ch_names = select_topomap_channels(ch_names)
        if not filtered_ch_names:
            continue

        condition_maps = {}
        for label, codes in target_conditions:
            present = [str(code) for code in codes if str(code) in alpha_map and str(code) in gamma_map]
            if not present:
                continue
            alpha = np.stack([alpha_map[code] for code in present], axis=0).mean(axis=0)[keep_indices]
            gamma = np.stack([gamma_map[code] for code in present], axis=0).mean(axis=0)[keep_indices]
            condition_maps[label] = {
                "alpha": alpha,
                "gamma": gamma,
            }

        if condition_maps:
            subjects.append(
                {
                    "subject": sub_dir.name,
                    "ch_names": filtered_ch_names,
                    "condition_maps": condition_maps,
                }
            )

    return subjects


def aggregate_condition_maps(subjects):
    if not subjects:
        return {}
    labels = sorted(subjects[0]["condition_maps"].keys())
    aggregated = {}
    for label in labels:
        alpha_vals = []
        gamma_vals = []
        for subject in subjects:
            if label not in subject["condition_maps"]:
                continue
            alpha_vals.append(subject["condition_maps"][label]["alpha"])
            gamma_vals.append(subject["condition_maps"][label]["gamma"])
        if not alpha_vals:
            continue
        aggregated[label] = {
            "alpha": np.mean(np.stack(alpha_vals, axis=0), axis=0),
            "gamma": np.mean(np.stack(gamma_vals, axis=0), axis=0),
            "n_subjects": len(alpha_vals),
        }
    return aggregated


def make_info(ch_names, sfreq=200.0):
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    try:
        montage = mne.channels.make_standard_montage("standard_1020")
        info.set_montage(montage, on_missing="ignore")
    except Exception:
        pass
    return info


def plot_condition_grid(aggregated, ch_names, band, out_path):
    labels = list(aggregated.keys())
    n = len(labels)
    cols = min(4, n)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    axes = np.atleast_1d(axes).ravel()

    info = make_info(ch_names)
    data_min = min(float(np.min(aggregated[label][band])) for label in labels)
    data_max = max(float(np.max(aggregated[label][band])) for label in labels)
    vmax = max(abs(data_min), abs(data_max))
    vlim = (-vmax, vmax)

    for ax, label in zip(axes, labels):
        mne.viz.plot_topomap(
            aggregated[label][band],
            info,
            axes=ax,
            show=False,
            contours=4,
            cmap="RdBu_r",
            vlim=vlim,
        )
        ax.set_title(f"{label}\n({band.capitalize()})")

    for ax in axes[len(labels):]:
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Build grand-average topographic maps from subject alpha/gamma outputs."
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(__file__).resolve().parent / "condition_mapping.json",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    outputs_root = args.outputs_root.resolve()
    mapping = load_json(args.mapping_json.resolve())
    out_dir = (args.out_dir or outputs_root).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    subjects = collect_subject_maps(outputs_root, mapping)
    if not subjects:
        raise RuntimeError("No subject-level by-condition files were found for topomap aggregation.")

    aggregated = aggregate_condition_maps(subjects)
    ch_names = subjects[0]["ch_names"]

    gamma_path = out_dir / "Condition_Wise_Gamma_Topomaps_rebuilt.png"
    alpha_path = out_dir / "Condition_Wise_Alpha_Topomaps_rebuilt.png"
    plot_condition_grid(aggregated, ch_names, "gamma", gamma_path)
    plot_condition_grid(aggregated, ch_names, "alpha", alpha_path)

    payload = {
        "n_subjects": len(subjects),
        "subjects": [row["subject"] for row in subjects],
        "conditions": {
            label: {"n_subjects": aggregated[label]["n_subjects"]}
            for label in aggregated
        },
        "outputs": {
            "gamma_topomaps": str(gamma_path),
            "alpha_topomaps": str(alpha_path),
        },
    }
    save_json(out_dir / "group_topomaps_summary.json", payload)
    print(f"Saved rebuilt group topomaps into: {out_dir}")


if __name__ == "__main__":
    main()
