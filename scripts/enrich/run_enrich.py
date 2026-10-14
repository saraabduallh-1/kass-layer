from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

ROOT = Path(__file__).resolve().parents[2]
CLEANED_PATH = ROOT / "data" / "dictionaries" / "cleaned" / "seed_entries.cleaned.json"
OUTPUT_PATH = ROOT / "data" / "dictionaries" / "enriched" / "enriched_terms.json"


def main() -> None:
    entries = json.loads(CLEANED_PATH.read_text(encoding="utf-8")) if CLEANED_PATH.exists() else []
    enriched = []
    for item in entries:
        term = item.get("term", "")
        enriched.append({
            "entry_id": item.get("entry_id"),
            "canonical_term": term,
            "synonyms": [term, f"{term}  ", "بديل محلي"],
            "english_equivalents": ["model"],
            "foreign_variants": ["model"],
            "non_standard_variants": ["مودل"],
            "priority": "high_priority",
            "source": item.get("dictionary_name"),
            "verification_status": "pending_manual_review",
        })
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Enriched terminology written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
