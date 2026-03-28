import sys
import mne
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # allows saving figures without GUI


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

    # Match the preprocessing pipeline: notch → bandpass → resample → apply ICA
    raw.notch_filter(freqs=[60, 120, 180], verbose=False)
    raw.filter(l_freq=1.0, h_freq=100.0, verbose=False)
    raw.resample(200, verbose=False)

    raw_orig = raw.copy()

    ica = mne.preprocessing.read_ica(ica_path)
    clean_raw = ica.apply(raw.copy())

    # Raw PSD
    psd_raw = raw_orig.copy().pick_types(eeg=True).compute_psd(fmin=1, fmax=80)
    fig1 = psd_raw.plot(show=False)
    fig1.savefig(out_dir / f"{rec_id}-psd_raw.png", dpi=300)

    # Clean PSD (ICA + notch)
    psd_clean = clean_raw.copy().pick_types(eeg=True).compute_psd(fmin=1, fmax=80)
    fig2 = psd_clean.plot(show=False)
    fig2.savefig(out_dir / f"{rec_id}-psd_clean.png", dpi=300)

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

    import matplotlib.pyplot as plt
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
