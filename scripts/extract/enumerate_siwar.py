from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.robotparser import RobotFileParser

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.siwar_enumerator import (
    API_BASE_URL,
    MINIMUM_CRAWL_DELAY_SECONDS,
    ROBOTS_URL,
    PublicApiClient,
    atomic_write_json,
    build_extraction_report,
    discover_public_dictionaries,
    extract_dictionary,
)

DEFAULT_OUTPUT_ROOT = ROOT / "data" / "dictionaries" / "raw" / "siwar" / "by_dictionary"
CATALOG_PATH = ROOT / "data" / "dictionaries" / "raw" / "siwar_public_catalog.json"
REPORT_PATH = ROOT / "data" / "dictionaries" / "raw" / "siwar_enumeration_report.json"


def _load_and_validate_robots(client: PublicApiClient) -> float:
    contents = client.get_text(ROBOTS_URL)
    policy = RobotFileParser()
    policy.set_url(ROBOTS_URL)
    policy.parse(contents.splitlines())
    client.robots = policy
    crawl_delay = policy.crawl_delay("KassLayerPhase1Extractor")
    if crawl_delay is None:
        crawl_delay = policy.crawl_delay("*") or 0
    effective_delay = max(MINIMUM_CRAWL_DELAY_SECONDS, float(crawl_delay), client.delay_seconds)
    client.delay_seconds = effective_delay
    catalog_url = f"{API_BASE_URL}/lexicons/findAll/public"
    if not policy.can_fetch("KassLayerPhase1Extractor", catalog_url):
        raise PermissionError(f"Robots policy blocks the public catalog endpoint: {catalog_url}")
    return effective_delay


def _write_report(catalog: list[dict[str, Any]], output_root: Path, crawl_delay: float) -> None:
    atomic_write_json(REPORT_PATH, build_extraction_report(catalog, output_root, crawl_delay))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumably enumerate public SIWAR dictionaries and fetch source entries by lexical ID."
    )
    parser.add_argument("--dictionary-id", action="append", dest="dictionary_ids")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--delay-seconds", type=float, default=MINIMUM_CRAWL_DELAY_SECONDS)
    parser.add_argument("--max-entries-per-dictionary", type=int)
    args = parser.parse_args()

    if not 1 <= args.page_size <= 1000:
        parser.error("--page-size must be between 1 and 1000")
    if args.delay_seconds < MINIMUM_CRAWL_DELAY_SECONDS:
        parser.error("--delay-seconds cannot be less than the published robots.txt crawl delay")
    if args.max_entries_per_dictionary is not None and args.max_entries_per_dictionary < 1:
        parser.error("--max-entries-per-dictionary must be greater than zero")

    client = PublicApiClient(args.delay_seconds)
    crawl_delay = _load_and_validate_robots(client)
    catalog = discover_public_dictionaries(client)
    atomic_write_json(CATALOG_PATH, catalog)
    DEFAULT_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    selected_ids = set(args.dictionary_ids or [])
    selected_sources = [
        source for source in catalog if not selected_ids or source.get("_id") in selected_ids
    ]
    missing_ids = selected_ids - {source.get("_id") for source in selected_sources}
    if missing_ids:
        parser.error(f"Dictionary IDs were not found in the public catalog: {', '.join(sorted(missing_ids))}")

    _write_report(catalog, DEFAULT_OUTPUT_ROOT, crawl_delay)
    for source in selected_sources:
        dictionary_id = source["_id"]
        print(f"Extracting {source['name']} ({dictionary_id}); resume offset is stored per dictionary.", flush=True)
        try:
            progress = extract_dictionary(
                source,
                client,
                DEFAULT_OUTPUT_ROOT,
                page_size=args.page_size,
                max_new_entries=args.max_entries_per_dictionary,
            )
        except PermissionError as error:
            dictionary_path = DEFAULT_OUTPUT_ROOT / dictionary_id
            dictionary_path.mkdir(parents=True, exist_ok=True)
            progress = {
                "dictionary_id": dictionary_id,
                "dictionary_name": source.get("name"),
                "method": "SIWAR public catalog, paginated lexical IDs, public entry-by-ID API",
                "status": "blocked",
                "last_error": str(error),
                "unique_entries_extracted": 0,
                "sense_records_extracted": 0,
            }
            atomic_write_json(dictionary_path / "progress.json", progress)
        except Exception as error:
            dictionary_path = DEFAULT_OUTPUT_ROOT / dictionary_id
            dictionary_path.mkdir(parents=True, exist_ok=True)
            progress_path = dictionary_path / "progress.json"
            progress = {}
            if progress_path.exists():
                progress = json.loads(progress_path.read_text(encoding="utf-8"))
            blocked = isinstance(error, PermissionError) or (
                isinstance(error, requests.HTTPError)
                and error.response is not None
                and error.response.status_code in {401, 403}
            )
            progress.update({"status": "blocked" if blocked else "partial", "last_error": str(error)})
            atomic_write_json(progress_path, progress)
        print(
            f"  status={progress.get('status')} entries={progress.get('unique_entries_extracted', 0)} "
            f"senses={progress.get('sense_records_extracted', 0)} next_offset={progress.get('next_offset', 0)}",
            flush=True,
        )
        _write_report(catalog, DEFAULT_OUTPUT_ROOT, crawl_delay)

    report = build_extraction_report(catalog, DEFAULT_OUTPUT_ROOT, crawl_delay)
    atomic_write_json(REPORT_PATH, report)
    print(f"Extraction report written to {REPORT_PATH}")
    print(f"Public dictionaries inventoried: {len(catalog)}; complete dictionary dumps: "
          f"{sum(source['status'] == 'complete' for source in report['sources'])}")


if __name__ == "__main__":
    main()