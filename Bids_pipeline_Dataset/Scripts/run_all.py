#!/usr/bin/env python3
"""
Run all custom analyses in sequence.

This script runs after MNE-BIDS-Pipeline has produced cleaned epochs.
It replaces the analysis steps from Phase_1.sh (steps 4-9) and Phase_2.sh.

Usage:
    # Run all analyses for all subjects
    python run_all.py

    # Run for one subject only
    python run_all.py --subject 01

    # Skip group-level (useful for testing single subject)
    python run_all.py --subject 01 --skip-group
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def run_script(script_name, extra_args=None):
    """Run a script from the Scripts directory."""
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)]
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n{'='*60}")
    print(f"  Running: {script_name}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, cwd=SCRIPTS_DIR)
    if result.returncode != 0:
        print(f"  WARNING: {script_name} exited with code {result.returncode}")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run all custom analyses")
    parser.add_argument("--subject", default=None, help="Single subject (e.g., 01)")
    parser.add_argument("--skip-group", action="store_true", help="Skip group-level")
    args = parser.parse_args()

    sub_args = ["--subject", args.subject] if args.subject else []

    print("=" * 60)
    print("  CUSTOM ANALYSIS PIPELINE")
    print("  (runs after MNE-BIDS-Pipeline preprocessing)")
    print("=" * 60)

    # Step 1: Extract band power (alpha/gamma)
    run_script("extract_band_power.py", sub_args)

    # Step 2: Retinotopy condition analysis
    run_script("condition_analysis.py", sub_args)

    # Step 3: Orientation tuning analysis
    run_script("orientation_tuning.py", sub_args)

    if not args.skip_group:
        # Step 4: Retinotopy model fitting (group-level)
        run_script("retinotopy_model_fit.py")

        # Step 5: Group statistics
        run_script("group_statistics.py")

    print("\n" + "=" * 60)
    print("  ALL CUSTOM ANALYSES COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
