import numpy as np
import mne
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    scripts_dir = Path(__file__).resolve().parent
    output_root = scripts_dir.parent / "outputs"
    
    orient_triggers = list(range(41, 57)) # 16 orientations
    accum_gamma = {t: [] for t in orient_triggers}
    accum_alpha = {t: [] for t in orient_triggers}
    
    subjects = sorted([d for d in output_root.iterdir() if d.is_dir() and d.name.startswith("sub-")])
    info = None
    
    for sub_dir in subjects:
        alpha_npy = list(sub_dir.glob("*-alpha_diff.npy"))
        gamma_npy = list(sub_dir.glob("*-gamma_diff.npy"))
        fif_files = list(sub_dir.glob("*-final-epo.fif"))
        
        if not (alpha_npy and gamma_npy and fif_files): continue
            
        try:
            epochs = mne.read_epochs(fif_files[0], preload=False, verbose=False)
            if info is None: info = epochs.info
            events = epochs.events[:, 2]
            alpha_data = np.load(alpha_npy[0])
            gamma_data = np.load(gamma_npy[0])
            
            for t in orient_triggers:
                mask = (events == t)
                if np.any(mask):
                    accum_alpha[t].append(alpha_data[mask].mean(axis=0))
                    accum_gamma[t].append(gamma_data[mask].mean(axis=0))
        except: continue

    # Average over subjects then average over posterior channels
    vis_channels = [ch for ch in ["Oz", "O1", "O2", "POz", "PO3", "PO4"] if ch in info.ch_names]
    vis_picks = mne.pick_channels(info.ch_names, vis_channels)
    
    angles = np.linspace(0, 337.5, 16)
    gamma_curve = []
    alpha_curve = []
    
    for t in orient_triggers:
        if not accum_gamma[t]:
            gamma_curve.append(0)
            alpha_curve.append(0)
            continue
        ga_gamma = np.mean(np.array(accum_gamma[t]), axis=0)
        ga_alpha = np.mean(np.array(accum_alpha[t]), axis=0)
        gamma_curve.append(ga_gamma[vis_picks].mean())
        alpha_curve.append(ga_alpha[vis_picks].mean())
        
    plt.figure(figsize=(10, 5))
    plt.subplot(1, 2, 1)
    plt.plot(angles, gamma_curve, 'ro-')
    plt.title("Gamma Orientation Tuning (Posterior)")
    plt.xlabel("Angle (Deg)")
    plt.ylabel("Power Diff (|Task| - |Base|)")
    
    plt.subplot(1, 2, 2)
    plt.plot(angles, alpha_curve, 'bo-')
    plt.title("Alpha Orientation Tuning (Posterior)")
    plt.xlabel("Angle (Deg)")
    
    plt.tight_layout()
    plt.savefig(output_root / "Orientation_Tuning_Curves.png")
    plt.close()
    
    # Also save one big grid of topomaps
    fig, axes = plt.subplots(4, 4, figsize=(15, 15))
    axes = axes.flatten()
    eeg_picks = mne.pick_types(info, eeg=True)
    info_eeg = mne.pick_info(info, eeg_picks)
    for i, t in enumerate(orient_triggers):
        if not accum_gamma[t]: continue
        ga_data = np.mean(np.array(accum_gamma[t]), axis=0)[eeg_picks]
        vmax = np.percentile(np.abs(ga_data), 95)
        mne.viz.plot_topomap(ga_data, info_eeg, axes=axes[i], show=False, cmap="RdBu_r", vlim=(-vmax, vmax))
        axes[i].set_title(f"{angles[i]}°")
    plt.savefig(output_root / "Orientation_Gamma_Grid.png")
    plt.close()

if __name__ == "__main__":
    main()
