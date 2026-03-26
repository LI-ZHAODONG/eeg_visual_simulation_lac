import mne
import os
from pathlib import Path
import matplotlib
matplotlib.use("Agg")  # allows saving figures without GUI

def main():
    # --------- IDs ----------
    sub_id = "sub-01"
    ses_id = "ses-01"
    rec_id = f"{sub_id}_{ses_id}_task-visual_eeg"  # sub-01_ses-01_task-visual_eeg

    # --------- Robust paths (based on your layout) ----------
    # script: eeg_visual_simulation_lac/Custom_pipeline_Dataset/Scripts/<this_file>.py
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[2]  # eeg_visual_simulation_lac/

    bids_root = Path(os.environ.get("BIDS_ROOT", project_root.parent / "ds006547"))
    vhdr_path = bids_root / sub_id / ses_id / "eeg" / f"{rec_id}.vhdr"

    # outputs: Custom_pipeline_Dataset/outputs/sub-01/
    out_dir = project_root / "Custom_pipeline_Dataset" / "outputs" / sub_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ica_path = out_dir / f"{rec_id}-ica.fif"

    # --------- Sanity prints ----------
    print("VHDR:", vhdr_path)
    print("VHDR exists:", vhdr_path.exists())
    print("ICA:", ica_path)
    print("ICA exists:", ica_path.exists())

    if not vhdr_path.exists():
        raise FileNotFoundError(f"Cannot find vhdr: {vhdr_path}")
    if not ica_path.exists():
        raise FileNotFoundError(f"Cannot find ICA file: {ica_path}")

    # --------- Load raw ----------
    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True)
    print("Raw channels:", len(raw.ch_names))
    print("First 20 ch_names:", raw.ch_names[:20])

    # Keep an untouched copy for "raw PSD"
    raw_orig = raw.copy()

    # --------- Load ICA and apply to a COPY ----------
    ica = mne.preprocessing.read_ica(ica_path)
    print("ICA exclude:", ica.exclude)

    clean_raw = ica.apply(raw.copy())  # IMPORTANT: apply to a copy

    # --------- PSD plots ----------
    # Raw PSD
    psd_raw = raw_orig.copy().pick_types(eeg=True).compute_psd(fmin=1, fmax=80)
    fig1 = psd_raw.plot(show=False)
    fig1.savefig(out_dir / f"{rec_id}-psd_raw.png", dpi=300)

    # Clean PSD
    psd_clean = clean_raw.copy().pick_types(eeg=True).compute_psd(fmin=1, fmax=80)
    fig2 = psd_clean.plot(show=False)
    fig2.savefig(out_dir / f"{rec_id}-psd_clean.png", dpi=300)

    # EEG picks (indices) — define BEFORE using
    picks_eeg = mne.pick_types(clean_raw.info, eeg=True)

    # RAW 10s (use raw_orig, same picks, same scaling)
    browser_raw = raw_orig.plot(
        picks=picks_eeg,
        n_channels=32,
        start=100.0,
        duration=10.0,
        scalings=dict(eeg=20e-6),
        remove_dc=True,
        show=False,
        block=False,
    )
    browser_raw.figure.savefig(out_dir / f"{rec_id}-raw_10s.png", dpi=300)

    # CLEAN 10s (use clean_raw, same picks, same scaling)
    browser_clean = clean_raw.plot(
        picks=picks_eeg,
        n_channels=32,
        start=100.0,
        duration=10.0,
        scalings=dict(eeg=20e-6),
        remove_dc=True,
        show=False,
        block=False,
    )
    browser_clean.figure.savefig(out_dir / f"{rec_id}-clean_10s.png", dpi=300)

    print("Saved:")
    print(" -", out_dir / f"{rec_id}-psd_raw.png")
    print(" -", out_dir / f"{rec_id}-psd_clean.png")
    print(" -", out_dir / f"{rec_id}-clean_10s.png")
    print(" -", out_dir / f"{rec_id}-raw_10s.png")


if __name__ == "__main__":
    main()
