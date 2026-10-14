from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "data" / "dictionaries" / "raw" / "discovery_report.json"
RECORDS_PATH = ROOT / "data" / "dictionaries" / "raw" / "siwar_public_senses.json"
REGISTRY_PATH = ROOT / "data" / "dictionaries" / "raw" / "dictionary_registry.json"
ENUMERATION_REPORT_PATH = ROOT / "data" / "dictionaries" / "raw" / "siwar_enumeration_report.json"


def main() -> None:
    records = json.loads(RECORDS_PATH.read_text(encoding="utf-8")) if RECORDS_PATH.exists() else []
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8")) if REGISTRY_PATH.exists() else {"sources": []}
    if not ENUMERATION_REPORT_PATH.exists():
        raise SystemExit("Run scripts/extract/enumerate_siwar.py before generating the dictionary report.")

    enumeration = json.loads(ENUMERATION_REPORT_PATH.read_text(encoding="utf-8"))
    sources = enumeration["sources"]
    complete_count = sum(source["status"] == "complete" for source in sources)
    extracted_count = sum(source["number_of_entries"] > 0 for source in sources)
    if complete_count == len(sources) and sources:
        status = "complete"
    elif extracted_count:
        status = "partial_extraction_verified"
    else:
        status = "public_sources_discovered_extraction_pending"

    report = {
        "discovery_date": datetime.now(timezone.utc).date().isoformat(),
        "status": status,
        "discovery_scope": "All dictionaries returned by SIWAR's public lexicon catalog endpoint.",
        "dictionaries_discovered": len(sources),
        "dictionaries_extracted": extracted_count,
        "dictionaries_complete": complete_count,
        "total_original_entries": sum(source["number_of_entries"] for source in sources),
        "total_sense_records": sum(source["number_of_senses"] for source in sources),
        "sum_published_entry_metadata": sum(source["total_published_entries"] or 0 for source in sources),
        "sum_public_browse_rows": sum(source["public_browse_total_rows"] or 0 for source in sources),
        "coverage_note": enumeration["coverage_note"],
        "rate_limit_seconds": enumeration["rate_limit_seconds"],
        "discovered_sources": sources,
        "preserved_query_sample": {
            "scope": "Historical query-scoped output; excluded from enumeration counts to avoid overlap.",
            "source_dictionary_count": len(registry["sources"]),
            "unique_source_entries": len({(record["dictionary_id"], record["entry_id"]) for record in records}),
            "sense_records": len(records),
        },
        "notes": [
            "Entry totals and definitions are extracted separately under data/dictionaries/raw/siwar/by_dictionary/.",
            "Published metadata totals and public browse row totals differ; estimated coverage is withheld until full index reconciliation.",
            "The five-second robots crawl delay makes full entry-by-entry export a long-running resumable job.",
            "Seed and test fixtures are excluded from production counts.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Discovery report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
