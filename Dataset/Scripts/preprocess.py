import argparse
from pathlib import Path

import numpy as np
import mne
from mne.preprocessing import ICA


def detect_bad_channels_ssd(raw):
    """Detect bad channels with SSD (10–100 Hz) and interpolate them."""
    raw_filt = raw.copy().filter(10, 100, fir_design="firwin")
    data = raw_filt.get_data()  # (n_channels, n_samples)

    # Sum of squared differences across time
    ssd = np.sum(np.diff(data, axis=1) ** 2, axis=1)
    z = (ssd - ssd.mean()) / ssd.std()

    bads = [raw.ch_names[i] for i, zi in enumerate(z) if zi > 1.0]
    print(f"Detected bad channels (z > 1): {bads}")

    raw.info["bads"] = bads
    raw.interpolate_bads(reset_bads=True)
    return raw


def run_ica(raw, n_components=60):
    """Prepare data for ICA (1–100 Hz, 200 Hz resample) and fit Picard ICA."""
    # Filter 1–100 Hz for ICA
    ica_raw = raw.copy().filter(1, 100, fir_design="firwin")

    # Resample to 200 Hz to reduce computational load
    ica_raw.resample(200)

    # Get events from annotations
    events, event_id = mne.events_from_annotations(ica_raw)
    print(f"Found {len(events)} events, event_id mapping: {event_id}")

    # Epochs for ICA training: -1.0 to 4.0 s
    epochs = mne.Epochs(
        ica_raw,
        events,
        event_id=None,   # use all events
        tmin=-1.0,
        tmax=4.0,
        baseline=None,
        preload=True,
    )
    print(f"Epochs shape for ICA: {epochs.get_data().shape}")

    ica = ICA(
        method="picard",
        n_components=n_components,
        max_iter=500,
        fit_params=dict(extended=True),
        random_state=97,
    )
    ica.fit(epochs)
    return ica


def apply_ica_and_epoch(raw, ica, good_components=None, bad_components=None):
    """
    Apply ICA. 
    If good_components is provided, reconstruct signal using ONLY those.
    Otherwise, exclude bad_components.
    Then create final epochs (-0.5 to 3.5 s, baseline -0.5–0).
    """
    if good_components is not None:
        print(f"Reconstructing signal using ONLY ICA components: {good_components}")
        # To keep only 'good', we exclude everything EXCEPT those.
        all_inds = list(range(ica.n_components_))
        exclude_inds = [i for i in all_inds if i not in good_components]
        ica.exclude = exclude_inds
    elif bad_components is not None:
        print(f"Excluding ICA components: {bad_components}")
        ica.exclude = bad_components
    
    clean_raw = ica.apply(raw.copy())

    # Final epochs for analysis
    events, event_id = mne.events_from_annotations(clean_raw)

    final_epochs = mne.Epochs(
        clean_raw,
        events,
        event_id=None,
        tmin=-0.6, # Extra buffer for Hilbert/cropping
        tmax=3.6,
        baseline=(-0.5, 0.0), # Apply baseline correction
        preload=True,
    )
    # Set the actual analysis window
    final_epochs.crop(tmin=-0.5, tmax=3.5)
    
    print(f"Final epochs shape: {final_epochs.get_data().shape}")
    return final_epochs


def reject_outliers_broadband(epochs):
    """
    Reject trials with high broadband gamma (80–100 Hz) activity (z > 4).
    As per paper: "To isolate trials corrupted by broadband muscular or ocular 
    artifacts, we first extracted log power in the 80–100 Hz band... 
    Trials with |z| > 4 were excluded."
    """
    print("Performing 80-100 Hz outlier rejection...")
    # Ensure data is loaded
    epochs.load_data()
    
    from mne.filter import filter_data
    sfreq = epochs.info['sfreq']
    
    # Pick only EEG channels
    eeg_picks = mne.pick_types(epochs.info, eeg=True, exclude='bads')
    data = epochs.get_data(picks=eeg_picks, tmin=0, tmax=3) # (n_epochs, n_channels, n_times)
    
    # Force contiguous copy to avoid MNE/NumPy AttributeError during x.shape = ...
    data_c = np.ascontiguousarray(data.copy())
    
    # Filter for 80-100 Hz
    filtered = filter_data(data_c, sfreq, 80, 100, fir_design="firwin", verbose=False)
    
    # Compute power (mean square) per trial
    max_power = np.max(np.mean(filtered**2, axis=1), axis=1) 
    log_power = np.log10(max_power + 1e-10)
    
    z = (log_power - np.mean(log_power)) / (np.std(log_power) + 1e-10)
    keep_mask = np.abs(z) <= 4
    
    n_rejected = len(epochs) - np.sum(keep_mask)
    if n_rejected > 0:
        print(f"  Rejected {n_rejected} epochs with |z| > 4 in 80-100 Hz band.")
        epochs = epochs[keep_mask]
    else:
        print("  No epochs rejected based on 80-100 Hz criteria.")
    
    return epochs


def compute_band_amplitude(final_epochs, fmin, fmax, label):
    """
    Filter into band and compute |task| - |baseline| analytic amplitude per channel.
    Uses Hilbert transform as per paper's 'absolute analytic amplitude'.
    """
    print(f"Computing {label} power ({fmin}-{fmax} Hz)...")
    # Ensure data is loaded
    final_epochs.load_data()
    
    from mne.filter import filter_data
    from scipy.signal import hilbert
    
    sfreq = final_epochs.info['sfreq']
    data = final_epochs.get_data() # (n_epochs, n_channels, n_times)
    
    # Create a contiguous copy to avoid MNE _prep_for_filtering errors
    data_c = np.ascontiguousarray(data.copy())
    
    # Apply band-pass filter
    filtered = filter_data(data_c, sfreq, fmin, fmax, fir_design="firwin", verbose=False)
    
    # Apply Hilbert transform to get analytic signal envelope
    print(f"  Applying Hilbert envelope...")
    # Hilbert along the time axis (last axis)
    analytic = hilbert(filtered, axis=-1)
    envelope = np.abs(analytic)

    times = final_epochs.times

    # Indices for baseline (-0.5–0) and task (0.5–2.5) as per paper intent
    # Note: Stimulus starts at 0. Paper often evaluates specific windows.
    baseline_mask = (times >= -0.5) & (times <= 0.0)
    task_mask = (times >= 0.0) & (times <= 3.0)
    
    # Average envelope over time windows
    baseline_mean = envelope[:, :, baseline_mask].mean(axis=2) # (n_epochs, n_channels)
    task_mean = envelope[:, :, task_mask].mean(axis=2)

    diff = task_mean - baseline_mean  # Analytic amplitude difference
    print(f"  {label} band: computed analytic amplitude differences.")
    return diff  # shape: (n_epochs, n_channels)


def find_visual_components(ica, raw, n_keep=5):
    """
    Automated heuristic to find 'visual' components.
    Looks for components with high weights on posterior electrodes 
    and low weights on frontal ones.
    """
    print(f"Automatically searching for top {n_keep} visual components...")
    
    # Normalize channel names to handle Oz vs OZ vs oz
    ch_names_upper = [ch.upper() for ch in raw.ch_names]
    
    post_targets = ["OZ", "O1", "O2", "POZ", "PO3", "PO4"]
    front_targets = ["FP1", "FP2", "FZ", "F3", "F4", "F7", "F8"]
    
    post_channels = [raw.ch_names[i] for i, ch in enumerate(ch_names_upper) if ch in post_targets]
    front_channels = [raw.ch_names[i] for i, ch in enumerate(ch_names_upper) if ch in front_targets]

    if not post_channels:
        print("  WARNING: No posterior channels found! Using fallback (first n components).")
        return list(range(n_keep))
        
    post_picks = mne.pick_channels(raw.ch_names, post_channels)
    front_picks = mne.pick_channels(raw.ch_names, front_channels)
    
    # Get spatial maps (n_channels, n_components)
    maps = ica.get_components() 
    
    # Score = Power in back - Power in front
    post_score = np.abs(maps[post_picks, :]).mean(axis=0)
    front_score = np.abs(maps[front_picks, :]).mean(axis=0)
    
    scores = post_score - (0.5 * front_score) # Penalize frontal activity
    
    best_inds = np.argsort(scores)[-n_keep:]
    return sorted(best_inds.tolist())

def main(vhdr_path, out_dir):
    vhdr_path = Path(vhdr_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading BrainVision file: {vhdr_path}")
    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True)

    # 1) Bad channel detection + interpolation
    raw = detect_bad_channels_ssd(raw)

    # 2) Filter data (1–100 Hz) and remove line noise (60 Hz)
    print("Filtering data 1–100 Hz and removing 60 Hz line noise...")
    raw.filter(1.0, 100.0, fir_design="firwin")
    raw.notch_filter(60.0)

    # 3) Run ICA
    ica = run_ica(raw)

    # 4) Automatically find eye-related components
    # Try to find EOG channels explicitly
    eog_like = [ch for ch in raw.ch_names if "EOG" in ch.upper()]

    # If there is no dedicated EOG channel, fall back to frontal EEG (Fp, AF)
    if not eog_like:
        eog_like = [
            ch for ch in raw.ch_names
            if ch.upper().startswith("FP") or ch.upper().startswith("AF")
        ]

    if eog_like:
        print("Using these channels as EOG reference:", eog_like)
        eog_inds, eog_scores = ica.find_bads_eog(raw, ch_name=eog_like)
    else:
        print("No EOG or frontal channels found, skipping auto EOG detection.")
        eog_inds, eog_scores = [], []

    print("Auto-detected EOG components:", eog_inds)

    # RECONSTRUCTION STRATEGY: 
    # For Subject 01 we know the best ones, for others we use the heuristic.
    # Check filename for sub-01 (more robust than path string)
    if "sub-01" in vhdr_path.name.lower():
        print("Subject 01 detected: Using manual ICA component list [9, 11, 14]")
        good_components = [9, 11, 14] 
    else:
        good_components = find_visual_components(ica, raw, n_keep=4)
        print(f"Using automated visual components: {good_components}")
        
    final_epochs = apply_ica_and_epoch(raw, ica, good_components=good_components)
    
    # 5) 80-100 Hz Outlier Rejection
    final_epochs = reject_outliers_broadband(final_epochs)
    
    # Save final epochs
    final_epochs_path = out_dir / f"{vhdr_path.stem}-final-epo.fif"
    print(f"Saving final epochs to {final_epochs_path}")
    final_epochs.save(final_epochs_path, overwrite=True)

    # ===== Milestone 3 plots =====
    evoked = final_epochs.average()

    # Butterfly plot (all channels)
    fig_b = evoked.plot(spatial_colors=True, show=False)
    fig_b.savefig(out_dir / f"{vhdr_path.stem}-butterfly.png", dpi=300)

    # Robust channel selection
    for ch in ["Oz", "O1", "O2", "Pz", "Cz"]:
        if ch in evoked.ch_names:
            pick_ch = ch
            break
    else:
        pick_ch = evoked.ch_names[0]
    
    fig_e = evoked.plot(picks=[pick_ch], show=False)
    fig_e.savefig(out_dir / f"{vhdr_path.stem}-erp_{pick_ch}.png", dpi=300)

    print("Using channel:", pick_ch)


    # 6) Save ICA solution (with exclude list set)
    ica_fname = out_dir / f"{vhdr_path.stem}-ica.fif"
    print(f"Saving ICA solution to {ica_fname}")
    ica.save(ica_fname, overwrite=True)

    # 7) Compute alpha and gamma amplitude differences
    # Standardize bands: Alpha 8-12, Gamma 40-80
    alpha_diff = compute_band_amplitude(final_epochs, 8, 12, label="Alpha")
    gamma_diff = compute_band_amplitude(final_epochs, 40, 80, label="Gamma")

    # 8) Save results
    np.save(out_dir / f"{vhdr_path.stem}-alpha_diff.npy", alpha_diff)
    np.save(out_dir / f"{vhdr_path.stem}-gamma_diff.npy", gamma_diff)

    print(f"Saved alpha/gamma per-epoch per-channel arrays for {vhdr_path.stem}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--vhdr",
        required=True,
        help="Path to BrainVision .vhdr file (e.g., sub-01/ses-01/eeg/sub-01_ses-01_task-visual_eeg.vhdr)",
    )
    parser.add_argument(
        "--out_dir",
        default="outputs/preproc",
        help="Directory where preprocessed outputs will be saved",
    )
    args = parser.parse_args()
    main(args.vhdr, args.out_dir)
