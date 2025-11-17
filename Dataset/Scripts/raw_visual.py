import mne
from pathlib import Path

sub = "sub-01_ses-01_task-visual_eeg"
vhdr_path = "sub-01/ses-01/eeg/sub-01_ses-01_task-visual_eeg.vhdr"
out_dir = Path("outputs/sub-01")

def main():
    # Load raw + ICA
    raw = mne.io.read_raw_brainvision(vhdr_path, preload=True)
    ica = mne.preprocessing.read_ica(out_dir / f"{sub}-ica.fif")

    # Apply ICA
    clean_raw = ica.apply(raw.copy())

    # Pick only EEG channels (drop photosensor / optical / ecg / resp)
    picks_eeg = mne.pick_types(clean_raw.info, eeg=True)
    print("EEG channels:", [clean_raw.ch_names[p] for p in picks_eeg])

    # Plot a 10-second window with reasonable EEG scaling (~20 µV)
    fig = clean_raw.plot(
        picks=picks_eeg,
        n_channels=32,          # how many EEG channels to show at once
        start=100.0,            # starting time in seconds; change as you like
        duration=10.0,          # window length in seconds
        scalings=dict(eeg=20e-6),  # 20 µV
        block=True,
    )

    # Save as PNG for your report
    out_png = out_dir / f"{sub}-raw_eeg_10s.png"
    fig.savefig(out_png, dpi=300)
    print("Saved:", out_png)

if __name__ == "__main__":
    main()
