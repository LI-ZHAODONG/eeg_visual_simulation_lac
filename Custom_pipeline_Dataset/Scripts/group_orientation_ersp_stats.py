import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter, label
from scipy.stats import f_oneway

matplotlib.use("Agg")

ORIENTATION_CODES = list(range(41, 57))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def smooth_map(data, sigma_freq=2.0, sigma_time=4.0):
    return gaussian_filter(data, sigma=(sigma_freq, sigma_time))


def cluster_mask_from_pvalues(p_map, threshold=0.01):
    sig = np.isfinite(p_map) & (p_map < threshold)
    structure = np.ones((3, 3), dtype=int)
    labeled, n_clusters = label(sig, structure=structure)
    return sig, labeled, int(n_clusters)


def main():
    parser = argparse.ArgumentParser(
        description="Group-level ANOVA on orientation ERSP across all subjects."
    )
    parser.add_argument(
        "--outputs-root", type=Path, required=True,
        help="Root outputs directory containing sub-* folders."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Output directory. Defaults to outputs-root/group_level."
    )
    parser.add_argument("--p-threshold", type=float, default=0.05)
    args = parser.parse_args()

    outputs_root = args.outputs_root.resolve()
    out_dir = (args.out_dir or outputs_root / "group_level").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # For each subject: compute mean ERSP per orientation code
    # Shape per subject per code: (n_freqs, n_times)
    subject_means = {code: [] for code in ORIENTATION_CODES}
    freqs = None
    times = None
    loaded = 0

    for sub_dir in sorted(outputs_root.glob("sub-[0-9][0-9]")):
        ersp_files = sorted(sub_dir.glob("*-component_ersp.npy"))
        code_files = sorted(sub_dir.glob("*-component_ersp_event_codes.npy"))
        freqs_files = sorted(sub_dir.glob("*-component_ersp_freqs.npy"))
        times_files = sorted(sub_dir.glob("*-component_ersp_times.npy"))

        if not (ersp_files and code_files and freqs_files and times_files):
            print(f"  SKIP {sub_dir.name}: missing ERSP files.")
            continue

        ersp = np.load(ersp_files[0])          # (n_trials, n_components, n_freqs, n_times)
        codes = np.load(code_files[0])         # (n_trials,)
        f = np.load(freqs_files[0])
        t = np.load(times_files[0])

        if freqs is None:
            freqs = f
            times = t

        # Average over components → (n_trials, n_freqs, n_times)
        ersp_avg = ersp.mean(axis=1)

        for code in ORIENTATION_CODES:
            mask = codes == code
            if mask.sum() >= 1:
                # Smooth then average: (n_freqs, n_times)
                raw_mean = ersp_avg[mask].mean(axis=0)
                subject_means[code].append(smooth_map(raw_mean))

        loaded += 1
        print(f"  Loaded {sub_dir.name}")

    if loaded == 0:
        raise RuntimeError("No subjects with ERSP data found.")

    print(f"\nRunning group ANOVA across {loaded} subjects...")

    # ANOVA: for each pixel, test across orientation codes
    # Each group = list of subject means for that code
    n_freqs, n_times = freqs.shape[0], times.shape[0]
    f_map = np.full((n_freqs, n_times), np.nan)
    p_map = np.full((n_freqs, n_times), np.nan)

    usable_codes = [c for c in ORIENTATION_CODES if len(subject_means[c]) >= 2]
    if len(usable_codes) < 2:
        raise RuntimeError("Not enough orientation codes with >=2 subjects.")

    for fi in range(n_freqs):
        for ti in range(n_times):
            samples = [
                np.array([sub_mean[fi, ti] for sub_mean in subject_means[code]])
                for code in usable_codes
            ]
            stat = f_oneway(*samples)
            f_map[fi, ti] = stat.statistic
            p_map[fi, ti] = stat.pvalue

    # Smooth F-map for display; use raw p_map for thresholding
    f_smooth = smooth_map(f_map)
    cluster_sig, _, n_clusters = cluster_mask_from_pvalues(p_map, threshold=args.p_threshold)

    print(f"  Found {n_clusters} significant cluster(s) at p < {args.p_threshold}.")

    # --- Plot ---
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(f"Group-Level ANOVA Across Stim Types 41–56 (N={loaded} subjects)", fontsize=12)

    extent = [times[0], times[-1], freqs[0], freqs[-1]]

    im0 = axes[0, 0].imshow(f_smooth, aspect="auto", origin="lower", extent=extent, cmap="viridis")
    axes[0, 0].set_title("F-statistics (ANOVA: Stim 41-56)")
    axes[0, 0].set_xlabel("Time (s)")
    axes[0, 0].set_ylabel("Frequency (Hz)")
    fig.colorbar(im0, ax=axes[0, 0])

    neglog = -np.log10(np.clip(p_map, 1e-12, None))
    im1 = axes[0, 1].imshow(neglog, aspect="auto", origin="lower", extent=extent, cmap="magma")
    axes[0, 1].set_title("-log10(p-value) (ANOVA: Stim 41-56)")
    axes[0, 1].set_xlabel("Time (s)")
    axes[0, 1].set_ylabel("Frequency (Hz)")
    fig.colorbar(im1, ax=axes[0, 1])

    im2 = axes[1, 0].imshow(
        cluster_sig.astype(float), aspect="auto", origin="lower",
        extent=extent, cmap="plasma", vmin=0, vmax=1,
    )
    axes[1, 0].set_title(f"Significant Clusters (p < {args.p_threshold})")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].set_ylabel("Frequency (Hz)")
    fig.colorbar(im2, ax=axes[1, 0])

    # Bar: mean ERSP per orientation code in significant clusters
    ax_bar = axes[1, 1]
    if cluster_sig.any():
        bar_means, bar_sems, bar_labels = [], [], []
        for code in usable_codes:
            vals = np.array([sub_mean[cluster_sig].mean() for sub_mean in subject_means[code]])
            bar_means.append(vals.mean())
            bar_sems.append(vals.std(ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else 0.0)
            bar_labels.append(str(code))
        ax_bar.bar(bar_labels, bar_means, yerr=bar_sems, color="#5b8db8", capsize=3)
        ax_bar.set_title("Mean ERSP in Sig. Clusters (±SEM)")
        ax_bar.set_xlabel("Stimulus Type")
        ax_bar.set_ylabel("Mean ERSP")
        ax_bar.tick_params(axis="x", labelsize=8)
    else:
        ax_bar.text(0.5, 0.5, "No significant clusters", ha="center", va="center",
                    transform=ax_bar.transAxes)
        ax_bar.axis("off")

    fig.tight_layout()
    out_path = out_dir / "group_orientation_ersp_stats.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"Saved: {out_path}")

    summary = {
        "n_subjects": loaded,
        "usable_codes": usable_codes,
        "n_significant_clusters": n_clusters,
        "p_threshold": args.p_threshold,
    }
    write_json(out_dir / "group_orientation_ersp_stats_summary.json", summary)


if __name__ == "__main__":
    main()
