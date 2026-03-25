"""
Retinotopy model fitting: Linear summation vs Divisive Normalization.

Compares linear and divisive-normalization predictions against observed
full-field responses across spatial partitions (hemifields, quadrants,
octants, fovea/periphery).

This replaces: Custom_pipeline_Dataset/Scripts/retinotopy_model_fit.py

Usage:
    python retinotopy_model_fit.py
"""

import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (
    ALL_SUBJECTS,
    choose_channel,
    get_custom_output_dir,
    get_group_output_dir,
    load_json,
    mean_code_value,
    save_json,
)


def load_npz_dict(path):
    data = np.load(path)
    return {k: data[k] for k in data.files}


def divisive_prediction(parts, sigma=0.5):
    """Divisive normalization: sum(parts) / (1 + sigma * (N-1))."""
    parts = np.asarray(parts, dtype=float)
    if len(parts) == 0:
        return np.nan
    return parts.sum() / (1.0 + sigma * (len(parts) - 1))


def valid_parts(values):
    return [v for v in values if v is not None and not np.isnan(v)]


def build_subject_group_values(alpha_map, gamma_map, pick_idx):
    """Build spatial partition values for one subject."""
    return {
        "full": {
            "alpha": mean_code_value(alpha_map, [1], pick_idx),
            "gamma": mean_code_value(gamma_map, [1], pick_idx),
        },
        "blank": {
            "alpha": mean_code_value(alpha_map, [18], pick_idx),
            "gamma": mean_code_value(gamma_map, [18], pick_idx),
        },
        "left_right": {
            "alpha_parts": [
                mean_code_value(alpha_map, [2], pick_idx),
                mean_code_value(alpha_map, [3], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [2], pick_idx),
                mean_code_value(gamma_map, [3], pick_idx),
            ],
        },
        "top_bottom": {
            "alpha_parts": [
                mean_code_value(alpha_map, [4], pick_idx),
                mean_code_value(alpha_map, [5], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [4], pick_idx),
                mean_code_value(gamma_map, [5], pick_idx),
            ],
        },
        "quadrants": {
            "alpha_parts": [mean_code_value(alpha_map, [c], pick_idx) for c in [6, 7, 8, 9]],
            "gamma_parts": [mean_code_value(gamma_map, [c], pick_idx) for c in [6, 7, 8, 9]],
        },
        "octants": {
            "alpha_parts": [mean_code_value(alpha_map, [c], pick_idx) for c in range(10, 18)],
            "gamma_parts": [mean_code_value(gamma_map, [c], pick_idx) for c in range(10, 18)],
        },
        "fovea_periphery": {
            "alpha_parts": [
                mean_code_value(alpha_map, [20], pick_idx),
                mean_code_value(alpha_map, [19], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [20], pick_idx),
                mean_code_value(gamma_map, [19], pick_idx),
            ],
        },
    }


def compute_errors(group_values, sigma=0.5):
    """Compare linear vs divnorm predictions to observed full-field."""
    full_alpha = group_values["full"]["alpha"]
    full_gamma = group_values["full"]["gamma"]
    blank_alpha = group_values["blank"]["alpha"]

    results = {}
    for name in ["left_right", "top_bottom", "quadrants", "octants", "fovea_periphery"]:
        a_parts = valid_parts(group_values[name]["alpha_parts"])
        g_parts = valid_parts(group_values[name]["gamma_parts"])

        a_linear = np.sum(a_parts)
        a_blank = np.sum([p - blank_alpha for p in a_parts]) if blank_alpha is not None else np.nan
        a_divnorm = divisive_prediction(a_parts, sigma)
        g_linear = np.sum(g_parts)
        g_divnorm = divisive_prediction(g_parts, sigma)

        results[name] = {
            "alpha": {
                "observed_full": full_alpha,
                "linear_prediction": float(a_linear),
                "divnorm_prediction": float(a_divnorm),
                "blank_corrected_linear": float(a_blank),
                "linear_mae": float(abs(a_linear - full_alpha)),
                "divnorm_mae": float(abs(a_divnorm - full_alpha)),
            },
            "gamma": {
                "observed_full": full_gamma,
                "linear_prediction": float(g_linear),
                "divnorm_prediction": float(g_divnorm),
                "linear_mae": float(abs(g_linear - full_gamma)),
                "divnorm_mae": float(abs(g_divnorm - full_gamma)),
            },
        }
    return results


def aggregate_errors(per_subject_results):
    """Average model errors across subjects."""
    groups = ["left_right", "top_bottom", "quadrants", "octants", "fovea_periphery"]
    aggregated = {}
    for grp in groups:
        a_lin, a_div, g_lin, g_div = [], [], [], []
        for row in per_subject_results:
            if grp not in row["errors"]:
                continue
            e = row["errors"][grp]
            a_lin.append(e["alpha"]["linear_mae"])
            a_div.append(e["alpha"]["divnorm_mae"])
            g_lin.append(e["gamma"]["linear_mae"])
            g_div.append(e["gamma"]["divnorm_mae"])
        aggregated[grp] = {
            "alpha_linear_mae_mean": float(np.mean(a_lin)) if a_lin else None,
            "alpha_divnorm_mae_mean": float(np.mean(a_div)) if a_div else None,
            "gamma_linear_mae_mean": float(np.mean(g_lin)) if g_lin else None,
            "gamma_divnorm_mae_mean": float(np.mean(g_div)) if g_div else None,
            "n_subjects": len(a_lin),
        }
    return aggregated


def plot_error_bars(aggregated, out_path):
    labels = list(aggregated.keys())
    x = np.arange(len(labels))
    width = 0.35

    alpha_lin = [aggregated[l].get("alpha_linear_mae_mean", 0) or 0 for l in labels]
    alpha_div = [aggregated[l].get("alpha_divnorm_mae_mean", 0) or 0 for l in labels]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    axes[0].bar(x - width / 2, alpha_lin, width, label="Linear", color="#8ecae6")
    axes[0].bar(x + width / 2, alpha_div, width, label="DivNorm", color="#219ebc")
    axes[0].set_title("Alpha: Linear vs DivNorm MAE")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=30)
    axes[0].legend()

    gamma_lin = [aggregated[l].get("gamma_linear_mae_mean", 0) or 0 for l in labels]
    gamma_div = [aggregated[l].get("gamma_divnorm_mae_mean", 0) or 0 for l in labels]

    axes[1].bar(x - width / 2, gamma_lin, width, label="Linear", color="#f4a261")
    axes[1].bar(x + width / 2, gamma_div, width, label="DivNorm", color="#e76f51")
    axes[1].set_title("Gamma: Linear vs DivNorm MAE")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=30)
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Retinotopy model fitting")
    parser.add_argument("--sigma", type=float, default=0.5, help="DivNorm sigma")
    args = parser.parse_args()

    per_subject = []
    for sub in ALL_SUBJECTS:
        out_dir = get_custom_output_dir(sub)
        prefix = f"sub-{sub}_ses-01_task-visual"
        alpha_path = out_dir / f"{prefix}-alpha_by_condition.npz"
        gamma_path = out_dir / f"{prefix}-gamma_by_condition.npz"
        summary_path = out_dir / f"{prefix}-band_power_summary.json"

        if not alpha_path.exists() or not gamma_path.exists():
            continue

        alpha_map = load_npz_dict(alpha_path)
        gamma_map = load_npz_dict(gamma_path)
        bp_summary = load_json(summary_path)
        ch_names = bp_summary["ch_names"]
        pick_ch = choose_channel(ch_names)
        pick_idx = ch_names.index(pick_ch)

        gv = build_subject_group_values(alpha_map, gamma_map, pick_idx)
        errors = compute_errors(gv, sigma=args.sigma)
        per_subject.append({
            "subject": f"sub-{sub}",
            "channel": pick_ch,
            "errors": errors,
        })

    if not per_subject:
        print("No subjects with band power data found.")
        return

    aggregated = aggregate_errors(per_subject)

    group_dir = get_group_output_dir()
    plot_error_bars(aggregated, group_dir / "retinotopy_model_fit.png")
    save_json(group_dir / "retinotopy_model_fit_summary.json", {
        "sigma": args.sigma,
        "n_subjects": len(per_subject),
        "aggregated": aggregated,
        "per_subject": per_subject,
    })
    print(f"\nSaved model fit summary to {group_dir}")
    print(f"  Subjects included: {len(per_subject)}")
    for grp, vals in aggregated.items():
        a_lin = vals.get("alpha_linear_mae_mean", 0) or 0
        a_div = vals.get("alpha_divnorm_mae_mean", 0) or 0
        ratio = a_lin / a_div if a_div > 0 else float("inf")
        print(f"  {grp}: alpha linear/divnorm ratio = {ratio:.1f}x")


if __name__ == "__main__":
    main()
