"""
Orientation tuning analysis.

Builds orientation-selective response summaries, direction selectivity,
alpha-vs-gamma scatter plots, and pairwise t-test heatmaps.

This replaces: Custom_pipeline_Dataset/Scripts/orientation_tuning_analysis.py

Usage:
    python orientation_tuning.py              # all subjects
    python orientation_tuning.py --subject 01  # one subject
"""

import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import ttest_ind

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (
    ALL_SUBJECTS,
    TRIGGER_CODE_TO_NAME,
    choose_channel,
    get_custom_output_dir,
    load_condition_mapping,
    load_json,
    save_json,
)


def load_npz_dict(path):
    data = np.load(path)
    return {k: data[k] for k in data.files}


def code_mean(code_map, code):
    name = TRIGGER_CODE_TO_NAME.get(code, str(code))
    return code_map.get(name, code_map.get(str(code)))


def grouped_mean(code_map, codes, pick_idx):
    keys = []
    for c in codes:
        name = TRIGGER_CODE_TO_NAME.get(c, str(c))
        if name in code_map:
            keys.append(name)
        elif str(c) in code_map:
            keys.append(str(c))
    if not keys:
        return None
    stacked = np.stack([code_map[k] for k in keys], axis=0)
    return float(stacked.mean(axis=0)[pick_idx])


def grouped_trial_values(trial_matrix, event_names, codes, pick_idx):
    names = [TRIGGER_CODE_TO_NAME.get(c, str(c)) for c in codes]
    mask = np.isin(event_names, names)
    if not mask.any():
        return np.array([])
    return trial_matrix[mask, pick_idx]


def plot_trigger_bars(trigger_rows, out_path):
    labels = [str(r["code"]) for r in trigger_rows]
    gamma = [r["gamma"] for r in trigger_rows]
    alpha = [r["alpha"] for r in trigger_rows]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].bar(labels, gamma, color="#e76f51")
    axes[0].set_title("Gamma Power by Orientation Trigger")
    axes[0].set_ylabel("Mean Power")
    axes[0].tick_params(axis="x", rotation=45)
    axes[1].bar(labels, alpha, color="#8ecae6")
    axes[1].set_title("Alpha Power by Orientation Trigger")
    axes[1].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_group_bars(group_rows, out_path, title):
    labels = [r["label"] for r in group_rows]
    gamma = [r["gamma"] for r in group_rows]
    alpha = [r["alpha"] for r in group_rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(labels, gamma, color="#e76f51")
    axes[0].set_title(f"Gamma: {title}")
    axes[0].tick_params(axis="x", rotation=35)
    axes[1].bar(labels, alpha, color="#8ecae6")
    axes[1].set_title(f"Alpha: {title}")
    axes[1].tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_orientation_scatter(group_rows, out_path, title):
    alpha = np.array([r["alpha"] for r in group_rows], dtype=float)
    gamma = np.array([r["gamma"] for r in group_rows], dtype=float)
    labels = [r["label"] for r in group_rows]

    slope, intercept = np.polyfit(alpha, gamma, 1)
    corr = float(np.corrcoef(alpha, gamma)[0, 1])

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(alpha, gamma, color="#444444")
    ax.plot(np.sort(alpha), slope * np.sort(alpha) + intercept, "--", color="#1d3557")
    for x, y, lbl in zip(alpha, gamma, labels):
        ax.text(x, y, lbl, fontsize=8)
    ax.set_title(f"{title} (r = {corr:.2f})")
    ax.set_xlabel("Alpha Power")
    ax.set_ylabel("Gamma Power")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return corr


def compute_pairwise_ttests(group_rows, trial_matrix, event_codes, pick_idx):
    n = len(group_rows)
    t_values = np.full((n, n), np.nan)
    p_values = np.full((n, n), np.nan)

    for i, row_i in enumerate(group_rows):
        vals_i = grouped_trial_values(trial_matrix, event_codes, row_i["codes"], pick_idx)
        for j, row_j in enumerate(group_rows):
            if j >= i:
                continue
            vals_j = grouped_trial_values(trial_matrix, event_codes, row_j["codes"], pick_idx)
            if len(vals_i) < 2 or len(vals_j) < 2:
                continue
            stat = ttest_ind(vals_i, vals_j, equal_var=False, nan_policy="omit")
            t_values[i, j] = stat.statistic
            p_values[i, j] = stat.pvalue

    return t_values, p_values


def plot_pairwise_heatmap(t_values, p_values, labels, out_path, title):
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(np.nan_to_num(t_values, nan=0.0), cmap="coolwarm", vmin=-5, vmax=5)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)
    ax.set_title(title)

    for i in range(len(labels)):
        for j in range(len(labels)):
            if np.isnan(p_values[i, j]):
                continue
            text = f"{p_values[i, j]:.3f}"
            if p_values[i, j] < 0.05:
                text += "*"
            ax.text(j, i, text, ha="center", va="center", fontsize=8, color="black")

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="t-value")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def process_subject(subject):
    """Build orientation summaries for one subject."""
    print(f"\n  Orientation tuning analysis for sub-{subject}")

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
    bp_summary = load_json(summary_path)
    ch_names = bp_summary["ch_names"]
    pick_ch = choose_channel(ch_names)
    pick_idx = ch_names.index(pick_ch)

    # Per-trigger summaries
    trigger_rows = []
    for code in mapping["families"]["orientation"]["codes"]:
        alpha_vec = code_mean(alpha_map, code)
        gamma_vec = code_mean(gamma_map, code)
        if alpha_vec is None or gamma_vec is None:
            continue
        trigger_rows.append({
            "code": code,
            "deg": mapping["orientation_code_degrees"][str(code)],
            "alpha": float(alpha_vec[pick_idx]),
            "gamma": float(gamma_vec[pick_idx]),
        })

    # Orientation groups
    orientation_group_names = [
        "orientation_cardinal_combined",
        "orientation_oblique_perfect_45",
        "orientation_oblique_vertical_pm_22_5",
        "orientation_oblique_horizontal_pm_22_5",
        "orientation_horizontal",
        "orientation_vertical",
    ]
    direction_group_names = [
        "leftward_motion", "rightward_motion",
        "upward_motion", "downward_motion",
    ]

    orientation_groups = []
    for name in orientation_group_names:
        codes = mapping["orientation_groups"][name]
        orientation_groups.append({
            "label": name,
            "codes": codes,
            "alpha": grouped_mean(alpha_map, codes, pick_idx),
            "gamma": grouped_mean(gamma_map, codes, pick_idx),
        })

    direction_groups = []
    for name in direction_group_names:
        codes = mapping["orientation_groups"][name]
        direction_groups.append({
            "label": name.replace("_motion", ""),
            "codes": codes,
            "alpha": grouped_mean(alpha_map, codes, pick_idx),
            "gamma": grouped_mean(gamma_map, codes, pick_idx),
        })

    # Plots
    plot_trigger_bars(trigger_rows, out_dir / "orientation_trigger_summary.png")
    plot_group_bars(orientation_groups, out_dir / "orientation_group_summary.png", "Orientation Bins")
    plot_group_bars(direction_groups, out_dir / "direction_group_summary.png", "Direction Bins")
    orientation_corr = plot_orientation_scatter(
        orientation_groups, out_dir / "orientation_alpha_gamma_scatter.png",
        "Alpha vs Gamma: Orientation",
    )
    direction_corr = plot_orientation_scatter(
        direction_groups, out_dir / "direction_alpha_gamma_scatter.png",
        "Alpha vs Gamma: Direction",
    )

    # Pairwise t-tests (if trial-level data available)
    ttest_outputs = {}
    alpha_trial_path = out_dir / f"{prefix}-alpha_trial_diff.npy"
    gamma_trial_path = out_dir / f"{prefix}-gamma_trial_diff.npy"
    event_names_path = out_dir / f"{prefix}-event_names.npy"

    if all(p.exists() for p in [alpha_trial_path, gamma_trial_path, event_names_path]):
        alpha_trial = np.load(alpha_trial_path)
        gamma_trial = np.load(gamma_trial_path)
        event_names = np.load(event_names_path, allow_pickle=True)

        for groups, name_prefix in [
            (orientation_groups, "orientation"),
            (direction_groups, "direction"),
        ]:
            labels = [r["label"] for r in groups]
            for band, trial_data, band_name in [
                ("alpha", alpha_trial, "Alpha"),
                ("gamma", gamma_trial, "Gamma"),
            ]:
                t_vals, p_vals = compute_pairwise_ttests(groups, trial_data, event_names, pick_idx)
                fig_path = out_dir / f"{name_prefix}_{band}_ttests.png"
                plot_pairwise_heatmap(t_vals, p_vals, labels, fig_path,
                                      f"{band_name} T-values ({name_prefix.title()})")
                ttest_outputs[f"{name_prefix}_{band}_ttests"] = str(fig_path)

    payload = {
        "subject": f"sub-{subject}",
        "picked_channel": pick_ch,
        "trigger_rows": trigger_rows,
        "orientation_groups": orientation_groups,
        "direction_groups": direction_groups,
        "correlations": {
            "orientation": orientation_corr,
            "direction": direction_corr,
        },
    }
    save_json(out_dir / "orientation_summary.json", payload)
    print(f"    Saved orientation summaries to {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Orientation tuning analysis")
    parser.add_argument("--subject", default=None)
    args = parser.parse_args()

    subjects = [args.subject] if args.subject else ALL_SUBJECTS
    for sub in subjects:
        try:
            process_subject(sub)
        except Exception as e:
            print(f"    ERROR sub-{sub}: {e}")

    print("\nDone — orientation tuning analysis complete.")


if __name__ == "__main__":
    main()
