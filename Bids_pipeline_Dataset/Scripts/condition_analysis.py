"""
Retinotopy condition analysis.

Reads per-condition alpha/gamma power and builds spatial tuning summaries,
bar charts, and alpha-vs-gamma scatter plots.

This replaces: Dataset/Scripts/condition_analysis.py

Usage:
    python condition_analysis.py              # all subjects
    python condition_analysis.py --subject 01  # one subject
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
    group_mean,
    load_condition_mapping,
    save_json,
)


def load_npz_dict(path):
    data = np.load(path)
    return {k: data[k] for k in data.files}


def build_group_series(mapping, alpha_map, gamma_map, pick_idx):
    """Build retinotopy summary rows for all spatial groups."""
    groups = [
        ("full", mapping["retinotopy_groups"]["full_field"]),
        ("left", mapping["retinotopy_groups"]["left_hemifield"]),
        ("right", mapping["retinotopy_groups"]["right_hemifield"]),
        ("top", mapping["retinotopy_groups"]["upper_hemifield"]),
        ("bottom", mapping["retinotopy_groups"]["lower_hemifield"]),
        ("quad_BR", [6]),
        ("quad_BL", [7]),
        ("quad_TL", [8]),
        ("quad_TR", [9]),
        ("blank", mapping["retinotopy_groups"]["blank"]),
        ("periphery", mapping["retinotopy_groups"]["periphery"]),
        ("fovea", mapping["retinotopy_groups"]["fovea"]),
    ]
    summary = []
    for label, codes in groups:
        alpha = group_mean(alpha_map, codes)
        gamma = group_mean(gamma_map, codes)
        if alpha is None or gamma is None:
            continue
        summary.append({
            "label": label,
            "codes": codes,
            "alpha_mean": float(alpha[pick_idx]),
            "gamma_mean": float(gamma[pick_idx]),
        })
    return summary


def plot_band_bars(summary, out_path, title, field):
    labels = [r["label"] for r in summary]
    values = [r[field] for r in summary]
    fig, ax = plt.subplots(figsize=(14, 5))
    color = "#f28e2b" if "gamma" in field else "#7ea6d8"
    ax.bar(labels, values, color=color)
    ax.set_title(title)
    ax.set_ylabel("Mean Power")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_alpha_gamma_scatter(summary, out_path):
    alpha = np.array([r["alpha_mean"] for r in summary])
    gamma = np.array([r["gamma_mean"] for r in summary])
    labels = [r["label"] for r in summary]

    slope, intercept = np.polyfit(alpha, gamma, 1)
    corr = float(np.corrcoef(alpha, gamma)[0, 1])

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].scatter(alpha, gamma, color="#555555")
    axes[0].plot(np.sort(alpha), slope * np.sort(alpha) + intercept, "--", color="#1f77b4")
    for x, y, lbl in zip(alpha, gamma, labels):
        axes[0].text(x, y, lbl, fontsize=8)
    axes[0].set_title(f"Alpha vs Gamma (r = {corr:.2f})")
    axes[0].set_xlabel("Alpha Power")
    axes[0].set_ylabel("Gamma Power")

    residuals = gamma - (slope * alpha + intercept)
    axes[1].bar(labels, residuals, color="#888888")
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_title("Residuals from Alpha-Gamma Fit")
    axes[1].tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return corr, residuals.tolist()


def process_subject(subject):
    """Build retinotopy summaries for one subject."""
    print(f"\n  Condition analysis for sub-{subject}")

    out_dir = get_custom_output_dir(subject)
    prefix = f"sub-{subject}_ses-01_task-visual"

    alpha_path = out_dir / f"{prefix}-alpha_by_condition.npz"
    gamma_path = out_dir / f"{prefix}-gamma_by_condition.npz"
    summary_path = out_dir / f"{prefix}-band_power_summary.json"

    if not alpha_path.exists() or not gamma_path.exists():
        print(f"    SKIP: band power files not found — run extract_band_power first")
        return

    alpha_map = load_npz_dict(alpha_path)
    gamma_map = load_npz_dict(gamma_path)
    mapping = load_condition_mapping()

    from utils import load_json
    bp_summary = load_json(summary_path)
    ch_names = bp_summary["ch_names"]
    pick_ch = choose_channel(ch_names)
    pick_idx = ch_names.index(pick_ch)

    summary = build_group_series(mapping, alpha_map, gamma_map, pick_idx)

    # Plots
    plot_band_bars(summary, out_dir / "retinotopy_gamma_summary.png",
                   f"Gamma (40-80 Hz, {pick_ch})", "gamma_mean")
    plot_band_bars(summary, out_dir / "retinotopy_alpha_summary.png",
                   f"Alpha (8-13 Hz, {pick_ch})", "alpha_mean")
    corr, residuals = plot_alpha_gamma_scatter(
        summary, out_dir / "retinotopy_alpha_gamma_scatter.png"
    )

    payload = {
        "subject": f"sub-{subject}",
        "picked_channel": pick_ch,
        "groups": summary,
        "alpha_gamma_correlation": corr,
        "residuals": residuals,
    }
    save_json(out_dir / "retinotopy_summary.json", payload)
    print(f"    Saved retinotopy summaries to {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Retinotopy condition analysis")
    parser.add_argument("--subject", default=None)
    args = parser.parse_args()

    subjects = [args.subject] if args.subject else ALL_SUBJECTS
    for sub in subjects:
        try:
            process_subject(sub)
        except Exception as e:
            print(f"    ERROR sub-{sub}: {e}")

    print("\nDone — condition analysis complete.")


if __name__ == "__main__":
    main()
