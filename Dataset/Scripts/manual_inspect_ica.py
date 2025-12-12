import mne
from pathlib import Path
import matplotlib


sub = "sub-01"

# script is: eeg_visual_simulation_lac/Dataset/Scripts/<this_script>.py
script_path = Path(__file__).resolve()

# go up: Scripts -> Dataset -> eeg_visual_simulation_lac -> (repo root)
repo_root = script_path.parents[3]

bids_root = repo_root / "ds006547"
vhdr_path = bids_root / sub / "ses-01" / "eeg" / f"{sub}_ses-01_task-visual_eeg.vhdr"

# outputs are in: eeg_visual_simulation_lac/Dataset/outputs/sub-01  (from your screenshot)
out_dir = repo_root / "eeg_visual_simulation_lac" / "Dataset" / "outputs" / sub
out_dir.mkdir(parents=True, exist_ok=True)

raw = mne.io.read_raw_brainvision(vhdr_path, preload=True)

ica_path = out_dir / f"{sub}_ses-01_task-visual_eeg-ica.fif"
ica = mne.preprocessing.read_ica(ica_path)

figs = ica.plot_components(show=False)

if isinstance(figs, list):
    for i, f in enumerate(figs):
        f.savefig(out_dir / f"{sub}-ica_components_{i}.png", dpi=300)
else:
    figs.savefig(out_dir / f"{sub}-ica_components.png", dpi=300)
