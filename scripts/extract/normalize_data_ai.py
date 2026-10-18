"""Normalize the SIWAR Data and AI Dictionary from data/dictionaries/raw/siwar_data_ai_dictionary.json.

Subcommands:
  normalize  Build per-sense normalized JSONL + JSON from the source export.
  validate   Validate source/normalized data, write the report and update the manifest.
  flat       Write data/dictionaries/exports/<dictionary id>.json (flat term list).
  all        Run all steps in order.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.data_ai import (  # noqa: E402
    REPORT_PATH,
    build_report,
    update_manifest,
    write_flat_export,
    write_normalized,
)
from kass_layer.dictionary.siwar_enumerator import atomic_write_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["normalize", "validate", "flat", "all"])
    args = parser.parse_args()

    if args.step in {"normalize", "all"}:
        print(f"normalize: {write_normalized()}", flush=True)
    if args.step in {"validate", "all"}:
        report = build_report()
        atomic_write_json(REPORT_PATH, report)
        update_manifest(report)
        print(f"validate: status={report['completion_status']} checks_passed={report['validation']['all_checks_passed']}")
        print(f"report written to {REPORT_PATH.relative_to(ROOT)}")
    if args.step in {"flat", "all"}:
        print(f"flat: {write_flat_export()} records written")


if __name__ == "__main__":
    main()
