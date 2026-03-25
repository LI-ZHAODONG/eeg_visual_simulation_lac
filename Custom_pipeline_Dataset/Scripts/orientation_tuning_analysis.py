import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import ttest_ind

matplotlib.use("Agg")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_npz_dict(path):
    data = np.load(path)
    return {key: data[key] for key in data.files}


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def maybe_load_json(path):
    if path is None or not Path(path).exists():
        return None
    return load_json(Path(path))


def choose_channel(ch_names):
    for ch in ["Oz", "O1", "O2", "POz", "Pz", "Cz"]:
        if ch in ch_names:
            return ch
    return ch_names[0]


def code_mean(code_map, code):
    key = str(code)
    return code_map.get(key)


def grouped_mean(code_map, codes, pick_idx):
    present = [str(code) for code in codes if str(code) in code_map]
    if not present:
        return None
    stacked = np.stack([code_map[code] for code in present], axis=0)
    return float(stacked.mean(axis=0)[pick_idx])


def grouped_trial_values(trial_matrix, event_codes, codes, pick_idx):
    mask = np.isin(event_codes, list(codes))
    if not mask.any():
        return np.array([])
    return trial_matrix[mask, pick_idx]


def plot_trigger_bars(trigger_rows, out_path):
    labels = [str(row["code"]) for row in trigger_rows]
    gamma = [row["gamma"] for row in trigger_rows]
    alpha = [row["alpha"] for row in trigger_rows]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].bar(labels, gamma, color="#e76f51")
    axes[0].set_title("Gamma Power by Orientation Trigger")
    axes[0].set_ylabel("Mean Power")
    axes[0].tick_params(axis="x", rotation=45)

    axes[1].bar(labels, alpha, color="#8ecae6")
    axes[1].set_title("Alpha Power by Orientation Trigger")
    axes[1].tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_group_bars(group_rows, out_path, title):
    labels = [row["label"] for row in group_rows]
    gamma = [row["gamma"] for row in group_rows]
    alpha = [row["alpha"] for row in group_rows]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(labels, gamma, color="#e76f51")
    axes[0].set_title(f"Gamma: {title}")
    axes[0].tick_params(axis="x", rotation=35)
    axes[1].bar(labels, alpha, color="#8ecae6")
    axes[1].set_title(f"Alpha: {title}")
    axes[1].tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_orientation_scatter(group_rows, out_path, title):
    alpha = np.array([row["alpha"] for row in group_rows], dtype=float)
    gamma = np.array([row["gamma"] for row in group_rows], dtype=float)
    labels = [row["label"] for row in group_rows]

    slope, intercept = np.polyfit(alpha, gamma, 1)
    corr = float(np.corrcoef(alpha, gamma)[0, 1])

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(alpha, gamma, color="#444444")
    ax.plot(np.sort(alpha), slope * np.sort(alpha) + intercept, "--", color="#1d3557")
    for x, y, label in zip(alpha, gamma, labels):
        ax.text(x, y, label, fontsize=8)
    ax.set_title(f"{title} (r = {corr:.2f})")
    ax.set_xlabel("Alpha Power")
    ax.set_ylabel("Gamma Power")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    return corr


def compute_pairwise_ttests(group_rows, trial_matrix, event_codes, pick_idx):
    n = len(group_rows)
    t_values = np.full((n, n), np.nan)
    p_values = np.full((n, n), np.nan)

    for i, row_i in enumerate(group_rows):
        vals_i = grouped_trial_values(trial_matrix, event_codes, row_i["codes"], pick_idx)
        for j, row_j in enumerate(group_rows):
            if j >= i:
                continue
            vals_j = grouped_trial_values(trial_matrix, event_codes, row_j["codes"], pick_idx)
            if len(vals_i) < 2 or len(vals_j) < 2:
                continue
            stat = ttest_ind(vals_i, vals_j, equal_var=False, nan_policy="omit")
            t_values[i, j] = stat.statistic
            p_values[i, j] = stat.pvalue

    return t_values, p_values


def plot_pairwise_heatmap(t_values, p_values, labels, out_path, title):
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(np.nan_to_num(t_values, nan=0.0), cmap="coolwarm", vmin=-5, vmax=5)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)
    ax.set_title(title)

    for i in range(len(labels)):
        for j in range(len(labels)):
            if np.isnan(p_values[i, j]):
                continue
            text = f"{p_values[i, j]:.3f}"
            if p_values[i, j] < 0.05:
                text += "*"
            ax.text(j, i, text, ha="center", va="center", fontsize=8, color="black")

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="t-value")
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Build paper-style orientation summaries from alpha/gamma condition outputs."
    )
    parser.add_argument("--alpha-by-condition", type=Path, required=True)
    parser.add_argument("--gamma-by-condition", type=Path, required=True)
    parser.add_argument("--band-power-summary", type=Path, required=True)
    parser.add_argument("--alpha-trial", type=Path, default=None)
    parser.add_argument("--gamma-trial", type=Path, default=None)
    parser.add_argument("--event-codes", type=Path, default=None)
    parser.add_argument("--ersp-stats-summary", type=Path, default=None)
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=Path(__file__).resolve().parent / "condition_mapping.json",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    alpha_map = load_npz_dict(args.alpha_by_condition.resolve())
    gamma_map = load_npz_dict(args.gamma_by_condition.resolve())
    summary_json = load_json(args.band_power_summary.resolve())
    mapping = load_json(args.mapping_json.resolve())

    out_dir = (args.out_dir or args.alpha_by_condition.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    recording = summary_json.get("recording")
    alpha_trial_path = args.alpha_trial
    gamma_trial_path = args.gamma_trial
    event_codes_path = args.event_codes
    ersp_stats_summary_path = args.ersp_stats_summary
    if recording is not None:
        if alpha_trial_path is None:
            candidate = out_dir / f"{recording}-alpha_trial_diff.npy"
            alpha_trial_path = candidate if candidate.exists() else None
        if gamma_trial_path is None:
            candidate = out_dir / f"{recording}-gamma_trial_diff.npy"
            gamma_trial_path = candidate if candidate.exists() else None
        if event_codes_path is None:
            candidate = out_dir / f"{recording}-event_codes.npy"
            event_codes_path = candidate if candidate.exists() else None
        if ersp_stats_summary_path is None:
            candidate = out_dir / "orientation_ersp_stats_summary.json"
            ersp_stats_summary_path = candidate if candidate.exists() else None

    ch_names = summary_json["ch_names"]
    pick_ch = choose_channel(ch_names)
    pick_idx = ch_names.index(pick_ch)

    trigger_rows = []
    for code in mapping["families"]["orientation"]["codes"]:
        alpha_vec = code_mean(alpha_map, code)
        gamma_vec = code_mean(gamma_map, code)
        if alpha_vec is None or gamma_vec is None:
            continue
        trigger_rows.append(
            {
                "code": code,
                "deg": mapping["orientation_code_degrees"][str(code)],
                "alpha": float(alpha_vec[pick_idx]),
                "gamma": float(gamma_vec[pick_idx]),
            }
        )

    orientation_group_names = [
        "orientation_cardinal_combined",
        "orientation_oblique_perfect_45",
        "orientation_oblique_vertical_pm_22_5",
        "orientation_oblique_horizontal_pm_22_5",
        "orientation_horizontal",
        "orientation_vertical",
    ]
    direction_group_names = [
        "leftward_motion",
        "rightward_motion",
        "upward_motion",
        "downward_motion",
    ]

    orientation_groups = []
    for name in orientation_group_names:
        codes = mapping["orientation_groups"][name]
        orientation_groups.append(
            {
                "label": name,
                "codes": codes,
                "alpha": grouped_mean(alpha_map, codes, pick_idx),
                "gamma": grouped_mean(gamma_map, codes, pick_idx),
            }
        )

    direction_groups = []
    for name in direction_group_names:
        codes = mapping["orientation_groups"][name]
        direction_groups.append(
            {
                "label": name.replace("_motion", ""),
                "codes": codes,
                "alpha": grouped_mean(alpha_map, codes, pick_idx),
                "gamma": grouped_mean(gamma_map, codes, pick_idx),
            }
        )

    trigger_bar_path = out_dir / "orientation_trigger_summary.png"
    orientation_group_path = out_dir / "orientation_group_summary.png"
    direction_group_path = out_dir / "direction_group_summary.png"
    orientation_scatter_path = out_dir / "orientation_alpha_gamma_scatter.png"
    direction_scatter_path = out_dir / "direction_alpha_gamma_scatter.png"
    orientation_alpha_t_path = out_dir / "orientation_alpha_ttests.png"
    orientation_gamma_t_path = out_dir / "orientation_gamma_ttests.png"
    direction_alpha_t_path = out_dir / "direction_alpha_ttests.png"
    direction_gamma_t_path = out_dir / "direction_gamma_ttests.png"

    plot_trigger_bars(trigger_rows, trigger_bar_path)
    plot_group_bars(orientation_groups, orientation_group_path, "Orientation Bins")
    plot_group_bars(direction_groups, direction_group_path, "Direction Bins")
    orientation_corr = plot_orientation_scatter(
        orientation_groups, orientation_scatter_path, "Alpha vs Gamma: Orientation"
    )
    direction_corr = plot_orientation_scatter(
        direction_groups, direction_scatter_path, "Alpha vs Gamma: Direction"
    )

    ttest_outputs = {}
    if alpha_trial_path is not None and gamma_trial_path is not None and event_codes_path is not None:
        alpha_trial = np.load(Path(alpha_trial_path).resolve())
        gamma_trial = np.load(Path(gamma_trial_path).resolve())
        event_codes = np.load(Path(event_codes_path).resolve())

        orientation_labels = [row["label"] for row in orientation_groups]
        direction_labels = [row["label"] for row in direction_groups]

        alpha_t, alpha_p = compute_pairwise_ttests(
            orientation_groups, alpha_trial, event_codes, pick_idx
        )
        gamma_t, gamma_p = compute_pairwise_ttests(
            orientation_groups, gamma_trial, event_codes, pick_idx
        )
        plot_pairwise_heatmap(
            alpha_t,
            alpha_p,
            orientation_labels,
            orientation_alpha_t_path,
            "Alpha T-values (Orientation)",
        )
        plot_pairwise_heatmap(
            gamma_t,
            gamma_p,
            orientation_labels,
            orientation_gamma_t_path,
            "Gamma T-values (Orientation)",
        )

        dir_alpha_t, dir_alpha_p = compute_pairwise_ttests(
            direction_groups, alpha_trial, event_codes, pick_idx
        )
        dir_gamma_t, dir_gamma_p = compute_pairwise_ttests(
            direction_groups, gamma_trial, event_codes, pick_idx
        )
        plot_pairwise_heatmap(
            dir_alpha_t,
            dir_alpha_p,
            direction_labels,
            direction_alpha_t_path,
            "Alpha T-values (Direction)",
        )
        plot_pairwise_heatmap(
            dir_gamma_t,
            dir_gamma_p,
            direction_labels,
            direction_gamma_t_path,
            "Gamma T-values (Direction)",
        )

        ttest_outputs = {
            "orientation_alpha_ttests": str(orientation_alpha_t_path),
            "orientation_gamma_ttests": str(orientation_gamma_t_path),
            "direction_alpha_ttests": str(direction_alpha_t_path),
            "direction_gamma_ttests": str(direction_gamma_t_path),
        }

    payload = {
        "picked_channel": pick_ch,
        "trigger_rows": trigger_rows,
        "orientation_groups": orientation_groups,
        "direction_groups": direction_groups,
        "correlations": {
            "orientation": orientation_corr,
            "direction": direction_corr,
        },
        "outputs": {
            "trigger_summary": str(trigger_bar_path),
            "orientation_group_summary": str(orientation_group_path),
            "direction_group_summary": str(direction_group_path),
            "orientation_scatter": str(orientation_scatter_path),
            "direction_scatter": str(direction_scatter_path),
            **ttest_outputs,
        },
    }
    ersp_summary = maybe_load_json(ersp_stats_summary_path)
    if ersp_summary is not None:
        payload["ersp_stats_summary"] = ersp_summary
    save_json(out_dir / "orientation_summary.json", payload)
    print(f"Saved orientation summaries into: {out_dir}")


if __name__ == "__main__":
    main()
