#!/usr/bin/env python3
"""
Launch MNE-BIDS-Pipeline for the Visual EEG Study (ds006547).

This is a convenience wrapper around the CLI.  You can also run directly:

    mne_bids_pipeline --config config.py --steps preprocessing,sensor

Usage
-----
    # Preprocess all subjects (filtering, ICA, epoching)
    python run_pipeline.py --steps preprocessing

    # Preprocess one subject for testing
    python run_pipeline.py --steps preprocessing --subject 01

    # Full pipeline (preprocessing + sensor-level + TFR)
    python run_pipeline.py --steps preprocessing,sensor

    # Generate HTML reports
    python run_pipeline.py --steps preprocessing,sensor --report
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run MNE-BIDS-Pipeline for Visual EEG Study"
    )
    parser.add_argument(
        "--steps",
        default="preprocessing",
        help=(
            "Pipeline steps to run. Options: preprocessing, sensor, source. "
            "Comma-separated for multiple (default: preprocessing)"
        ),
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="Process only this subject (e.g., 01). Default: all subjects.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate HTML reports after processing.",
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=4,
        help="Number of parallel jobs (default: 4).",
    )
    args = parser.parse_args()

    config_path = Path(__file__).parent / "config.py"
    if not config_path.exists():
        print(f"ERROR: config.py not found at {config_path}")
        sys.exit(1)

    # Build command — use the installed CLI entry point
    cmd = [
        "mne_bids_pipeline",
        "--config", str(config_path),
        "--steps", args.steps,
        "--n_jobs", str(args.n_jobs),
    ]

    if args.subject:
        cmd.extend(["--subject", args.subject])

    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\nPipeline exited with code {result.returncode}")
        sys.exit(result.returncode)

    # Generate reports if requested
    if args.report:
        report_cmd = cmd.copy()
        # Add report generation flag
        report_cmd.append("--gen-report")
        print("\n" + "=" * 60)
        print("Generating HTML reports...")
        print("=" * 60)
        subprocess.run(report_cmd)

    print("\nDone!")


if __name__ == "__main__":
    main()
