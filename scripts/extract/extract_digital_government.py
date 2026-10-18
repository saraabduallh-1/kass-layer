"""Phase 1B: complete extraction of the SIWAR Digital Government Dictionary.

Subcommands:
  extract    Resume public browse-index + entry-by-ID extraction (network, honours robots.txt).
  normalize  Build per-sense normalized JSONL + JSON exports from the raw checkpoint records.
  validate   Validate raw/normalized data and write the extraction report.
  flat       Write data/dictionaries/raw/siwar_digital_government.json (flat term list).
  all        Run all steps in order.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.digital_government import (  # noqa: E402
    DICTIONARY_ID,
    NORMALIZED_DIR,
    RAW_ROOT,
    REPORT_PATH,
    build_report,
    write_flat_export,
    run_extraction,
    write_normalized,
)
from kass_layer.dictionary.siwar_enumerator import MINIMUM_CRAWL_DELAY_SECONDS, atomic_write_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["extract", "normalize", "validate", "flat", "all"])
    parser.add_argument("--delay-seconds", type=float, default=MINIMUM_CRAWL_DELAY_SECONDS)
    args = parser.parse_args()
    if args.delay_seconds < MINIMUM_CRAWL_DELAY_SECONDS:
        parser.error("--delay-seconds cannot be less than the published robots.txt crawl delay")

    raw_dir = RAW_ROOT / DICTIONARY_ID
    if args.step in {"extract", "all"}:
        progress = run_extraction(RAW_ROOT, args.delay_seconds)
        print(
            f"extract: status={progress.get('status')} entries={progress.get('unique_entries_extracted')} "
            f"senses={progress.get('sense_records_extracted')} last_error={progress.get('last_error')}",
            flush=True,
        )
    if args.step in {"normalize", "all"}:
        counts = write_normalized(raw_dir, NORMALIZED_DIR)
        print(f"normalize: {counts}", flush=True)
    if args.step in {"validate", "all"}:
        report = build_report(raw_dir, NORMALIZED_DIR)
        atomic_write_json(REPORT_PATH, report)
        print(f"validate: status={report['completion_status']} checks_passed={report['validation']['all_checks_passed']}")
        print(f"report written to {REPORT_PATH.relative_to(ROOT)}")
    if args.step in {"flat", "all"}:
        print(f"flat: {write_flat_export(NORMALIZED_DIR)} records written")


if __name__ == "__main__":
    main()
