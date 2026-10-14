from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.pipeline import classify_term

ROOT = Path(__file__).resolve().parents[2]
CLEANED_PATH = ROOT / "data" / "dictionaries" / "cleaned" / "seed_entries.cleaned.json"
REPORT_PATH = ROOT / "reports" / "classification_report.json"


def main() -> None:
    entries = json.loads(CLEANED_PATH.read_text(encoding="utf-8")) if CLEANED_PATH.exists() else []
    report = {
        "generated_at": "2026-10-14",
        "counts": {
            "high_priority": 0,
            "medium_priority": 0,
            "low_priority": 0,
            "general_vocabulary": 0,
        },
        "entries": [],
    }
    for item in entries:
        classification = classify_term(item.get("term", ""))
        report["counts"][classification] = report["counts"].get(classification, 0) + 1
        report["entries"].append({
            "entry_id": item.get("entry_id"),
            "term": item.get("term"),
            "classification": classification,
            "reason": "contains technical or professional terminology" if classification == "high_priority" else "general vocabulary"
        })
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Classification report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
