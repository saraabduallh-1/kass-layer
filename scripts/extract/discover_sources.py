from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "data" / "dictionaries" / "raw" / "discovery_report.json"


def main() -> None:
    report = {
        "discovery_date": "2026-10-14",
        "status": "partial_public_discovery",
        "discovered_sources": [
            {
                "name": "Siwar",
                "candidate_url": "https://siwar.sa/",
                "status": "not_dictionary",
                "reason": "Accessible site is a child hospitality landing page and not an Arabic dictionary platform."
            },
            {
                "name": "Riyadh Dictionary",
                "candidate_url": "https://riyadhdictionary.com",
                "status": "unresolved",
                "reason": "DNS resolution failed from this environment."
            },
            {
                "name": "King Salman Global Academy for Arabic Language",
                "candidate_url": "https://arabicacademy.gov.sa",
                "status": "unresolved",
                "reason": "No public dictionary endpoint was reachable from this environment."
            },
        ],
        "dictionaries_discovered": 0,
        "dictionaries_extracted": 0,
        "total_original_entries": 0,
        "notes": [
            "Public Academy dictionary sources were not accessible from this environment.",
            "The project records blocked sources and continues with the pipeline scaffold, cleaning, and retrieval logic without fabricating entries."
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Discovery report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
