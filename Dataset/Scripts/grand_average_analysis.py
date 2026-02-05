import numpy as np
import mne
import matplotlib.pyplot as plt
from pathlib import Path

def main():
    # Paths
    scripts_dir = Path(__file__).resolve().parent
    dataset_root = scripts_dir.parent
    output_root = dataset_root / "outputs"
    
    alpha_all = []
    gamma_all = []
    evokeds = []
    psds_task = []
    psds_base = []
    
    subjects = sorted([d for d in output_root.iterdir() if d.is_dir() and d.name.startswith("sub-")])
    print(f"Aggregating results from {len(subjects)} subjects...")
    
    info = None
    freqs_task = None
    freqs_base = None
    
    for sub_dir in subjects:
        sub_name = sub_dir.name
        print(f" Processing {sub_name}...")
        
        # 1. Topomap data (npy)
        alpha_files = list(sub_dir.glob("*-alpha_diff.npy"))
        gamma_files = list(sub_dir.glob("*-gamma_diff.npy"))
        
        if alpha_files and gamma_files:
            alpha_sub = np.load(alpha_files[0]).mean(axis=0)
            gamma_sub = np.load(gamma_files[0]).mean(axis=0)
            alpha_all.append(alpha_sub)
            gamma_all.append(gamma_sub)
            
        # 2. ERP & PSD data (FIF)
        fif_files = list(sub_dir.glob("*-final-epo.fif"))
        if fif_files:
            try:
                epochs = mne.read_epochs(fif_files[0], preload=True, verbose=False)
                
                if info is None:
                    info = epochs.info
                
                # ERP
                evokeds.append(epochs.average())
                
                # PSD
                psd_t = epochs.compute_psd(tmin=0.5, tmax=2.5, fmin=4, fmax=100, verbose=False)
                psds_task.append(psd_t.get_data().mean(axis=0)) 
                if freqs_task is None: freqs_task = psd_t.freqs
                
                psd_b = epochs.compute_psd(tmin=-0.5, tmax=0, fmin=4, fmax=100, verbose=False)
                psds_base.append(psd_b.get_data().mean(axis=0))
                if freqs_base is None: freqs_base = psd_b.freqs
                
                del epochs
            except Exception as e:
                print(f"  Error loading {sub_name}: {e}")

    if not alpha_all or not evokeds:
        print("No valid data found.")
        return

    print(f"\nComputing Grand Averages...")
    
    # --- Topomaps ---
    grand_alpha = np.mean(np.array(alpha_all), axis=0)
    grand_gamma = np.mean(np.array(gamma_all), axis=0)
    eeg_picks = mne.pick_types(info, eeg=True, exclude=[])
    grand_alpha_eeg = grand_alpha[eeg_picks]
    grand_gamma_eeg = grand_gamma[eeg_picks]
    info_eeg = mne.pick_info(info, eeg_picks)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    mne.viz.plot_topomap(grand_alpha_eeg, info_eeg, axes=axes[0], show=False, cmap="RdBu_r")
    axes[0].set_title("Grand Average Alpha (8-12 Hz)\n(Suppression)")
    mne.viz.plot_topomap(grand_gamma_eeg, info_eeg, axes=axes[1], show=False, cmap="RdBu_r")
    axes[1].set_title("Grand Average Gamma (40-80 Hz)\n(Activation)")
    plt.savefig(output_root / "GA_topomaps.png")
    plt.close()

    # --- ERP ---
    ga_evoked = mne.grand_average(evokeds)
    fig_erp = ga_evoked.plot(spatial_colors=True, show=False)
    fig_erp.savefig(output_root / "GA_butterfly.png")
    plt.close()

    if "Oz" in ga_evoked.ch_names:
        mne.viz.plot_compare_evokeds({"Grand Average": ga_evoked}, picks="Oz", show=False)[0].savefig(output_root / "GA_erp_Oz.png")
        plt.close()

    # --- PSD ---
    ga_psd_task = np.mean(np.array(psds_task), axis=0)
    ga_psd_base = np.mean(np.array(psds_base), axis=0)
    vis_channels = [ch for ch in ["Oz", "O1", "O2", "POz", "PO3", "PO4"] if ch in ga_evoked.ch_names]
    vis_picks = mne.pick_channels(ga_evoked.ch_names, vis_channels)
    
    plt.figure(figsize=(10, 6))
    plt.plot(freqs_task, 10 * np.log10(ga_psd_task[vis_picks].mean(axis=0)), label="Stimulus", color='red', linewidth=2)
    plt.plot(freqs_base, 10 * np.log10(ga_psd_base[vis_picks].mean(axis=0)), label="Baseline", color='black', linestyle='--', alpha=0.7)
    plt.title("Grand Average PSD (Posterior Channels)")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Power (dB)")
    plt.legend()
    plt.grid(True)
    plt.savefig(output_root / "GA_psd.png")
    plt.close()

    print(f"\nDone! saved GA_topomaps.png, GA_butterfly.png, GA_erp_Oz.png, GA_psd.png to {output_root}")

if __name__ == "__main__":
    main()
