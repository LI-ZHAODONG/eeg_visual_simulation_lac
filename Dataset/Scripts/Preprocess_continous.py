import sys
import subprocess
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
    # This file is: Dataset/Scripts/run_all_subjects.py
    scripts_dir = Path(__file__).resolve().parent      # .../Dataset/Scripts
    dataset_root = scripts_dir.parent                  # .../Dataset
    subjects_root = dataset_root / "ds006547"          # .../Dataset/ds006547

    preprocess_script = scripts_dir / "preprocess.py"

    if not preprocess_script.exists():
        raise FileNotFoundError(f"preprocess.py not found at {preprocess_script}")

    if not subjects_root.exists():
        raise FileNotFoundError(f"'ds006547' folder not found at {subjects_root}")

    # Find all subject folders inside ds006547/
    sub_dirs = sorted(
        d for d in subjects_root.iterdir()
        if d.is_dir() and d.name.startswith("sub-")
    )

    if not sub_dirs:
        print(f"No sub-* directories found inside '{subjects_root}'")
        return

    print(f"Found {len(sub_dirs)} subjects in {subjects_root}.\n")

    for sub_dir in sub_dirs:
        sub_name = sub_dir.name
        vhdr_path = find_vhdr(sub_dir)

        if vhdr_path is None:
            print(f"[{sub_name}] No .vhdr found in {sub_dir}/ses-01/eeg → skipping.\n")
            continue

        # Outputs go to: Dataset/outputs/sub-XX
        out_dir = dataset_root / "outputs" / sub_name
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{sub_name}]")
        print(f"  VHDR:    {vhdr_path}")
        print(f"  OUT_DIR: {out_dir}")

        # Build arguments relative to Dataset/ (dataset_root)
        vhdr_arg = vhdr_path.relative_to(dataset_root)
        out_arg = out_dir.relative_to(dataset_root)

        cmd = [
            sys.executable,                 # same Python interpreter / venv
            str(preprocess_script),         # Scripts/preprocess.py
            "--vhdr", str(vhdr_arg),        # e.g. ds006547/sub-01/ses-01/eeg/...
            "--out_dir", str(out_arg),      # e.g. outputs/sub-01
        ]

        print("  Running:", " ".join(cmd))
        # IMPORTANT: run with cwd = Dataset/
        result = subprocess.run(cmd, cwd=str(dataset_root))

        if result.returncode == 0:
            print("  ➜ DONE\n")
        else:
            print(f"  ➜ ERROR (code {result.returncode})\n")


if __name__ == "__main__":
    main()
