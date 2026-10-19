"""Extract SIWAR dictionaries (including the Riyadh Dictionary) and export one JSON file per dictionary.

Commands:
  list                         Show every public SIWAR dictionary with its local extraction status.
  extract DICT [DICT ...]      Resumable extraction, then export to data/dictionaries/exports/<id>.json.
  extract --all                Same, for every public dictionary in the catalog.
  export DICT [DICT ...]       Re-export JSON from what is already saved (no network). Also --all.

DICT is a SIWAR dictionary ID, an exact dictionary name, or an alias: riyadh, digital_government.

Examples:
  python scripts/extract/siwar_tool.py list
  python scripts/extract/siwar_tool.py extract riyadh
  python scripts/extract/siwar_tool.py extract 004ce05a-0d56-45e4-a284-1b0358d4cfc4 --max-entries 500
  python scripts/extract/siwar_tool.py export riyadh

Stopping with Ctrl+C is safe: progress is checkpointed every 25 entries and the next run resumes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.siwar_enumerator import MINIMUM_CRAWL_DELAY_SECONDS, PublicApiClient  # noqa: E402
from kass_layer.dictionary.siwar_export import (  # noqa: E402
    dictionary_lock,
    dictionary_status,
    export_dictionary,
    extract_with_retries,
    load_catalog,
    recently_active,
    resolve_dictionaries,
)


def _selected(args, catalog):
    if args.all:
        return catalog
    if not args.dictionaries:
        raise SystemExit("Name at least one dictionary, or pass --all (see: siwar_tool.py list)")
    try:
        return resolve_dictionaries(args.dictionaries, catalog)
    except LookupError as error:
        raise SystemExit(str(error))


def _print_export(result) -> None:
    counts = result["counts"]
    print(
        f"  exported {counts['senses']} senses / {counts['entries_extracted']} entries "
        f"(published {counts['published_entries']}) status={result['status']} -> {result['path'].relative_to(ROOT)}",
        flush=True,
    )


def cmd_list(args) -> None:
    catalog = load_catalog(refresh=args.refresh)
    print(f"{'status':<12}{'extracted':>10}{'published':>11}  {'json':<5} id / name")
    for source in catalog:
        row = dictionary_status(source)
        published = "?" if row["published"] is None else row["published"]
        print(f"{row['status']:<12}{row['entries']:>10}{published!s:>11}  {'yes' if row['exported'] else '-':<5} "
              f"{row['id']}  {row['name']}")


def cmd_extract(args) -> None:
    client = PublicApiClient(args.delay_seconds)
    delay = client.load_robots_policy()
    print(f"robots.txt crawl delay honoured: {delay:.0f}s between requests", flush=True)
    catalog = load_catalog(refresh=True, client=client)
    for source in _selected(args, catalog):
        dictionary_id = source["_id"]
        name = " ".join(str(source.get("name", "")).split())
        print(f"\n== {name} ({dictionary_id})", flush=True)
        if dictionary_status(source)["status"] == "complete" and not args.force:
            print("  already complete; exporting only (pass --force to re-check against SIWAR).", flush=True)
            if not args.no_export:
                _print_export(export_dictionary(source))
            continue
        if recently_active(dictionary_id) and not args.force:
            print("  skipped: its checkpoint was updated in the last 2 minutes, so another extraction "
                  "seems to be running. Stop it first, or pass --force.", flush=True)
            continue
        try:
            with dictionary_lock(dictionary_id):
                progress = extract_with_retries(
                    source, client, max_new_entries=args.max_entries, retries=args.retries
                )
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
        if not args.no_export:
            _print_export(export_dictionary(source))


def cmd_export(args) -> None:
    catalog = load_catalog()
    for source in _selected(args, catalog):
        print(f"== {' '.join(str(source.get('name', '')).split())} ({source['_id']})", flush=True)
        _print_export(export_dictionary(source))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="list dictionaries and local status")
    list_parser.add_argument("--refresh", action="store_true", help="re-download the public catalog first")
    list_parser.set_defaults(handler=cmd_list)

    for name, handler in (("extract", cmd_extract), ("export", cmd_export)):
        sub = commands.add_parser(name)
        sub.add_argument("dictionaries", nargs="*")
        sub.add_argument("--all", action="store_true", help="every public dictionary in the catalog")
        sub.set_defaults(handler=handler)
        if name == "extract":
            sub.add_argument("--max-entries", type=int, help="stop after this many new entries per dictionary")
            sub.add_argument("--delay-seconds", type=float, default=MINIMUM_CRAWL_DELAY_SECONDS)
            sub.add_argument("--retries", type=int, default=5, help="resume attempts after network errors")
            sub.add_argument("--no-export", action="store_true", help="skip writing the JSON export")
            sub.add_argument("--force", action="store_true", help="re-check complete dictionaries and run even if another run looks active")

    args = parser.parse_args()
    if getattr(args, "delay_seconds", MINIMUM_CRAWL_DELAY_SECONDS) < MINIMUM_CRAWL_DELAY_SECONDS:
        parser.error("--delay-seconds cannot be below the published robots.txt crawl delay (5s)")
    if getattr(args, "max_entries", None) is not None and args.max_entries < 1:
        parser.error("--max-entries must be greater than zero")
    args.handler(args)


if __name__ == "__main__":
    main()
