import argparse
import json
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def extract_probability(notes: str):
    """
    Extract percentage from notes like:
    'Unsure: brain (57.0%) - Did not meet auto-decision rule. Please review.'
    Returns float in [0, 1], or None if parsing fails.
    """
    if not notes:
        return None
    try:
        start = notes.index("(") + 1
        end = notes.index("%", start)
        return float(notes[start:end]) / 100.0
    except ValueError:
        return None


def refine_component(label: str, prob: float | None):
    """
    Semi-manual heuristic:
    - borderline brain -> keep
    - borderline artifacts -> reject
    - otherwise leave unsure
    """

    if prob is None:
        return None, "No probability parsed from notes; left unchanged."

    # Borderline brain: keep
    if label == "brain" and prob >= 0.50:
        return True, f"Manual-assisted keep: borderline brain ({prob * 100:.1f}%)."

    # Borderline artifacts: reject
    if label == "channel noise" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline channel noise ({prob * 100:.1f}%)."

    if label == "muscle artifact" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline muscle artifact ({prob * 100:.1f}%)."

    if label == "eye blink" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline eye blink ({prob * 100:.1f}%)."

    if label == "heart beat" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline heart beat ({prob * 100:.1f}%)."

    # Be more conservative with "other"
    if label == "other" and prob >= 0.65:
        return False, f"Manual-assisted reject: stronger other ({prob * 100:.1f}%)."

    return None, f"Left unsure: {label} ({prob * 100:.1f}%)."


    
def refine_review_file(review_json: Path, overwrite: bool = False):
    payload = load_json(review_json)
    decisions = payload.get("component_decisions", {})

    added_keeps = 0
    added_rejects = 0

    for comp_idx, comp in decisions.items():
        current_keep = comp.get("keep")
        label = comp.get("label")
        notes = comp.get("notes", "")

        # Only touch unsure components
        if current_keep is not None:
            continue

        prob = extract_probability(notes)
        new_keep, new_note = refine_component(label, prob)

        if new_keep is True:
            comp["keep"] = True
            comp["notes"] = new_note
            added_keeps += 1
        elif new_keep is False:
            comp["keep"] = False
            comp["notes"] = new_note
            added_rejects += 1
        else:
            comp["notes"] = new_note

    final_kept = sum(1 for d in decisions.values() if d.get("keep") is True)
    final_rejected = sum(1 for d in decisions.values() if d.get("keep") is False)
    final_unsure = sum(1 for d in decisions.values() if d.get("keep") is None)

    if overwrite:
        out_json = review_json
    else:
        out_json = review_json.with_name(review_json.stem + "-refined.json")

    write_json(out_json, payload)

    return {
        "input": str(review_json),
        "output": str(out_json),
        "added_keeps": added_keeps,
        "added_rejects": added_rejects,
        "final_kept": final_kept,
        "final_rejected": final_rejected,
        "final_unsure": final_unsure,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Batch-refine ICA review JSON files across all subject output folders."
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        required=True,
        help="Path to Dataset/outputs directory containing sub-XX folders.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the original review JSON instead of creating a -refined copy.",
    )
    args = parser.parse_args()

    outputs_dir = args.outputs_dir.resolve()
    if not outputs_dir.exists():
        raise FileNotFoundError(f"Outputs directory not found: {outputs_dir}")

    review_files = sorted(outputs_dir.glob("sub-*/**/*-ica_component_review.json"))

    if not review_files:
        print("No ICA review JSON files found.")
        return

    print(f"Found {len(review_files)} ICA review JSON files.\n")

    total_added_keeps = 0
    total_added_rejects = 0

    for review_json in review_files:
        result = refine_review_file(review_json, overwrite=args.overwrite)

        total_added_keeps += result["added_keeps"]
        total_added_rejects += result["added_rejects"]

        print(f"Processed: {review_json.parent.name}")
        print(f"  Input:          {result['input']}")
        print(f"  Output:         {result['output']}")
        print(f"  Added keeps:    {result['added_keeps']}")
        print(f"  Added rejects:  {result['added_rejects']}")
        print(f"  Final kept:     {result['final_kept']}")
        print(f"  Final rejected: {result['final_rejected']}")
        print(f"  Final unsure:   {result['final_unsure']}")
        print()

    print("=== Batch refinement complete ===")
    print(f"Total new keeps added:   {total_added_keeps}")
    print(f"Total new rejects added: {total_added_rejects}")


if __name__ == "__main__":
    main()