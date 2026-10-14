from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.pipeline import deduplicate_entries, normalize_arabic

ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "tests" / "fixtures" / "seed_entries.json"
OUTPUT_PATH = ROOT / "tests" / "fixtures" / "seed_entries.cleaned.json"


def main() -> None:
    records = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    cleaned = []
    for item in records:
        cleaned.append({**item, "term": normalize_arabic(item.get("term", "")), "definition": normalize_arabic(item.get("definition", ""))})
    cleaned = deduplicate_entries(cleaned)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Cleaned output written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
