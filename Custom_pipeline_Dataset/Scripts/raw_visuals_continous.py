import mne
from pathlib import Path
from typing import Optional


def find_vhdr(sub_dir: Path) -> Optional[Path]:
    """
    Find the BrainVision .vhdr file for a subject.

    Expected structure:
        ds006547/sub-XX/ses-01/eeg/*.vhdr
    """
    eeg_dir = sub_dir / "ses-01" / "eeg"
    if not eeg_dir.exists():
        return None

    vhdr_files = sorted(eeg_dir.glob("*.vhdr"))
    if not vhdr_files:
        return None

    return vhdr_files[0]


def main():
    # This file is: Custom_pipeline_Dataset/Scripts/raw_visuals_continous.py
    scripts_dir = Path(__file__).resolve().parent      # .../Custom_pipeline_Dataset/Scripts
    dataset_root = scripts_dir.parent                  # .../Custom_pipeline_Dataset
    subjects_root = Path("/Volumes/personal/EEG/ds006547")  # BIDS dataset (external)
    outputs_root = dataset_root / "outputs"            # .../Custom_pipeline_Dataset/outputs

    if not subjects_root.exists():
        raise FileNotFoundError(f"'ds006547' folder not found at {subjects_root}")

    outputs_root.mkdir(exist_ok=True)

    # All subject folders: sub-01, sub-02, ...
    sub_dirs = sorted(
        d for d in subjects_root.iterdir()
        if d.is_dir() and d.name.startswith("sub-")
    )

    if not sub_dirs:
        print(f"No sub-* directories found inside '{subjects_root}'")
        return

    print(f"Found {len(sub_dirs)} subjects in {subjects_root}.\n")

    for sub_dir in sub_dirs:
        sub_name = sub_dir.name  # e.g. "sub-01"
        vhdr_path = find_vhdr(sub_dir)

        if vhdr_path is None:
            print(f"[{sub_name}] No .vhdr found in {sub_dir}/ses-01/eeg → skipping.\n")
            continue

        sub_stem = vhdr_path.stem  # e.g. "sub-01_ses-01_task-visual_eeg"

        out_dir = outputs_root / sub_name
        out_dir.mkdir(parents=True, exist_ok=True)

        ica_path = out_dir / f"{sub_stem}-ica.fif"
        if not ica_path.exists():
            print(f"[{sub_name}] ICA file not found at {ica_path} → skipping.\n")
            continue

        print(f"[{sub_name}]")
        print(f"  VHDR:    {vhdr_path}")
        print(f"  ICA:     {ica_path}")
        print(f"  OUT_DIR: {out_dir}")

        # Load raw + ICA
        raw = mne.io.read_raw_brainvision(vhdr_path, preload=True)
        ica = mne.preprocessing.read_ica(ica_path)

        # Apply ICA
        clean_raw = ica.apply(raw.copy())

        # Pick EEG channels only
        picks_eeg = mne.pick_types(clean_raw.info, eeg=True)
        print("  EEG channels:", [clean_raw.ch_names[p] for p in picks_eeg])

        # Plot a 10-second window, but do NOT show it
        browser = clean_raw.plot(
            picks=picks_eeg,
            n_channels=min(32, len(picks_eeg)),
            start=100.0,               # change if you want a different segment
            duration=10.0,
            scalings=dict(eeg=20e-6),  # 20 µV
            show=False,                # do not display
        )

        # In recent MNE versions, .plot returns a Browser object
        fig = browser.figure
        out_png = out_dir / f"{sub_stem}-raw_eeg_10s.png"
        fig.savefig(out_png, dpi=300)
        print(f"  Saved: {out_png}\n")


if __name__ == "__main__":
    main()
