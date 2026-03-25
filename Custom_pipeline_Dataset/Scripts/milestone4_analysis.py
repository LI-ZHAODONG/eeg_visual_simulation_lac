# milestone4_analysis.py
import numpy as np
import mne
from pathlib import Path
import matplotlib
matplotlib.use("Agg")


def pick_best_channel(ch_names):
    for ch in ["Oz", "O1", "O2", "Pz", "Cz"]:
        if ch in ch_names:
            return ch
    return ch_names[0]


def main():
    # ---- Paths (robust) ----
    script_dir = Path(__file__).resolve().parent          # .../Custom_pipeline_Dataset/Scripts
    project_root = script_dir.parents[1]                  # .../eeg_visual_simulation_lac
    out_dir = project_root / "Custom_pipeline_Dataset" / "outputs" / "sub-01"
    out_dir.mkdir(parents=True, exist_ok=True)

    epochs_path = out_dir / "sub-01_ses-01_task-visual_eeg-final-epo.fif"
    print("Epochs path:", epochs_path)
    print("Exists:", epochs_path.exists())
    if not epochs_path.exists():
        raise FileNotFoundError(epochs_path)

    # ---- Load epochs ----
    epochs = mne.read_epochs(epochs_path, preload=True)
    print("event_id:", epochs.event_id)
    print("Total epochs:", len(epochs))

    # ---- Define conditions by EVENT CODES (robust; avoids string query issues) ----
    condA_codes = list(range(1, 21))     # 1..20 from the paper figures
    condB_codes = list(range(41, 57))    # 41..56

    mask_A = np.isin(epochs.events[:, 2], condA_codes)
    mask_B = np.isin(epochs.events[:, 2], condB_codes)

    epochs_A = epochs[mask_A]
    epochs_B = epochs[mask_B]

    print("Cond A epochs:", len(epochs_A))
    print("Cond B epochs:", len(epochs_B))
    print("Unique codes A:", sorted(set(epochs_A.events[:, 2])))
    print("Unique codes B:", sorted(set(epochs_B.events[:, 2])))

    if len(epochs_A) == 0 or len(epochs_B) == 0:
        raise RuntimeError("One of the conditions has 0 epochs. Check event codes.")

    # ---- Average (ERP) ----
    evoked_A = epochs_A.average()
    evoked_B = epochs_B.average()

    # Choose a good visual channel
    pick_ch = pick_best_channel(evoked_A.ch_names)
    print("Using channel for ERP overlay:", pick_ch)

    # ---- 1) Butterfly plots ----
    figA = evoked_A.plot(spatial_colors=True, show=False)
    figA.savefig(out_dir / "m4-butterfly_A.png", dpi=300)

    figB = evoked_B.plot(spatial_colors=True, show=False)
    figB.savefig(out_dir / "m4-butterfly_B.png", dpi=300)

    # ---- 2) ERP overlay at chosen channel ----
    fig_cmp = mne.viz.plot_compare_evokeds(
    {"A(1-20)": evoked_A, "B(41-56)": evoked_B},
    picks=[pick_ch],
    show=False,
    )

    # Some MNE versions return a list of figures
    if isinstance(fig_cmp, list):
        for i, f in enumerate(fig_cmp):
            f.savefig(out_dir / f"m4-erp_compare_{pick_ch}_{i}.png", dpi=300)
    else:
        fig_cmp.savefig(out_dir / f"m4-erp_compare_{pick_ch}.png", dpi=300)


    # ---- 3) Difference ERP (A - B) ----
    evoked_diff = mne.combine_evoked([evoked_A, evoked_B], weights=[1, -1])
    fig_diff = evoked_diff.plot(picks=[pick_ch], show=False)
    fig_diff.savefig(out_dir / f"m4-erp_diff_{pick_ch}.png", dpi=300)

    # ---- 4) Topomaps (time windows) ----
    windows = [(0.10, 0.20), (0.20, 0.30), (0.30, 0.40)]
    for t0, t1 in windows:
        tmid = (t0 + t1) / 2
        avg = (t1 - t0)

        fig_topo_A = evoked_A.plot_topomap(times=[tmid], average=avg, show=False)
        fig_topo_A.savefig(out_dir / f"m4-topo_A_{t0:.2f}-{t1:.2f}.png", dpi=300)

        fig_topo_B = evoked_B.plot_topomap(times=[tmid], average=avg, show=False)
        fig_topo_B.savefig(out_dir / f"m4-topo_B_{t0:.2f}-{t1:.2f}.png", dpi=300)

        fig_topo_D = evoked_diff.plot_topomap(times=[tmid], average=avg, show=False)
        fig_topo_D.savefig(out_dir / f"m4-topo_diff_{t0:.2f}-{t1:.2f}.png", dpi=300)

    # ---- Save summary text ----
    summary = out_dir / "m4-results-summary.txt"
    with open(summary, "w") as f:
        f.write("Milestone 4 – Subject 01 summary\n")
        f.write("--------------------------------\n")
        f.write(f"Epochs file: {epochs_path.name}\n")
        f.write(f"Total epochs: {len(epochs)}\n")
        f.write(f"Condition A (codes 1–20): {len(epochs_A)} epochs\n")
        f.write(f"Condition B (codes 41–56): {len(epochs_B)} epochs\n")
        f.write(f"ERP overlay channel: {pick_ch}\n")
        f.write("Outputs:\n")
        f.write("  m4-butterfly_A.png\n")
        f.write("  m4-butterfly_B.png\n")
        f.write(f"  m4-erp_compare_{pick_ch}.png\n")
        f.write(f"  m4-erp_diff_{pick_ch}.png\n")
        f.write("  m4-topo_A_*.png / m4-topo_B_*.png / m4-topo_diff_*.png\n")

    print("Saved Milestone 4 outputs into:", out_dir)
    print("Also wrote:", summary)


if __name__ == "__main__":
    main()
