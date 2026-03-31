import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils import load_pipeline_epochs

matplotlib.use("Agg")


def main():
    parser = argparse.ArgumentParser(
        description="Group-average sensor-space ERSP across all subjects."
    )
    parser.add_argument(
        "--outputs-root", type=Path, required=True,
        help="Root outputs directory containing sub-* folders."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Output directory. Defaults to outputs-root/group_level."
    )
    parser.add_argument("--alpha-fmin", type=float, default=8.0)
    parser.add_argument("--alpha-fmax", type=float, default=12.0)
    parser.add_argument("--gamma-fmin", type=float, default=40.0)
    parser.add_argument("--gamma-fmax", type=float, default=80.0)
    args = parser.parse_args()

    outputs_root = args.outputs_root.resolve()
    out_dir = (args.out_dir or outputs_root / "group_level").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mean_erspS = []
    # per subject: (ch_names_list, alpha_topo_array, gamma_topo_array)
    sub_topo_data = []
    freqs = None
    times = None
    ref_info = None  # info object with full channel set (most channels)

    sub_dirs = sorted(outputs_root.glob("sub-[0-9][0-9]"))
    loaded = 0

    for sub_dir in sub_dirs:
        ersp_files = sorted(sub_dir.glob("*-sensor_ersp_corrected.npy"))
        if not ersp_files:
            print(f"  SKIP {sub_dir.name}: no sensor ERSP array found.")
            continue

        corrected = np.load(ersp_files[0])        # (n_ch, n_freqs, n_times)
        freqs_sub = np.load(str(ersp_files[0]).replace("_corrected.npy", "_freqs.npy"))
        times_sub = np.load(str(ersp_files[0]).replace("_corrected.npy", "_times.npy"))
        alpha_topo = np.load(str(ersp_files[0]).replace("_corrected.npy", "_alpha_topo.npy"))
        gamma_topo = np.load(str(ersp_files[0]).replace("_corrected.npy", "_gamma_topo.npy"))

        mean_erspS.append(corrected.mean(axis=0))  # (n_freqs, n_times)

        if freqs is None:
            freqs = freqs_sub
            times = times_sub

        # Get EEG channel names matching the topo arrays
        try:
            sub_id = sub_dir.name.split("-")[1]
            epo = load_pipeline_epochs(sub_id)
            eeg_picks = mne.pick_types(epo.info, eeg=True, exclude=[])
            ch_names = [epo.ch_names[i] for i in eeg_picks]
            # Keep only as many names as topo entries (guard against mismatch)
            ch_names = ch_names[: len(alpha_topo)]
            if ref_info is None or len(ch_names) > len(ref_info.ch_names):
                ref_info = mne.pick_info(epo.info, eeg_picks[: len(alpha_topo)])
        except Exception as e:
            print(f"    Failed to get epo info: {e}")
            ch_names = None

        if ch_names is not None:
            sub_topo_data.append((ch_names, alpha_topo, gamma_topo))

        loaded += 1
        print(f"  Loaded {sub_dir.name}")

    if loaded == 0:
        raise RuntimeError("No subjects with sensor ERSP data found.")

    # Align topos by channel-name intersection across all subjects
    all_ch_sets = [set(names) for names, _, _ in sub_topo_data]
    common_chs = sorted(all_ch_sets[0].intersection(*all_ch_sets[1:]))
    print(f"  Common channels across all subjects: {len(common_chs)}")

    alpha_topos_filt = []
    gamma_topos_filt = []
    for ch_names, alpha_topo, gamma_topo in sub_topo_data:
        idx = [ch_names.index(ch) for ch in common_chs]
        alpha_topos_filt.append(alpha_topo[idx])
        gamma_topos_filt.append(gamma_topo[idx])

    # Build info matching common channels
    ref_ch_names = list(ref_info.ch_names)
    common_idx_in_ref = [ref_ch_names.index(ch) for ch in common_chs if ch in ref_ch_names]
    info_loaded = mne.pick_info(ref_info, common_idx_in_ref)

    n_topo = len(alpha_topos_filt)
    print(f"\nAveraging over {loaded} subjects (topomaps: {n_topo} with {len(common_chs)} common channels)...")

    # Match time axis to shortest length before mean
    min_t = min(arr.shape[-1] for arr in mean_erspS)
    ga_ersp = np.mean([arr[:, :min_t] for arr in mean_erspS], axis=0)
    times = times[:min_t]

    ga_alpha_topo = np.mean(alpha_topos_filt, axis=0)
    ga_gamma_topo = np.mean(gamma_topos_filt, axis=0)

    alpha_mask = (freqs >= args.alpha_fmin) & (freqs <= args.alpha_fmax)
    gamma_mask = (freqs >= args.gamma_fmin) & (freqs <= args.gamma_fmax)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # Left: group mean ERSP
    ax = axes[0]
    im = ax.imshow(
        ga_ersp,
        aspect="auto",
        origin="lower",
        extent=[times[0], times[-1], freqs[0], freqs[-1]],
        cmap="RdBu_r",
        vmin=-0.4,
        vmax=0.4,
    )
    ax.axvline(0, color="black", linestyle="--", linewidth=0.8)
    ax.axvline(3.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlim(times[0], 3.0)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title(f"Group Mean ERSP (N={loaded})")
    plt.colorbar(im, ax=ax, label="Log Power Ratio (log(Task/Baseline))")

    # Middle: gamma topomap
    ax_g = axes[1]
    vmax_g = np.abs(ga_gamma_topo).max()
    mne.viz.plot_topomap(
        ga_gamma_topo, info_loaded, axes=ax_g, show=False,
        cmap="RdBu_r", vlim=(-vmax_g, vmax_g),
    )
    ax_g.set_title(f"Group Mean Gamma ({args.gamma_fmin:.0f}–{args.gamma_fmax:.0f} Hz)")

    # Right: alpha topomap
    ax_a = axes[2]
    vmax_a = np.abs(ga_alpha_topo).max()
    mne.viz.plot_topomap(
        ga_alpha_topo, info_loaded, axes=ax_a, show=False,
        cmap="RdBu_r", vlim=(-vmax_a, vmax_a),
    )
    ax_a.set_title(f"Group Mean Alpha ({args.alpha_fmin:.0f}–{args.alpha_fmax:.0f} Hz)")

    fig.suptitle(f"Group-Level Sensor ERSP (N={loaded} subjects)", fontsize=11)
    fig.tight_layout()

    out_path = out_dir / "group_sensor_ersp_summary.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"Saved group sensor ERSP summary: {out_path}")


if __name__ == "__main__":
    main()
