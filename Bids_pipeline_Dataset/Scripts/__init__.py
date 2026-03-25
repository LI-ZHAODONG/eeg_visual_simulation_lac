"""
Custom analysis scripts for the Visual EEG Study.

These scripts run AFTER MNE-BIDS-Pipeline has produced cleaned epochs.
They implement the project-specific analyses that the pipeline doesn't cover:

1. extract_band_power.py  — Alpha/gamma Hilbert power (task − baseline)
2. condition_analysis.py  — Retinotopy spatial tuning summaries
3. orientation_tuning.py  — Orientation selectivity analysis
4. retinotopy_model_fit.py — Linear vs divisive normalization models
5. group_statistics.py    — Group-level aggregation and stats
6. run_all.py             — Run all custom analyses in sequence
"""
