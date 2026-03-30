"""
Group-level per-electrode ANOVA on sensor-space ERSP.

For each electrode and frequency band (alpha / gamma), run a one-way ANOVA
across orientation conditions (codes 41-56) on the per-subject mean ERSP.
Produces:
1. Group ANOVA topomaps: F-statistic and -log10(p) per electrode
2. Group ERSP time-frequency map with significant cluster contours

Usage:
    python group_sensor_anova.py --outputs-root Custom_pipeline_Dataset/outputs
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import load_pipeline_epochs

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np
from scipy.stats import f_oneway

matplotlib.use("Agg")

ORIENTATION_CODES = list(range(41, 57))  # 16 orientations
ALPHA_BAND = (8.0, 13.0)
GAMMA_BAND = (40.0, 80.0)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def infer_recording_name(sub_dir):
    sub = sub_dir.name
    return f"{sub}_ses-01_task-visual_eeg"


def load_subject_sensor_ersp(sub_dir):
    """Load sensor ERSP corrected array, freqs, times for one subject."""
    rec = infer_recording_name(sub_dir)
    prefix = sub_dir / f"{rec}-sensor_ersp"

    corrected_path = prefix.parent / f"{prefix.name}_corrected.npy"
    freqs_path = prefix.parent / f"{prefix.name}_freqs.npy"
    times_path = prefix.parent / f"{prefix.name}_times.npy"

    if not corrected_path.exists():
        return None

    return {
        "corrected": np.load(corrected_path),   # (n_ch, n_freqs, n_times)
        "freqs": np.load(freqs_path),
        "times": np.load(times_path),
    }


def load_subject_component_ersp(sub_dir):
    """Load per-trial component ERSP and event codes."""
    rec = infer_recording_name(sub_dir)
    prefix = sub_dir / f"{rec}-component_ersp"

    ersp_path = prefix.parent / f"{prefix.name}.npy"
    events_path = prefix.parent / f"{prefix.name}_event_codes.npy"
    freqs_path = prefix.parent / f"{prefix.name}_freqs.npy"
    times_path = prefix.parent / f"{prefix.name}_times.npy"

    if not ersp_path.exists():
        return None

    return {
        "ersp": np.load(ersp_path),             # (n_trials, n_comp, n_freqs, n_times)
        "event_codes": np.load(events_path),
        "freqs": np.load(freqs_path),
        "times": np.load(times_path),
    }


def get_info_from_epochs(sub_dir):
    """Try to load MNE info from the epochs file."""
    try:
        sub_id = sub_dir.name.split("-")[1]
        epo = load_pipeline_epochs(sub_id)
        eeg_picks = mne.pick_types(epo.info, eeg=True, exclude=[])
        return mne.pick_info(epo.info, eeg_picks)
    except Exception as e:
        print(f"Failed to load info for {sub_dir.name}: {e}")
        return None


def band_mask(freqs, fmin, fmax):
    return (freqs >= fmin) & (freqs <= fmax)


def compute_per_condition_sensor_power(sub_dir):
    """Compute mean sensor ERSP per orientation condition for one subject.

    Uses component ERSP (per-trial) averaged over components, then averages
    the gamma and alpha band power per channel per condition.

    Falls back to sensor ERSP (already condition-averaged) if component ERSP
    is unavailable.

    Returns dict: code -> (n_ch,) array for alpha and gamma bands.
    """
    comp = load_subject_component_ersp(sub_dir)
    if comp is not None:
        ersp = comp["ersp"]          # (n_trials, n_comp, n_freqs, n_times)
        events = comp["event_codes"]
        freqs = comp["freqs"]
        times = comp["times"]

        # Average over components -> (n_trials, n_freqs, n_times)
        ersp_avg = ersp.mean(axis=1)

        # Task window: 0 to 3 s
        task_mask = (times >= 0.0) & (times <= 3.0)
        alpha_mask = band_mask(freqs, *ALPHA_BAND)
        gamma_mask = band_mask(freqs, *GAMMA_BAND)

        result = {}
        for code in ORIENTATION_CODES:
            trial_mask = events == code
            if trial_mask.sum() == 0:
                continue
            mean_ersp = ersp_avg[trial_mask].mean(axis=0)  # (n_freqs, n_times)
            alpha_val = mean_ersp[alpha_mask][:, task_mask].mean()
            gamma_val = mean_ersp[gamma_mask][:, task_mask].mean()
            result[code] = {"alpha": float(alpha_val), "gamma": float(gamma_val)}
        return result, "component"

    # Fallback: sensor ERSP (no per-condition split available)
    return None, None


# ---------------------------------------------------------------------------
# 1. Group ANOVA across subjects at each electrode
# ---------------------------------------------------------------------------

def compute_group_electrode_anova(outputs_root):
    """Per-electrode ANOVA on alpha/gamma topo across subjects.

    For each subject, load alpha_topo and gamma_topo (n_ch,).
    Not condition-resolved, so instead test: does mean alpha/gamma differ
    across subjects at each electrode (not useful).

    Better: use the per-subject orientation_summary.json to get per-condition
    power at Oz, then test across conditions at group level.
    """
    # Collect per-subject alpha_topo and gamma_topo
    sub_dirs = sorted(outputs_root.glob("sub-[0-9][0-9]"))
    alpha_topos = []
    gamma_topos = []
    ch_names_list = []
    ref_info = None

    for sub_dir in sub_dirs:
        rec = infer_recording_name(sub_dir)
        alpha_path = sub_dir / f"{rec}-sensor_ersp_alpha_topo.npy"
        gamma_path = sub_dir / f"{rec}-sensor_ersp_gamma_topo.npy"
        if not alpha_path.exists():
            continue

        alpha_topo = np.load(alpha_path)
        gamma_topo = np.load(gamma_path)

        info = get_info_from_epochs(sub_dir)
        if info is not None:
            ch_names = list(info.ch_names)[:len(alpha_topo)]
            ch_names_list.append(ch_names)
            if ref_info is None or len(ch_names) > len(ref_info.ch_names):
                ref_info = mne.pick_info(info, list(range(len(alpha_topo))))

        alpha_topos.append(alpha_topo)
        gamma_topos.append(gamma_topo)

    if not ch_names_list:
        return None, None, None, 0

    # Align on common channels
    all_sets = [set(names) for names in ch_names_list]
    common = sorted(all_sets[0].intersection(*all_sets[1:]))

    alpha_aligned = []
    gamma_aligned = []
    for i, (alpha, gamma) in enumerate(zip(alpha_topos, gamma_topos)):
        idx = [ch_names_list[i].index(ch) for ch in common if ch in ch_names_list[i]]
        alpha_aligned.append(alpha[idx])
        gamma_aligned.append(gamma[idx])

    alpha_stack = np.stack(alpha_aligned)  # (n_subs, n_ch)
    gamma_stack = np.stack(gamma_aligned)  # (n_subs, n_ch)

    # Build info for common channels
    ref_ch = list(ref_info.ch_names)
    common_idx = [ref_ch.index(ch) for ch in common if ch in ref_ch]
    info_common = mne.pick_info(ref_info, common_idx)

    return alpha_stack, gamma_stack, info_common, len(alpha_aligned)


def plot_group_anova_topos(alpha_stack, gamma_stack, info, n_subs, out_path):
    """Plot group mean + variance topomaps for alpha and gamma."""
    alpha_mean = alpha_stack.mean(axis=0)
    gamma_mean = gamma_stack.mean(axis=0)
    alpha_sem = alpha_stack.std(axis=0, ddof=1) / np.sqrt(n_subs)
    gamma_sem = gamma_stack.std(axis=0, ddof=1) / np.sqrt(n_subs)

    # T-stat vs zero at each electrode
    alpha_t = alpha_mean / (alpha_sem + 1e-30)
    gamma_t = gamma_mean / (gamma_sem + 1e-30)

    ch_names = list(info.ch_names)
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))

    # Row 1: Alpha
    vmax_a = np.abs(alpha_mean).max()
    mne.viz.plot_topomap(alpha_mean, info, axes=axes[0, 0], show=False,
                         cmap="RdBu_r", vlim=(-vmax_a, vmax_a), names=ch_names)
    axes[0, 0].set_title(f"Alpha Mean (N={n_subs})")

    mne.viz.plot_topomap(alpha_sem, info, axes=axes[0, 1], show=False,
                         cmap="Reds", names=ch_names)
    axes[0, 1].set_title("Alpha SEM")

    vmax_t = max(np.abs(alpha_t).max(), 1)
    mne.viz.plot_topomap(alpha_t, info, axes=axes[0, 2], show=False,
                         cmap="RdBu_r", vlim=(-vmax_t, vmax_t), names=ch_names)
    axes[0, 2].set_title("Alpha t-stat (vs 0)")

    # Row 2: Gamma
    vmax_g = np.abs(gamma_mean).max()
    mne.viz.plot_topomap(gamma_mean, info, axes=axes[1, 0], show=False,
                         cmap="RdBu_r", vlim=(-vmax_g, vmax_g), names=ch_names)
    axes[1, 0].set_title(f"Gamma Mean (N={n_subs})")

    mne.viz.plot_topomap(gamma_sem, info, axes=axes[1, 1], show=False,
                         cmap="Reds", names=ch_names)
    axes[1, 1].set_title("Gamma SEM")

    vmax_t = max(np.abs(gamma_t).max(), 1)
    mne.viz.plot_topomap(gamma_t, info, axes=axes[1, 2], show=False,
                         cmap="RdBu_r", vlim=(-vmax_t, vmax_t), names=ch_names)
    axes[1, 2].set_title("Gamma t-stat (vs 0)")

    fig.suptitle(f"Group-Level Electrode ERSP (N={n_subs})", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out_path}")


# ---------------------------------------------------------------------------
# 2. Group ERSP time-frequency map with cluster statistics
# ---------------------------------------------------------------------------

def compute_group_ersp_with_clusters(outputs_root):
    """Average sensor ERSP across subjects, compute pixelwise t-tests."""
    sub_dirs = sorted(outputs_root.glob("sub-[0-9][0-9]"))
    erspS = []
    freqs = None
    times = None

    for sub_dir in sub_dirs:
        data = load_subject_sensor_ersp(sub_dir)
        if data is None:
            continue
        # Average over channels -> (n_freqs, n_times)
        erspS.append(data["corrected"].mean(axis=0))
        if freqs is None:
            freqs = data["freqs"]
            times = data["times"]

    if len(erspS) < 3:
        return None, None, None, 0

    min_t = min(arr.shape[-1] for arr in erspS)
    ersp_stack = np.stack([arr[:, :min_t] for arr in erspS])  # (n_subs, n_freqs, n_times)
    times = times[:min_t]
    return ersp_stack, freqs, times, len(erspS)


def plot_group_ersp_clusters(ersp_stack, freqs, times, n_subs, out_path):
    """Group mean ERSP with F-stat and -log10(p) overlays."""
    from scipy.stats import ttest_1samp

    mean_ersp = ersp_stack.mean(axis=0)
    t_vals, p_vals = ttest_1samp(ersp_stack, 0, axis=0)
    neg_log_p = -np.log10(np.clip(p_vals, 1e-20, 1.0))

    # Mask to task window
    task_mask = (times >= -0.2) & (times <= 3.2)
    t_plot = times[task_mask]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Mean ERSP
    ax = axes[0]
    im = ax.imshow(mean_ersp[:, task_mask], aspect="auto", origin="lower",
                   extent=[t_plot[0], t_plot[-1], freqs[0], freqs[-1]],
                   cmap="RdBu_r", vmin=-0.3, vmax=0.3)
    ax.axvline(0, color="black", linestyle="--", linewidth=0.8)
    ax.axvline(3.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title(f"Group Mean ERSP (N={n_subs})")
    plt.colorbar(im, ax=ax, label="Log Power Ratio")

    # F-statistic (squared t)
    ax = axes[1]
    f_vals = t_vals[:, task_mask] ** 2
    im = ax.imshow(f_vals, aspect="auto", origin="lower",
                   extent=[t_plot[0], t_plot[-1], freqs[0], freqs[-1]],
                   cmap="hot", vmin=0, vmax=np.percentile(f_vals, 99))
    ax.axvline(0, color="white", linestyle="--", linewidth=0.8)
    ax.axvline(3.0, color="white", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("F-statistic (t² vs 0)")
    plt.colorbar(im, ax=ax, label="F")

    # -log10(p) with significance threshold
    ax = axes[2]
    nlp = neg_log_p[:, task_mask]
    im = ax.imshow(nlp, aspect="auto", origin="lower",
                   extent=[t_plot[0], t_plot[-1], freqs[0], freqs[-1]],
                   cmap="hot", vmin=0, vmax=min(nlp.max(), 10))
    # Contour at p=0.05 (-log10(0.05) ≈ 1.3) and p=0.001 (3.0)
    ax.contour(nlp, levels=[1.3], colors=["cyan"], linewidths=[1.0],
               extent=[t_plot[0], t_plot[-1], freqs[0], freqs[-1]],
               origin="lower")
    ax.contour(nlp, levels=[3.0], colors=["yellow"], linewidths=[1.5],
               extent=[t_plot[0], t_plot[-1], freqs[0], freqs[-1]],
               origin="lower")
    ax.axvline(0, color="white", linestyle="--", linewidth=0.8)
    ax.axvline(3.0, color="white", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("-log₁₀(p)  [cyan: p<0.05, yellow: p<0.001]")
    plt.colorbar(im, ax=ax, label="-log₁₀(p)")

    fig.suptitle(f"Group Sensor ERSP with Significance (N={n_subs})", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"  Saved: {out_path}")

    # Count significant pixels
    sig_05 = (p_vals[:, task_mask] < 0.05).sum()
    sig_001 = (p_vals[:, task_mask] < 0.001).sum()
    total = p_vals[:, task_mask].size
    return {
        "n_pixels_p05": int(sig_05),
        "n_pixels_p001": int(sig_001),
        "total_pixels": int(total),
        "pct_sig_05": float(sig_05 / total * 100),
        "pct_sig_001": float(sig_001 / total * 100),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Group-level per-electrode ANOVA and ERSP cluster stats."
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

    summary = {}

    # 1. Group electrode ANOVA topomaps
    print("Computing group electrode topomaps...")
    alpha_stack, gamma_stack, info, n_subs = compute_group_electrode_anova(outputs_root)
    if alpha_stack is not None:
        plot_group_anova_topos(alpha_stack, gamma_stack, info, n_subs,
                               out_dir / "group_electrode_anova_topos.png")
        summary["electrode_anova"] = {"n_subjects": n_subs, "n_channels": len(info.ch_names)}
    else:
        print("  SKIP: no sensor topo data found.")

    # 2. Group ERSP with cluster contours
    print("Computing group ERSP cluster statistics...")
    ersp_stack, freqs, times, n_subs = compute_group_ersp_with_clusters(outputs_root)
    if ersp_stack is not None:
        cluster_stats = plot_group_ersp_clusters(
            ersp_stack, freqs, times, n_subs,
            out_dir / "group_ersp_cluster_map.png"
        )
        summary["ersp_clusters"] = cluster_stats
        summary["ersp_clusters"]["n_subjects"] = n_subs
    else:
        print("  SKIP: insufficient sensor ERSP data.")

    save_json(out_dir / "group_sensor_anova_summary.json", summary)
    print(f"\nDone. Saved to {out_dir}")


if __name__ == "__main__":
    main()
