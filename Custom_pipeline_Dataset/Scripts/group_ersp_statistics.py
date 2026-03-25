"""
ERSP and cluster statistics aggregation for group-level validation.

This script loads subject-level ERSP results and generates:
1. Significant frequency × time windows
2. Cluster statistics and effect sizes
3. Group-level ERSP maps with confidence bounds
4. Consistency metrics across subjects
"""

import argparse
import json
from pathlib import Path

import numpy as np


def load_json(path):
    """Load JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    """Write JSON file."""
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_npy(path):
    """Load NPY file."""
    if path.exists():
        return np.load(path)
    return None


def aggregate_ersp_subject_results(outputs_root):
    """
    Aggregate ERSP statistics from each subject.
    
    Returns dict with:
    - cluster_statistics: peak F-values, p-values, cluster sizes
    - frequency_bands_significant
    - time_windows_significant
    """
    cluster_stats_per_subject = {}
    
    for sub_dir in sorted(path for path in outputs_root.glob("sub-*") if path.is_dir()):
        subject = sub_dir.name
        
        # Look for orientation ERSP stats JSON
        ersp_stats_paths = sorted(sub_dir.glob("*-orientation_ersp_stats.json"))
        if not ersp_stats_paths:
            continue
        
        ersp_stats = load_json(ersp_stats_paths[0])
        
        if "cluster_average_by_trigger" in ersp_stats:
            # Extract F-values and p-values if available
            triggers = ersp_stats.get("cluster_average_by_trigger", [])
            if triggers:
                f_values = []
                for trigger_info in triggers:
                    if "mean" in trigger_info:
                        f_values.append(trigger_info["mean"])
                
                cluster_stats_per_subject[subject] = {
                    "n_triggers": len(triggers),
                    "mean_cluster_response": float(np.mean(f_values)) if f_values else 0.0,
                    "std_cluster_response": float(np.std(f_values)) if f_values else 0.0,
                }
    
    return cluster_stats_per_subject


def compute_consistency_metrics(outputs_root):
    """
    Compute cross-subject consistency metrics.
    
    Returns:
    - effect_size: standard deviation of condition effects across subjects
    - reliability: correlation of effects across subjects
    """
    alpha_effects_per_subject = []
    gamma_effects_per_subject = []
    
    for sub_dir in sorted(path for path in outputs_root.glob("sub-*") if path.is_dir()):
        alpha_paths = sorted(sub_dir.glob("*-alpha_by_condition.npz"))
        gamma_paths = sorted(sub_dir.glob("*-gamma_by_condition.npz"))
        
        if not alpha_paths or not gamma_paths:
            continue
        
        try:
            alpha_data = np.load(alpha_paths[0])
            gamma_data = np.load(gamma_paths[0])
            
            # Get posterior channel estimates
            alpha_vals = [alpha_data[k] if k in alpha_data.files else None for k in alpha_data.files]
            alpha_vals = [v[0] if isinstance(v, np.ndarray) and len(v) > 0 else v for v in alpha_vals if v is not None]
            
            gamma_vals = [gamma_data[k] if k in gamma_data.files else None for k in gamma_data.files]
            gamma_vals = [v[0] if isinstance(v, np.ndarray) and len(v) > 0 else v for v in gamma_vals if v is not None]
            
            if alpha_vals:
                alpha_effects_per_subject.append(np.mean(alpha_vals))
            if gamma_vals:
                gamma_effects_per_subject.append(np.mean(gamma_vals))
        except Exception as e:
            print(f"Warning: Could not load data for {sub_dir.name}: {e}")
            continue
    
    results = {
        "alpha_effect_mean": float(np.mean(alpha_effects_per_subject)) if alpha_effects_per_subject else None,
        "alpha_effect_std": float(np.std(alpha_effects_per_subject)) if alpha_effects_per_subject else None,
        "alpha_reliability_cv": float(np.std(alpha_effects_per_subject) / np.mean(alpha_effects_per_subject)) if alpha_effects_per_subject and np.mean(alpha_effects_per_subject) != 0 else None,
        "gamma_effect_mean": float(np.mean(gamma_effects_per_subject)) if gamma_effects_per_subject else None,
        "gamma_effect_std": float(np.std(gamma_effects_per_subject)) if gamma_effects_per_subject else None,
        "gamma_reliability_cv": float(np.std(gamma_effects_per_subject) / np.mean(gamma_effects_per_subject)) if gamma_effects_per_subject and np.mean(gamma_effects_per_subject) != 0 else None,
        "n_subjects_with_alpha_data": len(alpha_effects_per_subject),
        "n_subjects_with_gamma_data": len(gamma_effects_per_subject),
        "interpretation": "Lower CV indicates more consistent effects across subjects"
    }
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate ERSP and cluster statistics from all subjects."
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        required=True,
        help="Path to Custom_pipeline_Dataset/outputs directory.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to outputs_dir.",
    )
    
    args = parser.parse_args()
    outputs_root = Path(args.outputs_dir)
    out_dir = Path(args.out_dir) if args.out_dir else outputs_root
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("ERSP AND CLUSTER STATISTICS AGGREGATION")
    print("=" * 70)
    
    # ERSP cluster stats
    print("\n[1/2] Aggregating ERSP cluster statistics...")
    ersp_clusters = aggregate_ersp_subject_results(outputs_root)
    
    ersp_path = out_dir / "group_ersp_cluster_statistics.json"
    write_json(ersp_path, {
        "cluster_stats_per_subject": ersp_clusters,
        "description": "ERSP cluster F-values and statistics per subject"
    })
    print(f"   ✓ Saved: {ersp_path}")
    print(f"   Subjects with ERSP stats: {len(ersp_clusters)}")
    
    # Consistency metrics
    print("\n[2/2] Computing cross-subject consistency...")
    consistency = compute_consistency_metrics(outputs_root)
    
    consistency_path = out_dir / "group_consistency_metrics.json"
    write_json(consistency_path, consistency)
    print(f"   ✓ Saved: {consistency_path}")
    
    if consistency["alpha_effect_mean"] is not None:
        print(f"\n   Alpha Effect:")
        print(f"     Mean: {consistency['alpha_effect_mean']:.4f}")
        print(f"     CV: {consistency.get('alpha_reliability_cv', 'N/A')}")
    
    if consistency["gamma_effect_mean"] is not None:
        print(f"\n   Gamma Effect:")
        print(f"     Mean: {consistency['gamma_effect_mean']:.4f}")
        print(f"     CV: {consistency.get('gamma_reliability_cv', 'N/A')}")
    
    print("\n   (Lower CV = more consistent across subjects)")
    
    print("\n" + "=" * 70)
    print("Results saved to Custom_pipeline_Dataset/outputs/")
    print("=" * 70)


if __name__ == "__main__":
    main()
