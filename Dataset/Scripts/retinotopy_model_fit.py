import argparse
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_npz_dict(path):
    data = np.load(path)
    return {key: data[key] for key in data.files}


def choose_channel(ch_names):
    for ch in ["Oz", "O1", "O2", "POz", "Pz", "Cz"]:
        if ch in ch_names:
            return ch
    return ch_names[0]


def mean_code_value(code_map, codes, pick_idx):
    present = [str(code) for code in codes if str(code) in code_map]
    if not present:
        return None
    stacked = np.stack([code_map[code] for code in present], axis=0)
    return float(stacked.mean(axis=0)[pick_idx])


def divisive_prediction(parts, sigma=0.5):
    parts = np.asarray(parts, dtype=float)
    if len(parts) == 0:
        return np.nan
    return parts.sum() / (1.0 + sigma * (len(parts) - 1))


def build_subject_group_values(alpha_map, gamma_map, pick_idx):
    return {
        "full": {
            "alpha": mean_code_value(alpha_map, [1], pick_idx),
            "gamma": mean_code_value(gamma_map, [1], pick_idx),
        },
        "blank": {
            "alpha": mean_code_value(alpha_map, [18], pick_idx),
            "gamma": mean_code_value(gamma_map, [18], pick_idx),
        },
        "left_right": {
            "alpha_parts": [
                mean_code_value(alpha_map, [2], pick_idx),
                mean_code_value(alpha_map, [3], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [2], pick_idx),
                mean_code_value(gamma_map, [3], pick_idx),
            ],
        },
        "top_bottom": {
            "alpha_parts": [
                mean_code_value(alpha_map, [4], pick_idx),
                mean_code_value(alpha_map, [5], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [4], pick_idx),
                mean_code_value(gamma_map, [5], pick_idx),
            ],
        },
        "quadrants": {
            "alpha_parts": [
                mean_code_value(alpha_map, [6], pick_idx),
                mean_code_value(alpha_map, [7], pick_idx),
                mean_code_value(alpha_map, [8], pick_idx),
                mean_code_value(alpha_map, [9], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [6], pick_idx),
                mean_code_value(gamma_map, [7], pick_idx),
                mean_code_value(gamma_map, [8], pick_idx),
                mean_code_value(gamma_map, [9], pick_idx),
            ],
        },
        "octants": {
            "alpha_parts": [
                mean_code_value(alpha_map, [10], pick_idx),
                mean_code_value(alpha_map, [11], pick_idx),
                mean_code_value(alpha_map, [12], pick_idx),
                mean_code_value(alpha_map, [13], pick_idx),
                mean_code_value(alpha_map, [14], pick_idx),
                mean_code_value(alpha_map, [15], pick_idx),
                mean_code_value(alpha_map, [16], pick_idx),
                mean_code_value(alpha_map, [17], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [10], pick_idx),
                mean_code_value(gamma_map, [11], pick_idx),
                mean_code_value(gamma_map, [12], pick_idx),
                mean_code_value(gamma_map, [13], pick_idx),
                mean_code_value(gamma_map, [14], pick_idx),
                mean_code_value(gamma_map, [15], pick_idx),
                mean_code_value(gamma_map, [16], pick_idx),
                mean_code_value(gamma_map, [17], pick_idx),
            ],
        },
        "fovea_periphery": {
            "alpha_parts": [
                mean_code_value(alpha_map, [20], pick_idx),
                mean_code_value(alpha_map, [19], pick_idx),
            ],
            "gamma_parts": [
                mean_code_value(gamma_map, [20], pick_idx),
                mean_code_value(gamma_map, [19], pick_idx),
            ],
        },
    }


def valid_parts(values):
    return [val for val in values if val is not None and not np.isnan(val)]


def compute_errors(group_values, sigma=0.5):
    full_alpha = group_values["full"]["alpha"]
    full_gamma = group_values["full"]["gamma"]
    blank_alpha = group_values["blank"]["alpha"]

    results = {}
    for group_name in ["left_right", "top_bottom", "quadrants", "octants", "fovea_periphery"]:
        alpha_parts = valid_parts(group_values[group_name]["alpha_parts"])
        gamma_parts = valid_parts(group_values[group_name]["gamma_parts"])

        alpha_linear = np.sum(alpha_parts)
        alpha_blank_corrected = np.sum([part - blank_alpha for part in alpha_parts]) if blank_alpha is not None else np.nan
        alpha_divnorm = divisive_prediction(alpha_parts, sigma=sigma)

        gamma_linear = np.sum(gamma_parts)
        gamma_divnorm = divisive_prediction(gamma_parts, sigma=sigma)

        results[group_name] = {
            "alpha": {
                "observed_full": full_alpha,
                "linear_prediction": float(alpha_linear),
                "divnorm_prediction": float(alpha_divnorm),
                "blank_corrected_linear_prediction": float(alpha_blank_corrected),
                "linear_mae": float(abs(alpha_linear - full_alpha)),
                "divnorm_mae": float(abs(alpha_divnorm - full_alpha)),
                "blank_corrected_linear_mae": float(abs(alpha_blank_corrected - full_alpha)),
            },
            "gamma": {
                "observed_full": full_gamma,
                "linear_prediction": float(gamma_linear),
                "divnorm_prediction": float(gamma_divnorm),
                "linear_mae": float(abs(gamma_linear - full_gamma)),
                "divnorm_mae": float(abs(gamma_divnorm - full_gamma)),
            },
        }
    return results


def aggregate_errors(per_subject_results):
    groups = ["left_right", "top_bottom", "quadrants", "octants", "fovea_periphery"]
    aggregated = {}
    for group in groups:
        alpha_linear = []
        alpha_div = []
        alpha_blank = []
        gamma_linear = []
        gamma_div = []
        for row in per_subject_results:
            if group not in row["errors"]:
                continue
            errs = row["errors"][group]
            alpha_linear.append(errs["alpha"]["linear_mae"])
            alpha_div.append(errs["alpha"]["divnorm_mae"])
            alpha_blank.append(errs["alpha"]["blank_corrected_linear_mae"])
            gamma_linear.append(errs["gamma"]["linear_mae"])
            gamma_div.append(errs["gamma"]["divnorm_mae"])
        aggregated[group] = {
            "alpha_linear_mae_mean": float(np.mean(alpha_linear)),
            "alpha_divnorm_mae_mean": float(np.mean(alpha_div)),
            "alpha_blank_corrected_linear_mae_mean": float(np.mean(alpha_blank)),
            "gamma_linear_mae_mean": float(np.mean(gamma_linear)),
            "gamma_divnorm_mae_mean": float(np.mean(gamma_div)),
            "n_subjects": len(alpha_linear),
        }
    return aggregated


def plot_error_bars(aggregated, out_path):
    labels = list(aggregated.keys())
    x = np.arange(len(labels))
    width = 0.35

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    axes[0].bar(x - width / 2, [aggregated[k]["alpha_linear_mae_mean"] for k in labels], width, label="Linear", color="#4c78a8")
    axes[0].bar(x + width / 2, [aggregated[k]["alpha_divnorm_mae_mean"] for k in labels], width, label="DivNorm", color="#d65f5f")
    axes[0].set_title("Alpha Band (Raw)")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=35)
    axes[0].legend()

    axes[1].bar(x - width / 2, [aggregated[k]["alpha_blank_corrected_linear_mae_mean"] for k in labels], width, label="Linear", color="#4c78a8")
    axes[1].bar(x + width / 2, [aggregated[k]["alpha_divnorm_mae_mean"] for k in labels], width, label="DivNorm", color="#d65f5f")
    axes[1].set_title("Alpha - Blank")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=35)
    axes[1].legend()

    axes[2].bar(x - width / 2, [aggregated[k]["gamma_linear_mae_mean"] for k in labels], width, label="Linear", color="#4c78a8")
    axes[2].bar(x + width / 2, [aggregated[k]["gamma_divnorm_mae_mean"] for k in labels], width, label="DivNorm", color="#d65f5f")
    axes[2].set_title("Gamma Band")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=35)
    axes[2].legend()

    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Fit simple linear and divisive retinotopy summation models."
    )
    parser.add_argument(
        "--outputs-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "outputs",
    )
    parser.add_argument("--sigma", type=float, default=0.5, help="Fixed divisive sigma.")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    outputs_root = args.outputs_root.resolve()
    out_dir = (args.out_dir or outputs_root).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    per_subject = []
    for sub_dir in sorted(path for path in outputs_root.glob("sub-*") if path.is_dir()):
        band_summary_paths = sorted(sub_dir.glob("*-band_power_summary.json"))
        alpha_paths = sorted(sub_dir.glob("*-alpha_by_condition.npz"))
        gamma_paths = sorted(sub_dir.glob("*-gamma_by_condition.npz"))
        if not band_summary_paths or not alpha_paths or not gamma_paths:
            continue

        band_summary = load_json(band_summary_paths[0])
        alpha_map = load_npz_dict(alpha_paths[0])
        gamma_map = load_npz_dict(gamma_paths[0])
        ch_names = band_summary["ch_names"]
        pick_ch = choose_channel(ch_names)
        pick_idx = ch_names.index(pick_ch)

        values = build_subject_group_values(alpha_map, gamma_map, pick_idx)
        errors = compute_errors(values, sigma=args.sigma)
        per_subject.append(
            {
                "subject": sub_dir.name,
                "picked_channel": pick_ch,
                "errors": errors,
            }
        )

    if not per_subject:
        raise RuntimeError("No subject-level band-power outputs were found for model fitting.")

    aggregated = aggregate_errors(per_subject)
    error_plot = out_dir / "retinotopy_model_fit_errors.png"
    plot_error_bars(aggregated, error_plot)

    payload = {
        "sigma": args.sigma,
        "n_subjects": len(per_subject),
        "per_subject": per_subject,
        "aggregated": aggregated,
        "outputs": {
            "error_plot": str(error_plot),
        },
        "notes": [
            "The divisive model here is a simple fixed-sigma approximation inferred from the paper summary.",
            "Prediction = sum(parts) / (1 + sigma * (n_parts - 1)).",
            "This is closer to the paper's intent than the previous repo state, but may still differ from the authors' exact implementation."
        ],
    }
    save_json(out_dir / "retinotopy_model_fit_summary.json", payload)
    print(f"Saved retinotopy model-fit outputs into: {out_dir}")


if __name__ == "__main__":
    main()
