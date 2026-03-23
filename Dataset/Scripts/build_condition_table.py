import argparse
import json
from pathlib import Path

import numpy as np


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_npz_dict(path):
    data = np.load(path)
    return {key: data[key] for key in data.files}


def summarize_group(code_map, group_codes):
    present = [str(code) for code in group_codes if str(code) in code_map]
    missing = [int(code) for code in group_codes if str(code) not in code_map]

    if not present:
        return {
            "codes": list(group_codes),
            "present_codes": [],
            "missing_codes": missing,
            "mean": None,
        }

    stacked = np.stack([code_map[code] for code in present], axis=0)
    return {
        "codes": list(group_codes),
        "present_codes": [int(code) for code in present],
        "missing_codes": missing,
        "mean": stacked.mean(axis=0).tolist(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Build grouped condition summaries from alpha/gamma event-code outputs."
    )
    parser.add_argument(
        "--alpha-by-condition",
        type=Path,
        required=True,
        help="Path to the alpha_by_condition.npz file.",
    )
    parser.add_argument(
        "--gamma-by-condition",
        type=Path,
        required=True,
        help="Path to the gamma_by_condition.npz file.",
    )
    parser.add_argument(
        "--mapping-json",
        type=Path,
        default=None,
        help="Path to the condition mapping JSON.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to the alpha file directory.",
    )
    args = parser.parse_args()

    alpha_path = args.alpha_by_condition.resolve()
    gamma_path = args.gamma_by_condition.resolve()
    if not alpha_path.exists():
        raise FileNotFoundError(f"Cannot find alpha condition file: {alpha_path}")
    if not gamma_path.exists():
        raise FileNotFoundError(f"Cannot find gamma condition file: {gamma_path}")

    out_dir = (args.out_dir or alpha_path.parent).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mapping_path = args.mapping_json
    if mapping_path is None:
        mapping_path = Path(__file__).resolve().parent / "condition_mapping.json"
    mapping_path = mapping_path.resolve()
    if not mapping_path.exists():
        raise FileNotFoundError(f"Cannot find condition mapping JSON: {mapping_path}")

    mapping = load_json(mapping_path)
    alpha_map = load_npz_dict(alpha_path)
    gamma_map = load_npz_dict(gamma_path)

    grouped = {
        "notes": mapping.get("notes", []),
        "retinotopy_groups": {},
        "orientation_groups": {},
    }

    for group_name, codes in mapping.get("retinotopy_groups", {}).items():
        grouped["retinotopy_groups"][group_name] = {
            "alpha": summarize_group(alpha_map, codes),
            "gamma": summarize_group(gamma_map, codes),
            "verified": bool(codes),
        }

    for group_name, codes in mapping.get("orientation_groups", {}).items():
        grouped["orientation_groups"][group_name] = {
            "alpha": summarize_group(alpha_map, codes),
            "gamma": summarize_group(gamma_map, codes),
            "verified": bool(codes),
        }

    payload = {
        "mapping_json": str(mapping_path),
        "alpha_by_condition": str(alpha_path),
        "gamma_by_condition": str(gamma_path),
        "families": mapping.get("families", {}),
        "grouped_conditions": grouped,
        "orientation_code_degrees": mapping.get("orientation_code_degrees", {}),
    }

    summary_path = out_dir / "condition_group_summary.json"
    write_json(summary_path, payload)
    print(f"Saved grouped condition summary: {summary_path}")


if __name__ == "__main__":
    main()
