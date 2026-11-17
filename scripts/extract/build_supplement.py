"""Turns the Kass supplement glossary (data/dictionaries/supplement/kass_supplement.json) into an enriched dictionary file
like the SIWAR ones, so the page index, the vectors and the API pick it up: data/dictionaries/enriched/kass-supplement.enriched.json.

The supplement holds standard Arabic terms for everyday words the SIWAR dictionaries of tech, finance and media do not
cover (طابعة for برنتر, كلمة المرور for باسورد). It is named «من خارج سوار» everywhere it shows.
Run: .venv/Scripts/python scripts/extract/build_supplement.py
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "dictionaries" / "supplement" / "kass_supplement.json"
OUT = ROOT / "data" / "dictionaries" / "enriched" / "kass-supplement.enriched.json"
DIAC = re.compile("[ً-ْٰ]")


def main() -> None:
    src = json.loads(SRC.read_text(encoding="utf-8"))
    records = []
    for i, t in enumerate(src["terms"]):
        variants = [{"form": v, "type": "foreign" if re.search("[A-Za-z]", v) else "transliteration", "status": "accepted"}
                    for v in t["variants"]]
        records.append({
            "entry_id": f"kass-supplement-{i}", "sense_id": f"kass-supplement-{i}:0",
            "term": t["term"], "term_without_diacritics": DIAC.sub("", t["term"]),
            "definition": t["definition"], "english_term": t["english"],
            "dictionary_id": "kass-supplement", "dictionary_name": src["name"], "source_url": None,
            "enrichment": {"variants": variants, "reviewed_by": "claude-opus-5-5 (Claude Code session)"},
        })
    out = {"dictionary_id": "kass-supplement", "dictionary_name": src["name"], "source_export": str(SRC.relative_to(ROOT)),
           "generated_at": datetime.now(timezone.utc).isoformat(), "enrichment_status": "complete", "note": src["note"],
           "counts": {"senses": len(records), "variants_accepted": sum(len(r["enrichment"]["variants"]) for r in records)},
           "records": records}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(records)} terms, {out['counts']['variants_accepted']} variants -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
