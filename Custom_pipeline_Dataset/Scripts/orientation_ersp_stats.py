import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.ndimage import gaussian_filter, label
from scipy.stats import f_oneway

matplotlib.use("Agg")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def infer_recording_name(path):
    name = path.name
    if name.endswith("-component_ersp.npy"):
        return name[: -len("-component_ersp.npy")]
    return path.stem


def zscore(values):
    values = np.asarray(values, dtype=float)
    std = values.std(ddof=0)
    if std == 0:
        return np.zeros_like(values)
    return (values - values.mean()) / std


def reject_broadband_outliers(ersp, freqs, times, z_thresh=4.0):
    freq_mask = (freqs >= 80.0) & (freqs <= 100.0)
    time_mask = (times >= 0.0) & (times <= 3.0)
    if not freq_mask.any() or not time_mask.any():
        raise RuntimeError("80-100 Hz / 0-3 s window not present for outlier rejection.")

    trial_component_mean = ersp[:, :, freq_mask][:, :, :, time_mask].mean(axis=1)
    per_trial_max = trial_component_mean.max(axis=(1, 2))
    scores = zscore(per_trial_max)
    keep_mask = np.abs(scores) <= z_thresh
    return keep_mask, scores


def smooth_trials(ersp, sigma_freq=2.0, sigma_time=4.0):
    trial_avg = ersp.mean(axis=1)
    smoothed = np.empty_like(trial_avg)
    for idx in range(trial_avg.shape[0]):
        smoothed[idx] = gaussian_filter(trial_avg[idx], sigma=(sigma_freq, sigma_time))
    return smoothed


def pixelwise_anova(smoothed_trials, event_codes, valid_codes):
    n_freqs = smoothed_trials.shape[1]
    n_times = smoothed_trials.shape[2]
    f_map = np.full((n_freqs, n_times), np.nan)
    p_map = np.full((n_freqs, n_times), np.nan)

    groups = {code: smoothed_trials[event_codes == code] for code in valid_codes}
    usable_codes = [code for code, arr in groups.items() if len(arr) >= 2]
    if len(usable_codes) < 2:
        raise RuntimeError("Not enough orientation groups with >=2 trials for ANOVA.")

    for fi in range(n_freqs):
        for ti in range(n_times):
            samples = [groups[code][:, fi, ti] for code in usable_codes]
            stat = f_oneway(*samples)
            f_map[fi, ti] = stat.statistic
            p_map[fi, ti] = stat.pvalue

    return f_map, p_map


def cluster_mask_from_pvalues(p_map, threshold=0.01):
    sig = np.isfinite(p_map) & (p_map < threshold)
    structure = np.ones((3, 3), dtype=int)
    labeled, n_clusters = label(sig, structure=structure)
    return sig, labeled, int(n_clusters)


def cluster_average_by_trigger(smoothed_trials, event_codes, valid_codes, cluster_mask):
    values = []
    for code in valid_codes:
        trial_mask = event_codes == code
        if not trial_mask.any():
            continue
        cluster_vals = smoothed_trials[trial_mask][:, cluster_mask]
        mean_per_trial = cluster_vals.mean(axis=1)
        values.append(
            {
                "code": int(code),
                "mean": float(mean_per_trial.mean()),
                "sem": float(mean_per_trial.std(ddof=1) / np.sqrt(len(mean_per_trial)))
                if len(mean_per_trial) > 1
                else 0.0,
                "n_trials": int(len(mean_per_trial)),
            }
        )
    return values


def plot_maps(freqs, times, f_map, p_map, cluster_mask, out_path):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))

    im0 = axes[0, 0].imshow(
        f_map,
        aspect="auto",
        origin="lower",
        extent=[times[0], times[-1], freqs[0], freqs[-1]],
        cmap="viridis",
    )
    axes[0, 0].set_title("F-statistics (ANOVA: Stim 41-56)")
    axes[0, 0].set_xlabel("Time (s)")
    axes[0, 0].set_ylabel("Frequency (Hz)")
    fig.colorbar(im0, ax=axes[0, 0])

    neglog = -np.log10(np.clip(p_map, 1e-12, None))
    im1 = axes[0, 1].imshow(
        neglog,
        aspect="auto",
        origin="lower",
        extent=[times[0], times[-1], freqs[0], freqs[-1]],
        cmap="magma",
    )
    axes[0, 1].set_title("-log10(p-value) (ANOVA: Stim 41-56)")
    axes[0, 1].set_xlabel("Time (s)")
    axes[0, 1].set_ylabel("Frequency (Hz)")
    fig.colorbar(im1, ax=axes[0, 1])

    im2 = axes[1, 0].imshow(
        cluster_mask.astype(float),
        aspect="auto",
        origin="lower",
        extent=[times[0], times[-1], freqs[0], freqs[-1]],
        cmap="plasma",
        vmin=0,
        vmax=1,
    )
    axes[1, 0].set_title("Significant Clusters (p < 0.010)")
    axes[1, 0].set_xlabel("Time (s)")
    axes[1, 0].set_ylabel("Frequency (Hz)")
    fig.colorbar(im2, ax=axes[1, 0])

    axes[1, 1].axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_cluster_bar(cluster_rows, out_path):
    labels = [str(row["code"]) for row in cluster_rows]
    means = [row["mean"] for row in cluster_rows]
    sems = [row["sem"] for row in cluster_rows]

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(labels, means, yerr=sems, color="#5b8db8", capsize=3)
    ax.set_title("Mean ERSP in Significant Clusters (±SEM)")
    ax.set_xlabel("Stimulus Type")
    ax.set_ylabel("Mean ERSP")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_freq_corr(freqs, spectra, out_path):
    corr = np.corrcoef(spectra, rowvar=False)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(
        corr,
        origin="lower",
        cmap="coolwarm",
        vmin=-0.5,
        vmax=0.5,
        extent=[freqs[0], freqs[-1], freqs[0], freqs[-1]],
    )
    ax.set_title("Freq × Freq Correlation")
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Frequency (Hz)")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return corr


OCCIPITAL_CHANNELS = {"Oz", "O1", "O2", "POz", "PO3", "PO4", "PO7", "PO8", "Iz"}


def get_occipital_component_mask(ica_path, kept_components, min_fraction=0.15):
    """Return boolean mask over kept_components selecting occipital-dominant ones."""
    ica = mne.preprocessing.read_ica(ica_path, verbose=False)
    mixing = ica.get_components()          # (n_channels, n_ica_components)
    ch_names = ica.ch_names

    occ_indices = [i for i, ch in enumerate(ch_names) if ch in OCCIPITAL_CHANNELS]
    if not occ_indices:
        print("  WARNING: No occipital channels found in ICA — using all components.")
        return np.ones(len(kept_components), dtype=bool)

    mask = []
    for comp_idx in kept_components:
        if comp_idx >= mixing.shape[1]:
            mask.append(False)
            continue
        topo = np.abs(mixing[:, comp_idx])
        total = topo.sum()
        occ_weight = topo[occ_indices].sum()
        fraction = occ_weight / total if total > 0 else 0.0
        mask.append(fraction >= min_fraction)

    n_occ = sum(mask)
    print(f"  Occipital components: {n_occ}/{len(kept_components)} kept.")
    return np.array(mask, dtype=bool)


def main():
    parser = argparse.ArgumentParser(
        description="Compute paper-style ERSP orientation statistics from retained ICA components."
    )
    parser.add_argument("--ersp-npy", type=Path, required=True)
    parser.add_argument("--event-codes-npy", type=Path, required=True)
    parser.add_argument("--freqs-npy", type=Path, required=True)
    parser.add_argument("--times-npy", type=Path, required=True)
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(__file__).resolve().parent / "condition_mapping.json",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--ica-path", type=Path, default=None,
        help="Path to ICA .fif. If provided, filters to occipital components only.",
    )
    parser.add_argument(
        "--kept-components-npy", type=Path, default=None,
        help="Path to *-component_ersp_kept_components.npy.",
    )
    parser.add_argument(
        "--occipital-min-fraction", type=float, default=0.15,
        help="Minimum fraction of weight on occipital channels to keep a component.",
    )
    args = parser.parse_args()

    ersp_path = args.ersp_npy.resolve()
    event_codes_path = args.event_codes_npy.resolve()
    freqs_path = args.freqs_npy.resolve()
    times_path = args.times_npy.resolve()
    mapping = load_json(args.mapping_json.resolve())

    out_dir = (args.out_dir or ersp_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    recording = infer_recording_name(ersp_path)
    ersp = np.load(ersp_path)
    event_codes = np.load(event_codes_path)
    freqs = np.load(freqs_path)
    times = np.load(times_path)

    orientation_codes = np.array(mapping["families"]["orientation"]["codes"], dtype=int)
    orientation_mask = np.isin(event_codes, orientation_codes)
    ersp = ersp[orientation_mask]
    event_codes = event_codes[orientation_mask]

    # Filter to occipital components if ICA path provided
    if args.ica_path and args.kept_components_npy:
        kept_components = np.load(args.kept_components_npy.resolve()).tolist()
        occ_mask = get_occipital_component_mask(
            args.ica_path.resolve(), kept_components, args.occipital_min_fraction
        )
        if occ_mask.any():
            ersp = ersp[:, occ_mask, :, :]
        else:
            print("  WARNING: No occipital components found — using all components.")

    keep_mask, outlier_scores = reject_broadband_outliers(ersp, freqs, times, z_thresh=4.0)
    ersp = ersp[keep_mask]
    event_codes = event_codes[keep_mask]

    smoothed = smooth_trials(ersp, sigma_freq=2.0, sigma_time=4.0)
    f_map, p_map = pixelwise_anova(smoothed, event_codes, orientation_codes)
    sig_mask, labeled, n_clusters = cluster_mask_from_pvalues(p_map, threshold=0.01)
    cluster_rows = cluster_average_by_trigger(smoothed, event_codes, orientation_codes, sig_mask)

    poststim_mask = (times >= 0.0) & (times <= 3.0)
    spectra = smoothed[:, :, poststim_mask].mean(axis=-1)
    freq_corr = plot_freq_corr(freqs, spectra, out_dir / "orientation_freq_corr.png")

    maps_path = out_dir / "orientation_anova_maps.png"
    cluster_bar_path = out_dir / "orientation_cluster_bar.png"
    plot_maps(freqs, times, f_map, p_map, sig_mask, maps_path)
    plot_cluster_bar(cluster_rows, cluster_bar_path)

    summary = {
        "recording": recording,
        "n_orientation_trials": int(len(event_codes)),
        "n_clusters": n_clusters,
        "outlier_rejection": {
            "kept_trials": int(keep_mask.sum()),
            "rejected_trials": int((~keep_mask).sum()),
            "z_threshold": 4.0,
        },
        "cluster_rows": cluster_rows,
        "outputs": {
            "anova_maps": str(maps_path),
            "cluster_bar": str(cluster_bar_path),
            "freq_corr": str(out_dir / "orientation_freq_corr.png"),
        },
    }
    write_json(out_dir / "orientation_ersp_stats_summary.json", summary)
    print(f"Saved ERSP orientation stats into: {out_dir}")


if __name__ == "__main__":
    main()
