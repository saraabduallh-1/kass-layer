"""Compact review loop for Claude inside a Claude Code session (no API key needed).

  .venv/bin/python scripts/enrich/session_review.py show <dictionary_id> [--limit 120]
      Prints the next unreviewed senses as numbered lines: term | english | definition | Qwen proposals.
      The selection is saved so `apply` maps line numbers back to sense ids.
  .venv/bin/python scripts/enrich/session_review.py apply <dictionary_id> <decisions.txt>
      Reads one line per reviewed sense and imports it as the Claude review, then finalizes.

Decision line format:  <n> <TAB> <variant> ; <variant> ; ...     or   <n> <TAB> -   (no variants)
  variant = form|type|confidence[|amb=<Arabic note>][|was=<proposed form it corrects>]
  type: t transliteration, f foreign, a abbreviation, i informal_synonym, c colloquial, s spelling_variant
  confidence: h, m, l
A form equal to a Qwen proposal is "kept" (Qwen's example is reused); with was= it is "corrected";
otherwise it is "added". Proposals not kept or corrected are recorded as dropped.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.enrichment import (  # noqa: E402
    OUT_DIR,
    REVIEW_DIR,
    append_jsonl,
    complete_dictionaries,
    finalize,
    normalize,
    pending_review,
    review_rows,
    write_json,
)

SELECTION_DIR = OUT_DIR / "session"
REVIEWER = "claude-opus-5-5 (Claude Code session)"
TYPES = {"t": "transliteration", "f": "foreign", "a": "abbreviation", "i": "informal_synonym",
         "c": "colloquial", "s": "spelling_variant"}
CONFIDENCE = {"h": "high", "m": "medium", "l": "low"}


def _dictionary(dictionary_id: str) -> dict:
    for dictionary in complete_dictionaries():
        if dictionary["dictionary_id"].startswith(dictionary_id):
            return dictionary
    raise SystemExit(f"No completed dictionary {dictionary_id}")


def cmd_show(args) -> None:
    dictionary = _dictionary(args.dictionary)
    pairs = pending_review(dictionary)[: args.limit]
    write_json(SELECTION_DIR / f"{dictionary['dictionary_id']}.json", [record["sense_id"] for record, _ in pairs])
    print(f"# {dictionary['dictionary_name'].strip()} — {len(pending_review(dictionary))} pending, showing {len(pairs)}")
    for n, (record, generation) in enumerate(pairs, start=1):
        proposals = " ; ".join(f"{v['form']}" for v in generation["variants"]) or "-"
        definition = " ".join((record.get("definition") or "").split())[: args.width]
        print(f"{n}\t{record.get('term_without_diacritics') or record['term']} | {record.get('english_term') or ''} "
              f"| {definition} || {proposals}")


def parse_decision(text: str, proposals: list[dict]) -> dict:
    by_form = {normalize(v["form"]): v for v in proposals}
    variants, used = [], set()
    if text.strip() not in {"", "-"}:
        for chunk in text.split(";"):
            parts = [p.strip() for p in chunk.split("|")]
            if not parts[0]:
                continue
            form, kind, confidence = parts[0], TYPES[parts[1]], CONFIDENCE[parts[2]]
            extras = dict(p.split("=", 1) for p in parts[3:] if "=" in p)
            original = extras.get("was", "")
            source = by_form.get(normalize(original or form))
            if source is not None:
                used.add(normalize(source["form"]))
            action = "corrected" if original else "kept" if source is not None else "added"
            variants.append({
                "form": form, "type": kind, "confidence": confidence,
                "ambiguous": "amb" in extras, "ambiguity_note": extras.get("amb", ""),
                "example": (source or {}).get("example", "") if action != "added" else "",
                "action": action, "original_form": original,
            })
    dropped = [{"form": v["form"], "reason": "rejected_in_review"} for v in proposals if normalize(v["form"]) not in used]
    return {"variants": variants, "dropped": dropped}


def cmd_apply(args) -> None:
    dictionary = _dictionary(args.dictionary)
    selection = json.loads((SELECTION_DIR / f"{dictionary['dictionary_id']}.json").read_text(encoding="utf-8"))
    pending = {record["sense_id"]: (record, generation) for record, generation in pending_review(dictionary)}
    pairs, parsed = [], {}
    for line in Path(args.decisions).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        number, _, text = line.partition("\t")
        sense_id = selection[int(number) - 1]
        if sense_id not in pending:
            continue
        pairs.append(pending[sense_id])
        parsed[len(pairs)] = parse_decision(text, pending[sense_id][1]["variants"])
    rows = review_rows(dictionary, pairs, parsed, REVIEWER, f"session:{Path(args.decisions).name}")
    append_jsonl(REVIEW_DIR / f"{dictionary['dictionary_id']}.jsonl", rows)
    report = finalize(complete_dictionaries())
    stats = report["dictionaries"][dictionary["dictionary_id"]]
    print(f"imported {len(rows)} reviews; {dictionary['dictionary_name'].strip()}: "
          f"reviewed {stats['reviewed']}/{stats['senses']}, accepted {stats['variants_accepted']}, "
          f"review {stats['variants_review']}")


def cmd_fix(args) -> None:
    """Replace the review of an already-reviewed sense, found by its exact term (first match)."""
    from kass_layer.dictionary.enrichment import current_generations
    dictionary = _dictionary(args.dictionary)
    generations = current_generations(dictionary)
    matches = [r for r in dictionary["records"]
               if (r.get("term_without_diacritics") or r["term"]).strip() == args.term.strip() and r["sense_id"] in generations]
    if not matches:
        raise SystemExit(f"No generated sense with term {args.term!r}")
    record = matches[0]
    pair = (record, generations[record["sense_id"]])
    rows = review_rows(dictionary, [pair], {1: parse_decision(args.decision, pair[1]["variants"])}, REVIEWER, "session:fix")
    append_jsonl(REVIEW_DIR / f"{dictionary['dictionary_id']}.jsonl", rows)
    finalize(complete_dictionaries())
    print(f"fixed {args.term}: {[v['form'] for v in rows[0]['variants']]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show")
    show.add_argument("dictionary")
    show.add_argument("--limit", type=int, default=120)
    show.add_argument("--width", type=int, default=90, help="definition characters shown")
    show.set_defaults(handler=cmd_show)
    apply = commands.add_parser("apply")
    apply.add_argument("dictionary")
    apply.add_argument("decisions")
    apply.set_defaults(handler=cmd_apply)
    fix = commands.add_parser("fix")
    fix.add_argument("dictionary")
    fix.add_argument("term")
    fix.add_argument("decision", help="same variant syntax as a decision line, or -")
    fix.set_defaults(handler=cmd_fix)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
