from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from kass_layer.dictionary.pipeline import write_json_file
from kass_layer.dictionary.siwar import (
    SIWAR_BASE_URL,
    limit_entries,
    parse_siwar_entries,
    search_url,
)

DEFAULT_QUERIES = ["نموذج", "كتاب", "بيت", "عمل", "لغة", "بيانات", "قهوة", "ماء", "طريق", "مدينة"]
OUTPUT_PATH = ROOT / "data" / "dictionaries" / "raw" / "siwar_public_senses.json"
REGISTRY_PATH = ROOT / "data" / "dictionaries" / "raw" / "dictionary_registry.json"


def extract_queries(queries: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    searched_queries: list[str] = []
    seen: set[tuple[str, str | None, str]] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="ar-SA", user_agent="Mozilla/5.0")
        try:
            for query in queries:
                page.goto(search_url(query), wait_until="domcontentloaded", timeout=60000)
                try:
                    page.get_by_role("button", name="بــحـــث", exact=True).click(timeout=15000)
                except PlaywrightTimeoutError:
                    continue
                searched_queries.append(query)
                try:
                    page.locator(".lexical-entry-card__details a[href*='public-dict-information']").first.wait_for(
                        state="attached", timeout=20000
                    )
                except PlaywrightTimeoutError:
                    continue

                page.wait_for_timeout(750)
                for record in parse_siwar_entries(page.content(), query):
                    identity = (
                        record["dictionary_id"],
                        record["entry_id"],
                        record["sense_number"],
                        record["definition"],
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    records.append(record)
        finally:
            browser.close()

    return records, searched_queries


def _registry(records: list[dict[str, Any]], queries: list[str]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for record in records:
        source = sources.setdefault(
            record["dictionary_id"],
            {
                "name": record["dictionary_name"],
                "platform": "SIWAR",
                "dictionary_id": record["dictionary_id"],
                "source_url": f"{SIWAR_BASE_URL}/",
                "dictionary_url": record["dictionary_url"],
                "public_search_pattern": f"{SIWAR_BASE_URL}/result-page-public/{{query}}?searchType=lemma",
                "queries_with_records": [],
                "sense_records_extracted": 0,
                "unique_entries_extracted": 0,
                "complete_dictionary_dump": False,
            },
        )
        source["sense_records_extracted"] += 1
        if record["extraction_query"] not in source["queries_with_records"]:
            source["queries_with_records"].append(record["extraction_query"])
    for dictionary_id, source in sources.items():
        source["unique_entries_extracted"] = len(
            {record["entry_id"] for record in records if record["dictionary_id"] == dictionary_id}
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queries_searched": queries,
        "entry_limit_per_dictionary": 20,
        "complete_catalog_dump": False,
        "sources": list(sources.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract public dictionary senses from SIWAR.")
    parser.add_argument("--queries", nargs="+", default=DEFAULT_QUERIES)
    parser.add_argument("--max-entries-per-dictionary", type=int, default=20)
    args = parser.parse_args()
    if args.max_entries_per_dictionary < 1:
        parser.error("--max-entries-per-dictionary must be greater than zero")

    records, searched_queries = extract_queries(args.queries)
    records = limit_entries(records, args.max_entries_per_dictionary)
    if not records:
        raise SystemExit("No official SIWAR dictionary senses were extracted; no production files written.")

    write_json_file(OUTPUT_PATH, records)
    write_json_file(REGISTRY_PATH, _registry(records, searched_queries))
    print(f"Saved {len(records)} SIWAR sense records to {OUTPUT_PATH}")
    print(f"Saved source registry to {REGISTRY_PATH}")


if __name__ == "__main__":
    main()