import sys
import mne
import os
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")  # allows saving figures without GUI
import matplotlib.pyplot as plt


def process_subject(sub_id: str, project_root: Path, bids_root: Path):
    ses_id = "ses-01"
    rec_id = f"{sub_id}_{ses_id}_task-visual_eeg"

    vhdr_path = bids_root / sub_id / ses_id / "eeg" / f"{rec_id}.vhdr"
    out_dir = project_root / "Custom_pipeline_Dataset" / "outputs" / sub_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ica_path = out_dir / f"{rec_id}-ica.fif"

    if not vhdr_path.exists():
        print(f"  [SKIP] VHDR not found: {vhdr_path}")
        return
    if not ica_path.exists():
        print(f"  [SKIP] ICA not found: {ica_path}")
        return

    print(f"\n--- {sub_id} ---")

    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True, verbose=False)

    raw_orig = raw.copy()  # truly unfiltered — kept for psd_raw plot

    # Match the preprocessing pipeline: notch → bandpass → resample → apply ICA
    raw.notch_filter(freqs=[60, 120, 180], verbose=False)
    raw.filter(l_freq=1.0, h_freq=100.0, verbose=False)
    raw.resample(200, verbose=False)

    ica = mne.preprocessing.read_ica(ica_path)
    clean_raw = ica.apply(raw.copy())

    # Raw PSD (unfiltered — 60 Hz spike visible)
    psd_raw = raw_orig.copy().pick_types(eeg=True).compute_psd(fmin=1, fmax=80)
    fig1 = psd_raw.plot(show=False)
    fig1.axes[0].set_title("Raw EEG — Power Spectral Density (1–80 Hz)")
    fig1.savefig(out_dir / f"{rec_id}-psd_raw.png", dpi=300)

    # Clean PSD (after notch + bandpass + ICA)
    psd_clean = clean_raw.copy().pick_types(eeg=True).compute_psd(fmin=1, fmax=80)
    fig2 = psd_clean.plot(show=False)
    for ax in fig2.axes:
        if ax.get_ylabel():
            ax.set_title("Clean EEG — After Notch + Bandpass + ICA (1–80 Hz)")
            ax.set_ylim(bottom=-20)
    fig2.savefig(out_dir / f"{rec_id}-psd_clean.png", dpi=300)

    # Comparison: mean of the same PSD objects used above
    raw_mean = 10 * np.log10(psd_raw.get_data().mean(axis=0) * 1e12)
    cln_mean = 10 * np.log10(psd_clean.get_data().mean(axis=0) * 1e12)
    freqs_r = psd_raw.freqs
    freqs_c = psd_clean.freqs

    fig3, ax3 = plt.subplots(figsize=(10, 4))
    ax3.plot(freqs_r, raw_mean, label="Raw", color="tab:red", alpha=0.8)
    ax3.plot(freqs_c, cln_mean, label="Clean (notch + bandpass + ICA)",
             color="tab:blue", alpha=0.8)
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Power (dB/Hz re 1 µV²)")
    ax3.set_title("PSD comparison — Raw vs Clean")
    ax3.set_ylim(bottom=-20)
    ax3.legend()
    ax3.set_xlim(1, 80)
    fig3.tight_layout()
    fig3.savefig(out_dir / f"{rec_id}-psd_comparison.png", dpi=300)

    picks_eeg = mne.pick_types(clean_raw.info, eeg=True)

    browser_raw = raw_orig.plot(
        picks=picks_eeg, n_channels=32, start=100.0, duration=10.0,
        scalings=dict(eeg=20e-6), remove_dc=True, show=False, block=False,
    )
    browser_raw.figure.savefig(out_dir / f"{rec_id}-raw_10s.png", dpi=300)

    browser_clean = clean_raw.plot(
        picks=picks_eeg, n_channels=32, start=100.0, duration=10.0,
        scalings=dict(eeg=20e-6), remove_dc=True, show=False, block=False,
    )
    browser_clean.figure.savefig(out_dir / f"{rec_id}-clean_10s.png", dpi=300)

    plt.close("all")

    print(f"  Saved psd_raw, psd_clean, raw_10s, clean_10s → {out_dir}")


def main():
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[2]
    bids_root = Path(os.environ.get("BIDS_ROOT", project_root.parent / "ds006547"))

    # Accept optional subject list from command line, e.g.: python raw_visual.py sub-01 sub-02
    # Default: all subjects sub-01 to sub-31
    if len(sys.argv) > 1:
        subjects = sys.argv[1:]
    else:
        subjects = [f"sub-{i:02d}" for i in range(1, 32)]

    print(f"Processing {len(subjects)} subject(s): {subjects[0]} … {subjects[-1]}")
    for sub_id in subjects:
        process_subject(sub_id, project_root, bids_root)

    print("\nDone.")


if __name__ == "__main__":
    main()
