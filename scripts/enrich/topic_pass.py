"""Topic pass: add reviewed variants to named terms of one dictionary (any sense, even one the Arabic pass covered).

  .venv/bin/python scripts/enrich/topic_pass.py <dictionary_id> <decisions.txt> [--dry-run]

decisions.txt: one term per line,  <standard term> TAB <form|type|conf ; form|type|conf ...>
(types and confidence as in session_review.py; lines starting with # are notes). A chunk "!form" withdraws a form
that an earlier topic pass added to that term (forms from other passes cannot be removed this way). The forms are merged into the
term's current review (existing variants are kept, duplicates skipped) and everything is finalized. Original
term files are never touched. Refuses a form that is already the standard term of another sense in the dictionary.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "enrich"))

from kass_layer.dictionary.enrichment import (  # noqa: E402
    REVIEW_DIR,
    append_jsonl,
    complete_dictionaries,
    current_generations,
    current_reviews,
    finalize,
    normalize,
    review_hash,
)
from session_review import REVIEWER, parse_decision  # noqa: E402

SOURCE_PREFIX = "topic-pass"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dictionary")
    ap.add_argument("decisions")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dictionary = next((d for d in complete_dictionaries() if d["dictionary_id"].startswith(args.dictionary)), None)
    if dictionary is None:
        raise SystemExit(f"No completed dictionary {args.dictionary}")
    generations = current_generations(dictionary)
    reviews = current_reviews(dictionary, generations)
    by_term: dict[str, list[dict]] = {}
    for record in dictionary["records"]:
        by_term.setdefault(normalize(record.get("term_without_diacritics") or record["term"]), []).append(record)

    rows, problems = {}, []
    for line in Path(args.decisions).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        term, _, text = line.partition("\t")
        records = by_term.get(normalize(term), [])
        if len(records) != 1:
            problems.append(f"{term}: {len(records)} senses with this term")
            continue
        sense_id = records[0]["sense_id"]
        if sense_id not in reviews:
            problems.append(f"{term}: no review yet")
            continue
        row = rows.get(sense_id) or dict(reviews[sense_id], variants=list(reviews[sense_id].get("variants") or []))
        withdraw = {normalize(c.strip()[1:]) for c in text.split(";") if c.strip().startswith("!")}
        mine = {normalize(f) for f in row.get("topic_pass_added", [])}
        for key in withdraw - mine:
            problems.append(f"{term}: {key} was not added by a topic pass, kept")
        withdraw &= mine
        row["variants"] = [v for v in row["variants"] if normalize(v["form"]) not in withdraw]
        row["topic_pass_added"] = [f for f in row.get("topic_pass_added", []) if normalize(f) not in withdraw]
        text = ";".join(c for c in text.split(";") if not c.strip().startswith("!"))
        seen = {normalize(v["form"]) for v in row["variants"]}
        added = []
        for v in parse_decision(text, [])["variants"]:
            key = normalize(v["form"])
            if key in seen:
                continue
            if key in by_term and normalize(term) != key:
                problems.append(f"{v['form']}: already the standard term of another sense, skipped")
                continue
            seen.add(key)
            added.append(v)
        row["variants"] += added
        row.update({"model": REVIEWER, "input_sha256": review_hash(generations[sense_id]),
                    "source": f"{SOURCE_PREFIX}:{Path(args.decisions).name}",
                    "topic_pass_added": row.get("topic_pass_added", []) + [v["form"] for v in added]})
        rows[sense_id] = row
    for p in problems:
        print("  !", p)
    added = sum(len(r["topic_pass_added"]) for r in rows.values())  # this pass's forms on the touched terms
    print(f"topic pass: {len(rows)} terms, {added} forms {'would be ' if args.dry_run else ''}added "
          f"in {dictionary['dictionary_name'].strip()}")
    if not args.dry_run and rows:
        append_jsonl(REVIEW_DIR / f"{dictionary['dictionary_id']}.jsonl", list(rows.values()))
        finalize(complete_dictionaries())


if __name__ == "__main__":
    main()
