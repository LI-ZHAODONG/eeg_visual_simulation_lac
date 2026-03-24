import argparse
import json
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def extract_probability(notes: str):
    if not notes:
        return None
    try:
        start = notes.index("(") + 1
        end = notes.index("%", start)
        return float(notes[start:end]) / 100.0
    except ValueError:
        return None


def refine_component(label: str, prob: float | None):
    if prob is None:
        return None, "No probability parsed from notes; left unchanged."

    if label == "brain" and prob >= 0.50:
        return True, f"Manual-assisted keep: borderline brain ({prob * 100:.1f}%)."

    if label == "channel noise" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline channel noise ({prob * 100:.1f}%)."

    if label == "muscle artifact" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline muscle artifact ({prob * 100:.1f}%)."

    if label == "eye blink" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline eye blink ({prob * 100:.1f}%)."

    if label == "heart beat" and prob >= 0.50:
        return False, f"Manual-assisted reject: borderline heart beat ({prob * 100:.1f}%)."

    if label == "other" and prob >= 0.65:
        return False, f"Manual-assisted reject: stronger other ({prob * 100:.1f}%)."

    return None, f"Left unsure: {label} ({prob * 100:.1f}%)."


def main():
    parser = argparse.ArgumentParser(
        description="Refine one ICA review JSON and save a separate refined copy."
    )
    parser.add_argument(
        "--review-json",
        type=Path,
        required=True,
        help="Path to the original ICA review JSON.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        required=True,
        help="Path to save the refined ICA review JSON.",
    )
    args = parser.parse_args()

    review_json = args.review_json.resolve()
    out_json = args.out_json.resolve()

    if not review_json.exists():
        raise FileNotFoundError(f"Review JSON not found: {review_json}")

    payload = load_json(review_json)
    decisions = payload.get("component_decisions", {})

    added_keeps = 0
    added_rejects = 0

    for _, comp in decisions.items():
        current_keep = comp.get("keep")
        label = comp.get("label")
        notes = comp.get("notes", "")

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

    write_json(out_json, payload)

    final_kept = sum(1 for d in decisions.values() if d.get("keep") is True)
    final_rejected = sum(1 for d in decisions.values() if d.get("keep") is False)
    final_unsure = sum(1 for d in decisions.values() if d.get("keep") is None)

    print(f"Saved refined review JSON: {out_json}")
    print("\n--- Refinement summary ---")
    print(f"Added keeps:    {added_keeps}")
    print(f"Added rejects:  {added_rejects}")
    print(f"Final kept:     {final_kept}")
    print(f"Final rejected: {final_rejected}")
    print(f"Final unsure:   {final_unsure}")


if __name__ == "__main__":
    main()