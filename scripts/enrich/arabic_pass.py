"""Second enrichment pass: add Arabic-script variants on top of each sense's current Claude review.

  .venv/bin/python scripts/enrich/arabic_pass.py show <dictionary_id> [--limit 300] [--width 0]
      Prints the next senses not yet covered by the Arabic pass: term | english | current variants
      [|| gemma: proposals from `arabic_auto.py propose`, when present].
  .venv/bin/python scripts/enrich/arabic_pass.py apply <dictionary_id> <decisions.txt>
      Same line syntax as session_review.py (<n> TAB form|type|conf ; ... or <n> TAB -).
      The new forms are merged into the current review (existing variants are kept) and the
      sense is marked as covered by the Arabic pass, then everything is finalized.
  .venv/bin/python scripts/enrich/arabic_pass.py ready
      Per dictionary: <ready for review> TAB <pending> TAB <id prefix>  (used by scripts/automation/autopilot.sh).
  .venv/bin/python scripts/enrich/arabic_pass.py status
      Senses covered by the Arabic pass per dictionary.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "enrich"))

from kass_layer.dictionary.enrichment import (  # noqa: E402
    OUT_DIR,
    REVIEW_DIR,
    append_jsonl,
    complete_dictionaries,
    current_generations,
    current_reviews,
    finalize,
    normalize,
    review_hash,
    write_json,
)
from session_review import REVIEWER, parse_decision  # noqa: E402

SELECTION_DIR = OUT_DIR / "session"
PROPOSAL_DIR = OUT_DIR / "raw" / "arabic_auto" / "proposals"  # Gemma proposals from arabic_auto.py propose
SOURCE_PREFIX = "arabic-pass"


def _dictionary(prefix: str) -> dict:
    for dictionary in complete_dictionaries():
        if dictionary["dictionary_id"].startswith(prefix):
            return dictionary
    raise SystemExit(f"No completed dictionary {prefix}")


def _state(dictionary: dict) -> tuple[dict, dict]:
    generations = current_generations(dictionary)
    return generations, current_reviews(dictionary, generations)


def _pending(dictionary: dict) -> list[tuple[dict, dict]]:
    _, reviews = _state(dictionary)
    return [(record, reviews[record["sense_id"]]) for record in dictionary["records"]
            if record["sense_id"] in reviews
            and not str(reviews[record["sense_id"]].get("source", "")).startswith(SOURCE_PREFIX)]


def _proposals(dictionary: dict) -> dict[str, list[dict]]:
    path = PROPOSAL_DIR / f"{dictionary['dictionary_id']}.jsonl"
    proposals = {}
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        try:  # `propose` may be appending while we read: skip a half-written last line
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        proposals[row["sense_id"]] = row["proposals"]
    return proposals


def cmd_show(args) -> None:
    dictionary = _dictionary(args.dictionary)
    pending = _pending(dictionary)
    proposals = _proposals(dictionary)
    if args.ready:
        pending = [(record, review) for record, review in pending if record["sense_id"] in proposals]
    pairs = pending[: args.limit]
    write_json(SELECTION_DIR / f"arabic-{dictionary['dictionary_id']}.json", [r["sense_id"] for r, _ in pairs])
    print(f"# {dictionary['dictionary_name'].strip()} — {len(pending)} pending, showing {len(pairs)}")
    for n, (record, review) in enumerate(pairs, start=1):
        current = " ; ".join(v["form"] for v in review.get("variants") or []) or "-"
        definition = " ".join((record.get("definition") or "").split())[: args.width]
        tail = f" | {definition}" if args.width else ""
        gemma = proposals.get(record["sense_id"])
        gemma_tail = "" if gemma is None else " || gemma: " + (" ; ".join(p["form"] for p in gemma) or "-")
        print(f"{n}\t{record.get('term_without_diacritics') or record['term']} | {record.get('english_term') or ''}"
              f"{tail} || {current}{gemma_tail}")


def cmd_apply(args) -> None:
    dictionary = _dictionary(args.dictionary)
    selection = json.loads((SELECTION_DIR / f"arabic-{dictionary['dictionary_id']}.json").read_text(encoding="utf-8"))
    generations, reviews = _state(dictionary)
    rows = []
    for line in Path(args.decisions).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        number, _, text = line.partition("\t")
        sense_id = selection[int(number) - 1]
        old = reviews.get(sense_id)
        if old is None or str(old.get("source", "")).startswith(SOURCE_PREFIX):
            continue
        existing = list(old.get("variants") or [])
        seen = {normalize(v["form"]) for v in existing}
        added = [v for v in parse_decision(text, [])["variants"] if normalize(v["form"]) not in seen]
        row = dict(old)
        row.update({"variants": existing + added, "model": REVIEWER,
                    "input_sha256": review_hash(generations[sense_id]),
                    "source": f"{SOURCE_PREFIX}:{Path(args.decisions).name}",
                    "arabic_pass_added": [v["form"] for v in added]})
        rows.append(row)
    append_jsonl(REVIEW_DIR / f"{dictionary['dictionary_id']}.jsonl", rows)
    finalize(complete_dictionaries())
    print(f"arabic pass: {len(rows)} senses, {sum(len(r['arabic_pass_added']) for r in rows)} forms added; "
          f"{len(_pending(dictionary))} pending in {dictionary['dictionary_name'].strip()}")


def cmd_status(args) -> None:
    for dictionary in complete_dictionaries():
        _, reviews = _state(dictionary)
        done = sum(str(r.get("source", "")).startswith(SOURCE_PREFIX) for r in reviews.values())
        print(f"{done:>6}/{len(dictionary['records']):<6} {dictionary['dictionary_id'][:8]}  {dictionary['dictionary_name'].strip()}")


def cmd_ready(args) -> None:
    """Per dictionary: senses pending the Arabic pass whose Gemma proposals exist (ready for review)."""
    for dictionary in complete_dictionaries():
        proposals = _proposals(dictionary)
        pending = _pending(dictionary)
        ready = sum(record["sense_id"] in proposals for record, _ in pending)
        print(f"{ready}\t{len(pending)}\t{dictionary['dictionary_id'][:8]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("show")
    show.add_argument("dictionary")
    show.add_argument("--limit", type=int, default=300)
    show.add_argument("--width", type=int, default=0)
    show.add_argument("--ready", action="store_true", help="only senses that already have Gemma proposals")
    show.set_defaults(handler=cmd_show)
    commands.add_parser("ready").set_defaults(handler=cmd_ready)
    apply = commands.add_parser("apply")
    apply.add_argument("dictionary")
    apply.add_argument("decisions")
    apply.set_defaults(handler=cmd_apply)
    status = commands.add_parser("status")
    status.set_defaults(handler=cmd_status)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
