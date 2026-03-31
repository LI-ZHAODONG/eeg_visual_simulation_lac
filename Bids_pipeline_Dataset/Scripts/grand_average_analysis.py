import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import TRIGGER_CODE_TO_NAME

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_npz_dict(path):
    data = np.load(path)
    return {key: data[key] for key in data.files}


def choose_channel(ch_names):
    for ch in ["Oz", "O1", "O2", "POz", "Pz", "Cz"]:
        if ch in ch_names:
            return ch
    return ch_names[0]


def group_scalar(code_map, codes, pick_idx):
    present_keys = []
    for c in codes:
        str_c = str(c)
        name = TRIGGER_CODE_TO_NAME.get(c, str_c)
        if name in code_map:
            present_keys.append(name)
        elif str_c in code_map:
            present_keys.append(str_c)
            
    if not present_keys:
        return None
    stacked = np.stack([code_map[key] for key in present_keys], axis=0)
    return float(stacked.mean(axis=0)[pick_idx])


def collect_subject_rows(subject_dirs, mapping):
    subjects = []
    orientation_codes = mapping["families"]["orientation"]["codes"]

    for sub_dir in sorted(subject_dirs):
        band_summary_paths = sorted(sub_dir.glob("*-band_power_summary.json"))
        alpha_paths = sorted(sub_dir.glob("*-alpha_by_condition.npz"))
        gamma_paths = sorted(sub_dir.glob("*-gamma_by_condition.npz"))
        if not band_summary_paths or not alpha_paths or not gamma_paths:
            continue

        band_summary = load_json(band_summary_paths[0])
        alpha_map = load_npz_dict(alpha_paths[0])
        gamma_map = load_npz_dict(gamma_paths[0])

        ch_names = band_summary["ch_names"]
        pick_ch = choose_channel(ch_names)
        pick_idx = ch_names.index(pick_ch)

        retinotopy_rows = []
        for label, codes in [
            ("full", mapping["retinotopy_groups"]["full_field"]),
            ("left", mapping["retinotopy_groups"]["left_hemifield"]),
            ("right", mapping["retinotopy_groups"]["right_hemifield"]),
            ("top", mapping["retinotopy_groups"]["upper_hemifield"]),
            ("bottom", mapping["retinotopy_groups"]["lower_hemifield"]),
            ("blank", mapping["retinotopy_groups"]["blank"]),
            ("periph", mapping["retinotopy_groups"]["periphery"]),
            ("fovea", mapping["retinotopy_groups"]["fovea"]),
        ]:
            alpha = group_scalar(alpha_map, codes, pick_idx)
            gamma = group_scalar(gamma_map, codes, pick_idx)
            if alpha is None or gamma is None:
                continue
            retinotopy_rows.append({"label": label, "alpha": alpha, "gamma": gamma})

        orientation_rows = []
        for code in orientation_codes:
            key_str = str(code)
            key = TRIGGER_CODE_TO_NAME.get(code, key_str)
            if key not in alpha_map and key_str not in alpha_map:
                continue
            use_key = key if key in alpha_map else key_str
            orientation_rows.append(
                {
                    "code": int(code),
                    "deg": float(mapping["orientation_code_degrees"][key_str]),
                    "alpha": float(alpha_map[use_key][pick_idx]),
                    "gamma": float(gamma_map[use_key][pick_idx]),
                }
            )

        subjects.append(
            {
                "subject": sub_dir.name,
                "picked_channel": pick_ch,
                "retinotopy_rows": retinotopy_rows,
                "orientation_rows": orientation_rows,
            }
        )

    return subjects


def aggregate_rows(subjects, key):
    labels = []
    if not subjects:
        return []
    for row in subjects[0][key]:
        labels.append(row["label"])

    aggregated = []
    for label in labels:
        alpha_vals = []
        gamma_vals = []
        for subject in subjects:
            match = next((row for row in subject[key] if row["label"] == label), None)
            if match is None:
                continue
            alpha_vals.append(match["alpha"])
            gamma_vals.append(match["gamma"])
        if not alpha_vals:
            continue
        aggregated.append(
            {
                "label": label,
                "alpha_mean": float(np.mean(alpha_vals)),
                "alpha_sem": float(np.std(alpha_vals, ddof=1) / np.sqrt(len(alpha_vals)))
                if len(alpha_vals) > 1
                else 0.0,
                "gamma_mean": float(np.mean(gamma_vals)),
                "gamma_sem": float(np.std(gamma_vals, ddof=1) / np.sqrt(len(gamma_vals)))
                if len(gamma_vals) > 1
                else 0.0,
                "n_subjects": len(alpha_vals),
            }
        )
    return aggregated


def aggregate_orientation(subjects):
    if not subjects:
        return []
    codes = [row["code"] for row in subjects[0]["orientation_rows"]]
    aggregated = []
    for code in codes:
        alpha_vals = []
        gamma_vals = []
        deg = None
        for subject in subjects:
            match = next((row for row in subject["orientation_rows"] if row["code"] == code), None)
            if match is None:
                continue
            alpha_vals.append(match["alpha"])
            gamma_vals.append(match["gamma"])
            deg = match["deg"]
        if not alpha_vals:
            continue
        aggregated.append(
            {
                "code": int(code),
                "deg": float(deg),
                "alpha_mean": float(np.mean(alpha_vals)),
                "alpha_sem": float(np.std(alpha_vals, ddof=1) / np.sqrt(len(alpha_vals)))
                if len(alpha_vals) > 1
                else 0.0,
                "gamma_mean": float(np.mean(gamma_vals)),
                "gamma_sem": float(np.std(gamma_vals, ddof=1) / np.sqrt(len(gamma_vals)))
                if len(gamma_vals) > 1
                else 0.0,
                "n_subjects": len(alpha_vals),
            }
        )
    return aggregated


def plot_group_bars(rows, out_path, title):
    labels = [row["label"] for row in rows]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].bar(labels, [row["gamma_mean"] for row in rows], yerr=[row["gamma_sem"] for row in rows], color="#e76f51", capsize=3)
    axes[0].set_title(f"Gamma: {title}")
    axes[0].tick_params(axis="x", rotation=35)

    axes[1].bar(labels, [row["alpha_mean"] for row in rows], yerr=[row["alpha_sem"] for row in rows], color="#8ecae6", capsize=3)
    axes[1].set_title(f"Alpha: {title}")
    axes[1].tick_params(axis="x", rotation=35)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_group_scatter(rows, out_path, title):
    alpha = np.array([row["alpha_mean"] for row in rows], dtype=float)
    gamma = np.array([row["gamma_mean"] for row in rows], dtype=float)
    labels = [row["label"] for row in rows]
    corr = float(np.corrcoef(alpha, gamma)[0, 1]) if len(rows) > 1 else float("nan")

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(alpha, gamma, color="#444444")
    if len(rows) > 1:
        slope, intercept = np.polyfit(alpha, gamma, 1)
        ax.plot(np.sort(alpha), slope * np.sort(alpha) + intercept, "--", color="#1d3557")
    for x, y, label in zip(alpha, gamma, labels):
        ax.text(x, y, label, fontsize=8)
    ax.set_title(f"{title} (r = {corr:.2f})" if not np.isnan(corr) else title)
    ax.set_xlabel("Alpha Power")
    ax.set_ylabel("Gamma Power")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return corr


def plot_orientation_triggers(rows, out_path):
    labels = [str(row["code"]) for row in rows]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].bar(labels, [row["gamma_mean"] for row in rows], yerr=[row["gamma_sem"] for row in rows], color="#e76f51", capsize=3)
    axes[0].set_title("Grand Average Gamma by Orientation Trigger")
    axes[0].tick_params(axis="x", rotation=45)

    axes[1].bar(labels, [row["alpha_mean"] for row in rows], yerr=[row["alpha_sem"] for row in rows], color="#8ecae6", capsize=3)
    axes[1].set_title("Grand Average Alpha by Orientation Trigger")
    axes[1].tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate subject-level alpha/gamma outputs into group summaries."
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
        help="Root folder containing sub-* output directories.",
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(__file__).resolve().parent / "condition_mapping.json",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    # Use BIDS outputs path if not explicitly provided
    if args.outputs_root == Path(__file__).resolve().parents[1] / "outputs":
        outputs_root = Path(__file__).resolve().parents[1] / "outputs" / "derivatives" / "bids_analysis"
    else:
        outputs_root = args.outputs_root.resolve()
        
    mapping = load_json(args.mapping_json.resolve())
    out_dir = (args.out_dir or (outputs_root / "group_level")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    subject_dirs = [path for path in outputs_root.glob("sub-*") if path.is_dir()]
    subjects = collect_subject_rows(subject_dirs, mapping)
    if not subjects:
        raise RuntimeError("No subject-level by-condition outputs were found to aggregate.")

    retinotopy_rows = aggregate_rows(subjects, "retinotopy_rows")
    orientation_rows = aggregate_orientation(subjects)

    retinotopy_bar = out_dir / "GA_retinotopy_summary.png"
    retinotopy_scatter = out_dir / "GA_retinotopy_scatter.png"
    orientation_bar = out_dir / "GA_orientation_trigger_summary.png"

    plot_group_bars(retinotopy_rows, retinotopy_bar, "Retinotopy")
    ret_corr = plot_group_scatter(retinotopy_rows, retinotopy_scatter, "Retinotopy Alpha vs Gamma")
    plot_orientation_triggers(orientation_rows, orientation_bar)

    payload = {
        "n_subjects": len(subjects),
        "subjects": [row["subject"] for row in subjects],
        "retinotopy_rows": retinotopy_rows,
        "orientation_rows": orientation_rows,
        "retinotopy_alpha_gamma_correlation": ret_corr,
        "outputs": {
            "retinotopy_summary": str(retinotopy_bar),
            "retinotopy_scatter": str(retinotopy_scatter),
            "orientation_trigger_summary": str(orientation_bar),
        },
    }
    save_json(out_dir / "grand_average_summary.json", payload)
    print(f"Saved grand-average summaries into: {out_dir}")


if __name__ == "__main__":
    main()
