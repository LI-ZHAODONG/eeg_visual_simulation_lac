"""
Group-level orientation and direction analysis across all subjects.

Aggregates per-subject orientation_summary.json data and produces:
1. Group orientation bar summary (alpha + gamma by orientation group)
2. Group direction bar summary (alpha + gamma by direction group)
3. Group alpha-gamma scatter (orientation + direction)
4. Group frequency correlation matrix
5. Group alpha-gamma regression + residuals (per trigger, N=16 orientations)
6. Group pairwise t-test heatmaps (orientation + direction, alpha + gamma)

Usage:
    python group_orientation_direction_analysis.py --outputs-root Custom_pipeline_Dataset/outputs
"""

import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import pearsonr, ttest_rel, linregress

matplotlib.use("Agg")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def collect_subject_summaries(outputs_root):
    """Load orientation_summary.json from all subjects."""
    records = []
    sub_dirs = sorted(outputs_root.glob("sub-[0-9][0-9]"))
    for sub_dir in sub_dirs:
        path = sub_dir / "orientation_summary.json"
        if path.exists():
            data = load_json(path)
            data["_subject"] = sub_dir.name
            records.append(data)
    return records


# ---------------------------------------------------------------------------
# 1 & 2. Group orientation / direction bar summaries
# ---------------------------------------------------------------------------

def collect_group_values(records, key):
    """Collect per-subject values for orientation_groups or direction_groups.

    Returns dict: label -> {"alpha": [n_subjects], "gamma": [n_subjects]}
    """
    result = {}
    for rec in records:
        for row in rec.get(key, []):
            label = row["label"]
            if label not in result:
                result[label] = {"alpha": [], "gamma": []}
            result[label]["alpha"].append(row["alpha"])
            result[label]["gamma"].append(row["gamma"])
    return result


def plot_group_bar_summary(group_vals, out_path, title, short_labels=None):
    """Bar chart: group mean +/- SEM for alpha and gamma."""
    labels = list(group_vals.keys())
    if short_labels is None:
        short_labels = [l.replace("orientation_", "").replace("direction_", "")
                        .replace("_combined", "").replace("_", " ") for l in labels]

    n = len(labels)
    alpha_means = [np.mean(group_vals[l]["alpha"]) for l in labels]
    alpha_sems = [np.std(group_vals[l]["alpha"], ddof=1) / np.sqrt(len(group_vals[l]["alpha"])) for l in labels]
    gamma_means = [np.mean(group_vals[l]["gamma"]) for l in labels]
    gamma_sems = [np.std(group_vals[l]["gamma"], ddof=1) / np.sqrt(len(group_vals[l]["gamma"])) for l in labels]

    x = np.arange(n)
    w = 0.35
    fig, ax = plt.subplots(figsize=(max(10, n * 1.2), 5))
    ax.bar(x - w / 2, alpha_means, w, yerr=alpha_sems, label="Alpha (8-13 Hz)",
           color="#4472C4", capsize=3, edgecolor="black", linewidth=0.5)
    ax.bar(x + w / 2, gamma_means, w, yerr=gamma_sems, label="Gamma (40-80 Hz)",
           color="#ED7D31", capsize=3, edgecolor="black", linewidth=0.5)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(short_labels, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Log Power Change (log(task/baseline))")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# 3. Group alpha-gamma scatter (orientation + direction)
# ---------------------------------------------------------------------------

def plot_group_scatter(group_vals, out_path, title):
    """Scatter plot of group-mean alpha vs gamma per group."""
    labels = list(group_vals.keys())
    alpha_means = [np.mean(group_vals[l]["alpha"]) for l in labels]
    gamma_means = [np.mean(group_vals[l]["gamma"]) for l in labels]
    short = [l.replace("orientation_", "").replace("direction_", "")
             .replace("_combined", "").replace("_", " ") for l in labels]

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.scatter(alpha_means, gamma_means, s=80, zorder=3, edgecolor="black")
    for i, txt in enumerate(short):
        ax.annotate(txt, (alpha_means[i], gamma_means[i]),
                    fontsize=7, ha="left", va="bottom", xytext=(4, 4),
                    textcoords="offset points")

    if len(alpha_means) >= 2:
        slope, intercept, r, p, _ = linregress(alpha_means, gamma_means)
        xline = np.linspace(min(alpha_means), max(alpha_means), 50)
        ax.plot(xline, slope * xline + intercept, "r--", linewidth=1,
                label=f"r={r:.3f}, p={p:.3f}")
        ax.legend(fontsize=9)

    ax.axhline(0, color="grey", linewidth=0.5, linestyle=":")
    ax.axvline(0, color="grey", linewidth=0.5, linestyle=":")
    ax.set_xlabel("Alpha Log Power Change")
    ax.set_ylabel("Gamma Log Power Change")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# 4. Group frequency correlation
# ---------------------------------------------------------------------------

def plot_group_frequency_correlation(records, out_path):
    """Average the per-subject alpha-gamma correlations and show a summary."""
    orient_corrs = [r["correlations"]["orientation"] for r in records
                    if "correlations" in r and r["correlations"].get("orientation") is not None]
    direct_corrs = [r["correlations"]["direction"] for r in records
                    if "correlations" in r and r["correlations"].get("direction") is not None]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    for ax, vals, label in zip(axes, [orient_corrs, direct_corrs],
                                ["Orientation", "Direction"]):
        vals = np.array(vals)
        ax.hist(vals, bins=15, edgecolor="black", alpha=0.7, color="#4472C4")
        mean_r = np.mean(vals)
        ax.axvline(mean_r, color="red", linewidth=2, linestyle="--",
                   label=f"Mean r = {mean_r:.3f}")
        ax.set_xlabel("Pearson r (Alpha vs Gamma)")
        ax.set_ylabel("Count (subjects)")
        ax.set_title(f"{label}: Alpha-Gamma Correlation (N={len(vals)})")
        ax.legend()

    fig.suptitle("Group Frequency Correlation: Alpha vs Gamma", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out_path}")

    return {
        "orientation_r_mean": float(np.mean(orient_corrs)),
        "orientation_r_std": float(np.std(orient_corrs)),
        "direction_r_mean": float(np.mean(direct_corrs)),
        "direction_r_std": float(np.std(direct_corrs)),
        "n_subjects": len(orient_corrs),
    }


# ---------------------------------------------------------------------------
# 5. Group alpha-gamma regression + residuals (per trigger)
# ---------------------------------------------------------------------------

def plot_group_regression_residuals(records, out_path):
    """Regression of group-mean gamma on alpha across 16 triggers + residuals."""
    # Collect per-trigger means across subjects
    trigger_alpha = {}
    trigger_gamma = {}
    for rec in records:
        for row in rec.get("trigger_rows", []):
            code = row["code"]
            if code not in trigger_alpha:
                trigger_alpha[code] = []
                trigger_gamma[code] = []
            trigger_alpha[code].append(row["alpha"])
            trigger_gamma[code].append(row["gamma"])

    codes = sorted(trigger_alpha.keys())
    alpha_means = np.array([np.mean(trigger_alpha[c]) for c in codes])
    gamma_means = np.array([np.mean(trigger_gamma[c]) for c in codes])
    alpha_sems = np.array([np.std(trigger_alpha[c], ddof=1) / np.sqrt(len(trigger_alpha[c])) for c in codes])
    gamma_sems = np.array([np.std(trigger_gamma[c], ddof=1) / np.sqrt(len(trigger_gamma[c])) for c in codes])

    slope, intercept, r, p, _ = linregress(alpha_means, gamma_means)
    predicted = slope * alpha_means + intercept
    residuals = gamma_means - predicted

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: regression
    ax = axes[0]
    ax.errorbar(alpha_means, gamma_means, xerr=alpha_sems, yerr=gamma_sems,
                fmt="o", capsize=3, color="#4472C4", markersize=6, zorder=3)
    xline = np.linspace(alpha_means.min() - 0.05, alpha_means.max() + 0.05, 50)
    ax.plot(xline, slope * xline + intercept, "r-", linewidth=1.5,
            label=f"y = {slope:.3f}x + {intercept:.3f}\nr = {r:.3f}, p = {p:.4f}")
    for i, c in enumerate(codes):
        ax.annotate(str(c), (alpha_means[i], gamma_means[i]),
                    fontsize=6, ha="left", va="bottom", xytext=(3, 3),
                    textcoords="offset points")
    ax.axhline(0, color="grey", linewidth=0.5, linestyle=":")
    ax.axvline(0, color="grey", linewidth=0.5, linestyle=":")
    ax.set_xlabel("Group Mean Alpha Log Power Change")
    ax.set_ylabel("Group Mean Gamma Log Power Change")
    ax.set_title(f"Alpha-Gamma Regression (N={len(records)} subjects, 16 triggers)")
    ax.legend(fontsize=9)

    # Right: residuals
    ax = axes[1]
    degs = [(c - 41) * 22.5 for c in codes]
    ax.bar(range(len(codes)), residuals, color=["#ED7D31" if r > 0 else "#4472C4" for r in residuals],
           edgecolor="black", linewidth=0.5)
    ax.set_xticks(range(len(codes)))
    ax.set_xticklabels([f"{d:.0f}°" for d in degs], rotation=45, fontsize=7)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Grating Orientation (°)")
    ax.set_ylabel("Residual (Gamma - predicted)")
    ax.set_title("Regression Residuals by Orientation")

    fig.suptitle("Group-Level Alpha-Gamma Anti-Proportionality", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out_path}")

    return {
        "slope": float(slope), "intercept": float(intercept),
        "r": float(r), "p": float(p),
        "n_triggers": len(codes), "n_subjects": len(records),
    }


# ---------------------------------------------------------------------------
# 6. Group pairwise t-test heatmaps
# ---------------------------------------------------------------------------

def group_pairwise_ttests(records, group_key):
    """Paired t-tests across subjects for each pair of groups.

    For each group label, collect per-subject values (alpha and gamma).
    Then do paired t-tests between all pairs.
    """
    group_vals = collect_group_values(records, group_key)
    labels = list(group_vals.keys())
    n = len(labels)
    n_sub = min(len(group_vals[l]["alpha"]) for l in labels)

    results = {}
    for band in ["alpha", "gamma"]:
        t_mat = np.zeros((n, n))
        p_mat = np.ones((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                vals_i = np.array(group_vals[labels[i]][band])[:n_sub]
                vals_j = np.array(group_vals[labels[j]][band])[:n_sub]
                t, p = ttest_rel(vals_i, vals_j)
                t_mat[i, j] = t
                t_mat[j, i] = -t
                p_mat[i, j] = p
                p_mat[j, i] = p
        results[band] = {"t": t_mat, "p": p_mat}

    return labels, results, n_sub


def plot_ttest_heatmap(t_values, p_values, labels, out_path, title):
    """Plot lower-triangle t-value heatmap with p-value annotations."""
    short = [l.replace("orientation_", "").replace("direction_", "")
             .replace("_combined", "").replace("_", " ") for l in labels]
    n = len(labels)
    # Mask: show only lower triangle (i > j); upper triangle and diagonal are white
    mask = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(i):
            mask[i, j] = t_values[i, j]

    fig, ax = plt.subplots(figsize=(max(6, n * 0.9), max(5, n * 0.8)))
    vmax = max(np.nanmax(np.abs(mask)), 1)
    im = ax.imshow(mask, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                   aspect="equal")

    for i in range(n):
        for j in range(i):
            p = p_values[i, j]
            txt = f"{p:.3f}"
            if p < 0.05:
                txt += "*"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    fontweight="bold" if p < 0.05 else "normal")

    ax.set_xticks(range(n))
    ax.set_xticklabels(short, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(n))
    ax.set_yticklabels(short, fontsize=8)
    ax.set_title(title)
    plt.colorbar(im, ax=ax, label="t-value", shrink=0.8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Group-level orientation and direction analysis."
    )
    parser.add_argument(
        "--outputs-root", type=Path, required=True,
        help="Root outputs directory containing sub-* folders."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Output directory. Defaults to outputs-root/group_level."
    )
    args = parser.parse_args()

    outputs_root = args.outputs_root.resolve()
    out_dir = (args.out_dir or outputs_root / "group_level").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    records = collect_subject_summaries(outputs_root)
    print(f"Loaded orientation summaries from {len(records)} subjects.")

    if len(records) < 3:
        raise RuntimeError("Need at least 3 subjects for group analysis.")

    # 1. Group orientation bar summary
    orient_vals = collect_group_values(records, "orientation_groups")
    if orient_vals:
        plot_group_bar_summary(
            orient_vals,
            out_dir / "group_orientation_summary.png",
            f"Group Orientation Summary (N={len(records)})",
        )

    # 2. Group direction bar summary
    direct_vals = collect_group_values(records, "direction_groups")
    if direct_vals:
        plot_group_bar_summary(
            direct_vals,
            out_dir / "group_direction_summary.png",
            f"Group Direction Summary (N={len(records)})",
        )

    # 3. Group alpha-gamma scatter (orientation + direction)
    if orient_vals:
        plot_group_scatter(
            orient_vals,
            out_dir / "group_orientation_alpha_gamma_scatter.png",
            f"Group Orientation: Alpha vs Gamma (N={len(records)})",
        )
    if direct_vals:
        plot_group_scatter(
            direct_vals,
            out_dir / "group_direction_alpha_gamma_scatter.png",
            f"Group Direction: Alpha vs Gamma (N={len(records)})",
        )

    # 4. Group frequency correlation
    corr_stats = plot_group_frequency_correlation(
        records, out_dir / "group_frequency_correlation.png"
    )

    # 5. Group regression + residuals
    regr_stats = plot_group_regression_residuals(
        records, out_dir / "group_alpha_gamma_regression.png"
    )

    # 6. Group pairwise t-tests
    ttest_stats = {}
    for group_key, prefix in [("orientation_groups", "orientation"),
                               ("direction_groups", "direction")]:
        labels, results, n_sub = group_pairwise_ttests(records, group_key)
        for band in ["alpha", "gamma"]:
            fname = f"group_{prefix}_{band}_ttests.png"
            plot_ttest_heatmap(
                results[band]["t"], results[band]["p"], labels,
                out_dir / fname,
                f"Group {band.title()} T-values ({prefix.title()}, N={n_sub})",
            )
            sig_pairs = []
            n = len(labels)
            for i in range(n):
                for j in range(i + 1, n):
                    if results[band]["p"][i, j] < 0.05:
                        sig_pairs.append({
                            "pair": [labels[i], labels[j]],
                            "t": float(results[band]["t"][i, j]),
                            "p": float(results[band]["p"][i, j]),
                        })
            ttest_stats[f"{prefix}_{band}"] = {
                "n_subjects": n_sub,
                "n_pairs": n * (n - 1) // 2,
                "significant_pairs": sig_pairs,
            }

    # Save summary JSON
    summary = {
        "n_subjects": len(records),
        "subjects": [r["_subject"] for r in records],
        "frequency_correlation": corr_stats,
        "regression": regr_stats,
        "pairwise_ttests": ttest_stats,
    }
    save_json(out_dir / "group_orientation_direction_summary.json", summary)
    print(f"\nDone. All group-level orientation/direction plots saved to {out_dir}")


if __name__ == "__main__":
    main()
