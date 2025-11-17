import mne

raw = mne.io.read_raw_brainvision(
    "sub-01/ses-01/eeg/sub-01_ses-01_task-visual_eeg.vhdr",
    preload=True,
)

ica = mne.preprocessing.read_ica("outputs/sub-01/sub-01_ses-01_task-visual_eeg-ica.fif")
ica.apply(raw)
ica.plot_components()
print(ica.exclude)
