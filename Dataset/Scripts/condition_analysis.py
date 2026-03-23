import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_npz_dict(path):
    data = np.load(path)
    return {key: data[key] for key in data.files}


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def group_mean(code_map, codes):
    present = [str(code) for code in codes if str(code) in code_map]
    if not present:
        return None
    return np.stack([code_map[code] for code in present], axis=0).mean(axis=0)


def choose_channel(ch_names):
    for ch in ["Oz", "O1", "O2", "POz", "Pz", "Cz"]:
        if ch in ch_names:
            return ch
    return ch_names[0]


def build_group_series(mapping, alpha_map, gamma_map, ch_names, pick_idx):
    groups = [
        ("full", mapping["retinotopy_groups"]["full_field"]),
        ("left", mapping["retinotopy_groups"]["left_hemifield"]),
        ("right", mapping["retinotopy_groups"]["right_hemifield"]),
        ("top", mapping["retinotopy_groups"]["upper_hemifield"]),
        ("bottom", mapping["retinotopy_groups"]["lower_hemifield"]),
        ("quad_BR", [6]),
        ("quad_BL", [7]),
        ("quad_TL", [8]),
        ("quad_TR", [9]),
        ("oct_BR1", [10]),
        ("oct_BR2", [11]),
        ("oct_BL2", [12]),
        ("oct_BL1", [13]),
        ("oct_TL1", [14]),
        ("oct_TL2", [15]),
        ("oct_TR2", [16]),
        ("oct_TR1", [17]),
        ("blank", mapping["retinotopy_groups"]["blank"]),
        ("periph", mapping["retinotopy_groups"]["periphery"]),
        ("fovea", mapping["retinotopy_groups"]["fovea"]),
    ]

    summary = []
    for label, codes in groups:
        alpha = group_mean(alpha_map, codes)
        gamma = group_mean(gamma_map, codes)
        if alpha is None or gamma is None:
            continue
        summary.append(
            {
                "label": label,
                "codes": codes,
                "alpha_mean": float(alpha[pick_idx]),
                "gamma_mean": float(gamma[pick_idx]),
            }
        )
    return summary


def plot_band_bars(summary, out_path, title, field):
    labels = [row["label"] for row in summary]
    values = [row[field] for row in summary]

    fig, ax = plt.subplots(figsize=(14, 5))
    color = "#f28e2b" if "gamma" in field else "#7ea6d8"
    ax.bar(labels, values, color=color)
    ax.set_title(title)
    ax.set_ylabel("Mean Power")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def plot_alpha_gamma_scatter(summary, out_path):
    alpha = np.array([row["alpha_mean"] for row in summary])
    gamma = np.array([row["gamma_mean"] for row in summary])
    labels = [row["label"] for row in summary]

    slope, intercept = np.polyfit(alpha, gamma, 1)
    predicted = slope * alpha + intercept
    residuals = gamma - predicted
    corr = float(np.corrcoef(alpha, gamma)[0, 1])

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].scatter(alpha, gamma, color="#555555")
    axes[0].plot(np.sort(alpha), slope * np.sort(alpha) + intercept, "--", color="#1f77b4")
    for x, y, label in zip(alpha, gamma, labels):
        axes[0].text(x, y, label, fontsize=8)
    axes[0].set_title(f"Alpha vs Gamma (r = {corr:.2f})")
    axes[0].set_xlabel("Alpha Power")
    axes[0].set_ylabel("Gamma Power")

    axes[1].bar(labels, residuals, color="#888888")
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_title("Residuals from Alpha-Gamma Fit")
    axes[1].tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    return corr, residuals.tolist()


def main():
    parser = argparse.ArgumentParser(
        description="Build paper-style retinotopy summaries from alpha/gamma condition outputs."
    )
    parser.add_argument("--alpha-by-condition", type=Path, required=True)
    parser.add_argument("--gamma-by-condition", type=Path, required=True)
    parser.add_argument("--band-power-summary", type=Path, required=True)
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

    ch_names = summary_json["ch_names"]
    pick_ch = choose_channel(ch_names)
    pick_idx = ch_names.index(pick_ch)

    summary = build_group_series(mapping, alpha_map, gamma_map, ch_names, pick_idx)

    gamma_bar_path = out_dir / "retinotopy_gamma_summary.png"
    alpha_bar_path = out_dir / "retinotopy_alpha_summary.png"
    scatter_path = out_dir / "retinotopy_alpha_gamma_scatter.png"

    plot_band_bars(summary, gamma_bar_path, f"Gamma Band (40-80 Hz, {pick_ch})", "gamma_mean")
    plot_band_bars(summary, alpha_bar_path, f"Alpha Band (8-13 Hz, {pick_ch})", "alpha_mean")
    corr, residuals = plot_alpha_gamma_scatter(summary, scatter_path)

    payload = {
        "picked_channel": pick_ch,
        "groups": summary,
        "alpha_gamma_correlation": corr,
        "residuals": residuals,
        "outputs": {
            "gamma_bar": str(gamma_bar_path),
            "alpha_bar": str(alpha_bar_path),
            "scatter": str(scatter_path),
        },
    }
    save_json(out_dir / "retinotopy_summary.json", payload)
    print(f"Saved retinotopy summaries into: {out_dir}")


if __name__ == "__main__":
    main()
