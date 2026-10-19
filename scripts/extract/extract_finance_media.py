"""Extract the Financial & Economic Terms, Media Terms and Qiyas (public-agency performance) dictionaries from SIWAR.

Safe to run while other extractions (e.g. enumerate_siwar.py for Aerospace or Riyadh) are running:
  * writes only inside each target's own folder under data/dictionaries/raw/siwar/by_dictionary/<id>/
    and its export file data/dictionaries/exports/<id>.json;
  * never writes the shared siwar_public_catalog.json or siwar_enumeration_report.json;
  * takes a per-dictionary lock and skips a dictionary whose checkpoint another process updated recently;
  * runs the dictionaries one after the other on a single client, with a default delay of 10s
    (twice the robots.txt crawl delay) because other extractors are hitting SIWAR at the same time.

Commands:
  status [NAME ...]      Show local progress for every target (no network).
                         NAME is a key of TARGETS below (finance, media, qiyas, statistics, ...).
  extract [NAME ...]
                         Resumable extraction then JSON export. With no names, extracts all in order.
  export [NAME ...]
                         Re-export JSON from saved records (no network).

Examples:
  python3 scripts/extract/extract_finance_media.py status
  python3 scripts/extract/extract_finance_media.py extract
  python3 scripts/extract/extract_finance_media.py extract media --delay-seconds 8

Stopping with Ctrl+C is safe: progress is checkpointed and the next run resumes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.siwar_enumerator import (  # noqa: E402
    MINIMUM_CRAWL_DELAY_SECONDS,
    PublicApiClient,
    discover_public_dictionaries,
)
from kass_layer.dictionary.siwar_export import (  # noqa: E402
    CATALOG_PATH,
    dictionary_lock,
    dictionary_status,
    export_dictionary,
    extract_with_retries,
    recently_active,
)

TARGETS = {
    "finance": "4264f8ae-7c51-437d-a6e4-877abad57325",  # معجم المصطلحات المالية والاقتصادية
    "media": "928f4f87-b98c-4b2d-b31d-0b45c6747644",  # معجم مصطلحات الإعلام
    "qiyas": "7806f9cf-4bdb-4c10-b9e5-2705d8945603",  # معجم مصطلحات مركز قياس أداء الأجهزة العامة
    # Overnight queue, most useful for the terminology layer first.
    "statistics": "ee392446-a5df-4b0c-b1e2-f0002b74342d",  # معجم المصطلحات الإحصائية
    "nonprofit": "2885a7fb-c347-4390-92c9-808c9b9b17c2",  # معجم مصطلحات القطاع غير الربحي
    "development": "2932b042-933a-4d5b-af72-8585027ddb6f",  # معجم المصطلحات الإنمائية
    "esports": "54a32a50-2b7e-49c2-9aa4-897f58fae786",  # معجم مصطلحات الرياضات الإلكترونية
    "sports": "ae041c6d-79e6-42c3-b54b-ffbf28c88b9a",  # معجم المصطلحات الرياضية
    "railways": "2813060b-8eda-4c7b-8b10-1fc3255305cb",  # معجم مصطلحات الخطوط الحديدية
    "electric_vehicles": "0f0ad290-0fa5-4983-bb56-7144c641cc8c",  # معجم مصطلحات تصنيع السيارات الكهربائية وصيانتها
    "human_resources": "4fc63968-9cd8-47d9-a32e-aadc6c6a265b",  # معجم مصطلحات الموارد البشرية والتنمية الاجتماعية
    "administrative": "c59be8de-20c3-482b-ab57-ce923dfb4cee",  # معجم المصطلحات الإدارية في المملكة العربية السعودية
    "wildlife": "6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d",  # معجم مصطلحات الحياة الفطرية
    "roads": "94d205e3-6e93-4b6b-a245-1d5304b3ed7d",  # معجم مصطلحات الطرق
    "music": "b4759d02-40ef-4df5-a818-4081a11c338c",  # معجم المصطلحات الموسيقية
    "legal": "0f465c61-2af3-46e6-9ad5-f3a3d4c0bc24",  # معجم المصطلحات القانونية
    "aerospace": "b60a0505-57cb-436a-8a07-75b062de8013",  # معجم مصطلحات علوم هندسة الطيران والفضاء
    "behavioral": "004ce05a-0d56-45e4-a284-1b0358d4cfc4",  # معجم مصطلحات علم السلوك
    "energy": "f990c2a0-f601-466f-8153-2cd35e4710a3",  # معجم مصطلحات الطاقة
    "contracts": "89af196b-70be-4a4b-b193-4b761e0b0fdd",  # قاموس العقود والمشتريات وسلاسل الإمداد
}
DEFAULT_DELAY_SECONDS = 10.0


def _sources(names: list[str], client: PublicApiClient | None = None) -> list[dict]:
    """Catalog records for the requested targets, read from the saved catalog (never rewritten here)."""
    wanted = [TARGETS[name] for name in (names or list(TARGETS))]
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8")) if CATALOG_PATH.exists() else []
    by_id = {source["_id"]: source for source in catalog}
    if any(dictionary_id not in by_id for dictionary_id in wanted):
        if client is None:
            raise SystemExit(f"Not in {CATALOG_PATH.relative_to(ROOT)}; run 'extract' to fetch the catalog in memory.")
        by_id = {source["_id"]: source for source in discover_public_dictionaries(client)}
    missing = [dictionary_id for dictionary_id in wanted if dictionary_id not in by_id]
    if missing:
        raise SystemExit(f"Not in the public SIWAR catalog: {missing}")
    return [by_id[dictionary_id] for dictionary_id in wanted]


def _name(source: dict) -> str:
    return " ".join(str(source.get("name", "")).split())


def _print_export(result) -> None:
    counts = result["counts"]
    print(
        f"  exported {counts['senses']} senses / {counts['entries_extracted']} entries "
        f"(published {counts['published_entries']}) status={result['status']} -> {result['path'].relative_to(ROOT)}",
        flush=True,
    )


def cmd_status(args) -> None:
    for source in _sources(args.dictionaries):
        row = dictionary_status(source)
        active = " (active now)" if recently_active(source["_id"]) else ""
        print(f"{row['status']:<12}{row['entries']:>6} / {row['published'] or '?':<6} {row['name']}{active}")


def cmd_extract(args) -> None:
    client = PublicApiClient(args.delay_seconds)
    robots_delay = client.load_robots_policy()
    print(f"robots.txt crawl delay {robots_delay:.0f}s; this run waits {client.delay_seconds:.0f}s between requests",
          flush=True)
    for source in _sources(args.dictionaries, client):
        dictionary_id = source["_id"]
        print(f"\n== {_name(source)} ({dictionary_id})", flush=True)
        if dictionary_status(source)["status"] == "complete":
            print("  already complete; exporting only.", flush=True)
            _print_export(export_dictionary(source))
            continue
        if recently_active(dictionary_id):
            print("  skipped: another process updated this checkpoint in the last 2 minutes.", flush=True)
            continue
        try:
            with dictionary_lock(dictionary_id):
                progress = extract_with_retries(source, client, retries=args.retries)
        except RuntimeError as error:
            print(f"  skipped: {error}", flush=True)
            continue
        except KeyboardInterrupt:
            print("\n  interrupted; saved batches are kept and the next run resumes from them.", flush=True)
            _print_export(export_dictionary(source))
            raise SystemExit(130)
        except (PermissionError, requests.HTTPError) as error:
            print(f"  blocked: {error}", flush=True)
            continue
        print(f"  status={progress.get('status')} entries={progress.get('unique_entries_extracted')} "
              f"published={progress.get('metadata_total_entries')} last_error={progress.get('last_error')}",
              flush=True)
        _print_export(export_dictionary(source))


def cmd_export(args) -> None:
    for source in _sources(args.dictionaries):
        print(f"== {_name(source)} ({source['_id']})", flush=True)
        _print_export(export_dictionary(source))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("status", cmd_status), ("extract", cmd_extract), ("export", cmd_export)):
        sub = commands.add_parser(name)
        sub.add_argument("dictionaries", nargs="*", metavar="NAME")
        sub.set_defaults(handler=handler)
        if name == "extract":
            sub.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
            sub.add_argument("--retries", type=int, default=5, help="resume attempts after network errors")

    args = parser.parse_args()
    unknown = [name for name in args.dictionaries if name not in TARGETS]
    if unknown:
        parser.error(f"unknown dictionary {unknown}; choose from: {', '.join(TARGETS)}")
    if getattr(args, "delay_seconds", DEFAULT_DELAY_SECONDS) < MINIMUM_CRAWL_DELAY_SECONDS:
        parser.error(f"--delay-seconds cannot be below the robots.txt crawl delay ({MINIMUM_CRAWL_DELAY_SECONDS:.0f}s)")
    args.handler(args)


if __name__ == "__main__":
    main()
