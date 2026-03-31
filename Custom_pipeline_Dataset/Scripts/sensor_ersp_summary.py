import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np

matplotlib.use("Agg")


def infer_recording_name(epochs_path):
    name = epochs_path.name
    if name.endswith("-final-epo.fif"):
        return name[: -len("-final-epo.fif")]
    return epochs_path.stem


def baseline_correct_log(data, times, baseline=(-0.5, 0.0)):
    mask = (times >= baseline[0]) & (times < baseline[1])
    if not mask.any():
        raise RuntimeError(f"No samples in baseline window {baseline}.")
    log = np.log10(np.maximum(data, np.finfo(float).eps))
    log -= log[..., mask].mean(axis=-1, keepdims=True)
    return log


def main():
    parser = argparse.ArgumentParser(
        description="Sensor-space ERSP summary: mean TFR + alpha/gamma topomaps."
    )
    parser.add_argument(
        "--epochs-path", type=Path, required=True,
        help="Path to the cleaned *-final-epo.fif file."
    )
    parser.add_argument(
        "--out-dir", type=Path, default=None,
        help="Output directory. Defaults to the epochs file directory."
    )
    parser.add_argument("--fmin", type=float, default=4.0)
    parser.add_argument("--fmax", type=float, default=100.0)
    parser.add_argument("--fstep", type=float, default=2.0)
    parser.add_argument("--n-cycles-factor", type=float, default=0.25)
    parser.add_argument("--baseline-start", type=float, default=-0.5)
    parser.add_argument("--baseline-end", type=float, default=0.0)
    parser.add_argument("--alpha-fmin", type=float, default=8.0)
    parser.add_argument("--alpha-fmax", type=float, default=12.0)
    parser.add_argument("--gamma-fmin", type=float, default=40.0)
    parser.add_argument("--gamma-fmax", type=float, default=80.0)
    args = parser.parse_args()

    epochs_path = args.epochs_path.resolve()
    if not epochs_path.exists():
        raise FileNotFoundError(f"Cannot find epochs file: {epochs_path}")

    out_dir = (args.out_dir or epochs_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    recording = infer_recording_name(epochs_path)

    print(f"Loading epochs: {epochs_path}")
    epochs = mne.read_epochs(epochs_path, preload=True, verbose=False)
    eeg_picks = mne.pick_types(epochs.info, eeg=True, exclude=[])
    epochs = epochs.pick(eeg_picks)
    if epochs.info["sfreq"] > 200:
        epochs = epochs.resample(200, verbose=False)

    freqs = np.arange(args.fmin, args.fmax + args.fstep, args.fstep)
    n_cycles = np.maximum(freqs * args.n_cycles_factor, 2.0)

    print(
        f"Computing Morlet TFR: {len(freqs)} freqs, {len(epochs)} epochs, "
        f"{len(eeg_picks)} channels."
    )
    tfr = mne.time_frequency.tfr_morlet(
        epochs,
        freqs=freqs,
        n_cycles=n_cycles,
        use_fft=True,
        return_itc=False,
        average=True,
        output="power",
        verbose=False,
    )

    # Baseline correct (log ratio)
    corrected = baseline_correct_log(
        tfr.data,
        tfr.times,
        baseline=(args.baseline_start, args.baseline_end),
    )

    # Mean ERSP across all channels: shape (n_freqs, n_times)
    mean_ersp = corrected.mean(axis=0)

    # Band indices
    alpha_mask = (freqs >= args.alpha_fmin) & (freqs <= args.alpha_fmax)
    gamma_mask = (freqs >= args.gamma_fmin) & (freqs <= args.gamma_fmax)

    # Stimulus window (post-onset) for topomap: 0.1 to tmax
    time_mask = tfr.times >= 0.1
    alpha_topo = corrected[:, alpha_mask, :][:, :, time_mask].mean(axis=(1, 2))
    gamma_topo = corrected[:, gamma_mask, :][:, :, time_mask].mean(axis=(1, 2))

    # --- Plot ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    # Left: mean ERSP
    ax = axes[0]
    im = ax.imshow(
        mean_ersp,
        aspect="auto",
        origin="lower",
        extent=[tfr.times[0], tfr.times[-1], freqs[0], freqs[-1]],
        cmap="RdBu_r",
        vmin=-0.4,
        vmax=0.4,
    )
    ax.axvline(0, color="black", linestyle="--", linewidth=0.8)
    ax.axvline(3.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlim(tfr.times[0], 3.0)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Mean ERSP across all stimuli")
    plt.colorbar(im, ax=ax, label="Log Power Ratio (log(Task/Baseline))")

    # Middle: gamma topomap
    ax_g = axes[1]
    vmax_g = np.abs(gamma_topo).max()
    mne.viz.plot_topomap(
        gamma_topo,
        tfr.info,
        axes=ax_g,
        show=False,
        cmap="RdBu_r",
        vlim=(-vmax_g, vmax_g),
    )
    ax_g.set_title(f"Mean Gamma ({args.gamma_fmin:.0f}–{args.gamma_fmax:.0f} Hz) Topography")

    # Right: alpha topomap
    ax_a = axes[2]
    vmax_a = np.abs(alpha_topo).max()
    mne.viz.plot_topomap(
        alpha_topo,
        tfr.info,
        axes=ax_a,
        show=False,
        cmap="RdBu_r",
        vlim=(-vmax_a, vmax_a),
    )
    ax_a.set_title(f"Mean Alpha ({args.alpha_fmin:.0f}–{args.alpha_fmax:.0f} Hz) Topography")

    fig.suptitle(recording, fontsize=10)
    fig.tight_layout()

    out_path = out_dir / f"{recording}-sensor_ersp_summary.png"
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"Saved sensor ERSP summary: {out_path}")

    # Save arrays for group averaging
    np.save(out_dir / f"{recording}-sensor_ersp_corrected.npy", corrected)
    np.save(out_dir / f"{recording}-sensor_ersp_freqs.npy", freqs)
    np.save(out_dir / f"{recording}-sensor_ersp_times.npy", tfr.times)
    np.save(out_dir / f"{recording}-sensor_ersp_alpha_topo.npy", alpha_topo)
    np.save(out_dir / f"{recording}-sensor_ersp_gamma_topo.npy", gamma_topo)
    print(f"Saved sensor ERSP arrays for group averaging.")


if __name__ == "__main__":
    main()
