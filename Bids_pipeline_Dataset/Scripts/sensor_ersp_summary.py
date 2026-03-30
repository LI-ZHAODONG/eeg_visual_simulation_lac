import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import mne
import numpy as np

matplotlib.use("Agg")


def infer_recording_name(subject):
    return f"sub-{subject}_ses-01_task-visual_eeg"


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
        "--subject", type=str, default=None,
        help="Subject ID (e.g. 01) or omit for all subjects"
    )
    parser.add_argument("--fmin", type=float, default=4.0)
    parser.add_argument("--fmax", type=float, default=100.0)
    parser.add_argument("--fstep", type=float, default=2.0)
    parser.add_argument("--n-cycles-factor", type=float, default=0.25)
    parser.add_argument("--baseline-start", type=float, default=-0.5)
    parser.add_argument("--baseline-end", type=float, default=0.0)
    parser.add_argument("--alpha-fmin", type=float, default=8.0)
    parser.add_argument("--alpha-fmax", type=float, default=13.0)
    parser.add_argument("--gamma-fmin", type=float, default=40.0)
    parser.add_argument("--gamma-fmax", type=float, default=80.0)
    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from utils import load_pipeline_epochs, get_custom_output_dir, ALL_SUBJECTS

    subjects_to_run = [args.subject] if args.subject else ALL_SUBJECTS

    for sub in subjects_to_run:
        try:
            out_dir = get_custom_output_dir(sub)
            recording = infer_recording_name(sub)
            
            out_path = out_dir / f"{recording}-sensor_ersp_summary.png"
            if out_path.exists():
                print(f"Skipping {sub}: output already exists at {out_path}")
                continue

            print(f"\n--- Loading epochs for subject: {sub} ---")
            epochs = load_pipeline_epochs(sub)
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

            # Stimulus window (post-onset) for topomap: 0.1 to 3.0s
            time_mask = (tfr.times >= 0.1) & (tfr.times <= 3.0)
            alpha_topo = corrected[:, alpha_mask, :][:, :, time_mask].mean(axis=(1, 2))
            gamma_topo = corrected[:, gamma_mask, :][:, :, time_mask].mean(axis=(1, 2))

            # Trim to safe inner window for group analysis (-0.2 to 3.0s)
            # to remove Morlet wavelet edge artifacts
            safe_mask = (tfr.times >= -0.2) & (tfr.times <= 3.0)
            corrected_trimmed = corrected[:, :, safe_mask]
            times_trimmed = tfr.times[safe_mask]

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

            # Save arrays for group averaging (trimmed to safe window)
            np.save(out_dir / f"{recording}-sensor_ersp_corrected.npy", corrected_trimmed)
            np.save(out_dir / f"{recording}-sensor_ersp_freqs.npy", freqs)
            np.save(out_dir / f"{recording}-sensor_ersp_times.npy", times_trimmed)
            np.save(out_dir / f"{recording}-sensor_ersp_alpha_topo.npy", alpha_topo)
            np.save(out_dir / f"{recording}-sensor_ersp_gamma_topo.npy", gamma_topo)
            print(f"Saved sensor ERSP arrays for group averaging.")
            
        except Exception as e:
            print(f"Failed to process subject {sub}: {e}")

if __name__ == "__main__":
    main()
