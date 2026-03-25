"""
Group-level statistics across subjects.

Aggregates per-subject band power, retinotopy, and orientation summaries
into group-level means, SEMs, and consistency metrics.

This replaces: Custom_pipeline_Dataset/Scripts/grand_average_analysis.py,
               Custom_pipeline_Dataset/Scripts/group_statistical_analysis.py,
               Custom_pipeline_Dataset/Scripts/group_ersp_statistics.py

Usage:
    python group_statistics.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import (
    ALL_SUBJECTS,
    get_custom_output_dir,
    get_group_output_dir,
    load_json,
    save_json,
)


def collect_retinotopy_summaries():
    """Collect per-subject retinotopy summaries."""
    records = []
    for sub in ALL_SUBJECTS:
        path = get_custom_output_dir(sub) / "retinotopy_summary.json"
        if path.exists():
            records.append(load_json(path))
    return records


def collect_orientation_summaries():
    """Collect per-subject orientation summaries."""
    records = []
    for sub in ALL_SUBJECTS:
        path = get_custom_output_dir(sub) / "orientation_summary.json"
        if path.exists():
            records.append(load_json(path))
    return records


def aggregate_retinotopy(records):
    """Compute group-level retinotopy statistics."""
    if not records:
        return {}

    # Gather values per condition label
    label_alpha = {}
    label_gamma = {}
    for rec in records:
        for grp in rec.get("groups", []):
            lbl = grp["label"]
            label_alpha.setdefault(lbl, []).append(grp["alpha_mean"])
            label_gamma.setdefault(lbl, []).append(grp["gamma_mean"])

    result = {}
    for lbl in label_alpha:
        a_vals = np.array(label_alpha[lbl])
        g_vals = np.array(label_gamma.get(lbl, []))
        result[lbl] = {
            "alpha_mean": float(np.mean(a_vals)),
            "alpha_sem": float(np.std(a_vals, ddof=1) / np.sqrt(len(a_vals))),
            "alpha_std": float(np.std(a_vals, ddof=1)),
            "gamma_mean": float(np.mean(g_vals)) if len(g_vals) > 0 else None,
            "gamma_sem": float(np.std(g_vals, ddof=1) / np.sqrt(len(g_vals))) if len(g_vals) > 0 else None,
            "gamma_std": float(np.std(g_vals, ddof=1)) if len(g_vals) > 0 else None,
            "n_subjects": len(a_vals),
        }
    return result


def aggregate_orientation(records):
    """Compute group-level orientation statistics."""
    if not records:
        return {}

    # Aggregate tuning correlations
    orient_corrs = []
    direction_corrs = []
    for rec in records:
        corrs = rec.get("correlations", {})
        if corrs.get("orientation") is not None:
            orient_corrs.append(corrs["orientation"])
        if corrs.get("direction") is not None:
            direction_corrs.append(corrs["direction"])

    # Aggregate per-trigger means
    trigger_alpha = {}
    trigger_gamma = {}
    for rec in records:
        for row in rec.get("trigger_rows", []):
            code = row["code"]
            trigger_alpha.setdefault(code, []).append(row["alpha"])
            trigger_gamma.setdefault(code, []).append(row["gamma"])

    trigger_summary = {}
    for code in sorted(trigger_alpha.keys()):
        a = np.array(trigger_alpha[code])
        g = np.array(trigger_gamma.get(code, []))
        trigger_summary[str(code)] = {
            "alpha_mean": float(np.mean(a)),
            "alpha_sem": float(np.std(a, ddof=1) / np.sqrt(len(a))),
            "gamma_mean": float(np.mean(g)) if len(g) > 0 else None,
            "gamma_sem": float(np.std(g, ddof=1) / np.sqrt(len(g))) if len(g) > 0 else None,
            "n": len(a),
        }

    # Tuning indices
    all_alpha = [v for vals in trigger_alpha.values() for v in vals]
    all_gamma = [v for vals in trigger_gamma.values() for v in vals]

    alpha_range = float(np.ptp(all_alpha)) if all_alpha else 0
    gamma_range = float(np.ptp(all_gamma)) if all_gamma else 0
    alpha_mean_abs = float(np.mean(np.abs(all_alpha))) if all_alpha else 1e-12
    gamma_mean_abs = float(np.mean(np.abs(all_gamma))) if all_gamma else 1e-12

    return {
        "orientation_correlation": {
            "mean": float(np.mean(orient_corrs)) if orient_corrs else None,
            "std": float(np.std(orient_corrs)) if orient_corrs else None,
            "n": len(orient_corrs),
        },
        "direction_correlation": {
            "mean": float(np.mean(direction_corrs)) if direction_corrs else None,
            "std": float(np.std(direction_corrs)) if direction_corrs else None,
            "n": len(direction_corrs),
        },
        "trigger_summary": trigger_summary,
        "tuning_indices": {
            "alpha_tuning_index": alpha_range / alpha_mean_abs if alpha_mean_abs > 0 else 0,
            "gamma_tuning_index": gamma_range / gamma_mean_abs if gamma_mean_abs > 0 else 0,
        },
    }


def compute_consistency_metrics(records_retino):
    """Cross-subject consistency (CV for alpha and gamma effects)."""
    all_alpha = []
    all_gamma = []
    for rec in records_retino:
        for grp in rec.get("groups", []):
            if grp["label"] == "full":
                all_alpha.append(grp["alpha_mean"])
                all_gamma.append(grp["gamma_mean"])

    if not all_alpha:
        return {}

    a = np.array(all_alpha)
    g = np.array(all_gamma)
    return {
        "alpha_effect": {
            "mean": float(np.mean(a)),
            "std": float(np.std(a, ddof=1)),
            "cv": float(np.std(a, ddof=1) / np.mean(a)) if np.mean(a) != 0 else None,
            "n": len(a),
        },
        "gamma_effect": {
            "mean": float(np.mean(g)),
            "std": float(np.std(g, ddof=1)),
            "cv": float(np.std(g, ddof=1) / np.mean(g)) if np.mean(g) != 0 else None,
            "n": len(g),
        },
    }


def main():
    print("=" * 60)
    print("  Group-Level Statistical Analysis")
    print("=" * 60)

    group_dir = get_group_output_dir()

    # Retinotopy
    retino_records = collect_retinotopy_summaries()
    retino_stats = aggregate_retinotopy(retino_records)
    save_json(group_dir / "group_retinotopy_statistics.json", {
        "n_subjects": len(retino_records),
        "conditions": retino_stats,
    })
    print(f"\n  Retinotopy: {len(retino_records)} subjects")

    # Orientation
    orient_records = collect_orientation_summaries()
    orient_stats = aggregate_orientation(orient_records)
    save_json(group_dir / "group_orientation_statistics.json", {
        "n_subjects": len(orient_records),
        **orient_stats,
    })
    print(f"  Orientation: {len(orient_records)} subjects")

    # Consistency
    consistency = compute_consistency_metrics(retino_records)
    save_json(group_dir / "group_consistency_metrics.json", consistency)
    if consistency:
        a_cv = consistency["alpha_effect"].get("cv")
        g_cv = consistency["gamma_effect"].get("cv")
        print(f"  Alpha CV: {a_cv:.2f}" if a_cv else "  Alpha CV: N/A")
        print(f"  Gamma CV: {g_cv:.2f}" if g_cv else "  Gamma CV: N/A")

    # Manifest
    save_json(group_dir / "phase2_manifest.json", {
        "n_retinotopy_subjects": len(retino_records),
        "n_orientation_subjects": len(orient_records),
        "outputs": [
            "group_retinotopy_statistics.json",
            "group_orientation_statistics.json",
            "group_consistency_metrics.json",
            "retinotopy_model_fit_summary.json",
        ],
    })

    print(f"\n  All group-level outputs saved to {group_dir}")
    print("Done.")


if __name__ == "__main__":
    main()
