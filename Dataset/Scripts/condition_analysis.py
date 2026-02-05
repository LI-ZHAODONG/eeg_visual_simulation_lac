import numpy as np
import mne
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    # Paths
    scripts_dir = Path(__file__).resolve().parent
    dataset_root = scripts_dir.parent
    output_root = dataset_root / "outputs"
    
    # Categories to inspect
    # Trigger mapping based on BrainVision annotations observed
    categories = {
        'Full Field': [1],
        'Left Hemifield': [2],
        'Right Hemifield': [3],
        'Upper Hemifield': [4],
        'Lower Hemifield': [5],
        'Fovea': [18],
        'Periphery': [19],
        'Vertical (0°)': [41],
        'Horizontal (90°)': [45],
        'Oblique (45°)': [43]
    }
    
    # Storage
    accum_alpha = {name: [] for name in categories}
    accum_gamma = {name: [] for name in categories}
    
    subjects = sorted([d for d in output_root.iterdir() if d.is_dir() and d.name.startswith("sub-")])
    print(f"Aggregating condition-wise results from {len(subjects)} subjects (Optimized)...")
    
    info = None
    
    for sub_dir in subjects:
        sub_name = sub_dir.name
        
        # 1. Load trial-level results
        alpha_npy = list(sub_dir.glob("*-alpha_diff.npy"))
        gamma_npy = list(sub_dir.glob("*-gamma_diff.npy"))
        fif_files = list(sub_dir.glob("*-final-epo.fif"))
        
        if not (alpha_npy and gamma_npy and fif_files):
            continue
            
        try:
            # Metadata only
            epochs = mne.read_epochs(fif_files[0], preload=False, verbose=False)
            if info is None: info = epochs.info
            
            # Events: (n_epochs, 3). Event code is 3rd column
            events = epochs.events[:, 2]
            
            alpha_data = np.load(alpha_npy[0]) # (n_epochs, n_channels)
            gamma_data = np.load(gamma_npy[0])
            
            if len(events) != len(alpha_data):
                print(f"  Warning: {sub_name} length mismatch! Skipping.")
                continue
                
            for cat_name, triggers in categories.items():
                # Indices for this condition
                mask = np.isin(events, triggers)
                if np.any(mask):
                    accum_alpha[cat_name].append(alpha_data[mask].mean(axis=0))
                    accum_gamma[cat_name].append(gamma_data[mask].mean(axis=0))

        except Exception as e:
            print(f"  Error: {e}")

    # Visualization
    print("\nGenerating Topographic Maps...")
    eeg_picks = mne.pick_types(info, eeg=True)
    info_eeg = mne.pick_info(info, eeg_picks)
    
    for band_name, accum_dict in [('Alpha', accum_alpha), ('Gamma', accum_gamma)]:
        fig, axes = plt.subplots(2, 5, figsize=(20, 8))
        axes = axes.flatten()
        
        for i, (cat_name, data_list) in enumerate(accum_dict.items()):
            if not data_list:
                axes[i].axis('off')
                continue
            ga_data = np.mean(np.array(data_list), axis=0)[eeg_picks]
            
            # Scale for visibility
            vmax = np.percentile(np.abs(ga_data), 95)
            mne.viz.plot_topomap(ga_data, info_eeg, axes=axes[i], show=False, cmap="RdBu_r", vlim=(-vmax, vmax))
            axes[i].set_title(f"{cat_name}\n({band_name})")
            
        plt.tight_layout()
        plt.savefig(output_root / f"Condition_Wise_{band_name}_Topomaps.png")
        plt.close()

    print(f"Done! Created Condition_Wise_Alpha_Topomaps.png and Condition_Wise_Gamma_Topomaps.png in {output_root}")

if __name__ == "__main__":
    main()
