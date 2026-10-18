"""Extract any public SIWAR dictionary (including the Riyadh Dictionary) and export it as one JSON file.

The Riyadh Dictionary site (dictionary.ksaa.gov.sa) is a front end over the same SIWAR API
(``https://siwar.ksaa.gov.sa/api``) and appears in the SIWAR public catalog as ``Riyadh``. Its own
``/riyadh/Search/GetLetterWords`` endpoint returns bare word strings without IDs or definitions,
so the complete, ID-stable route for Riyadh is the same browse-index + entry-by-ID API used here.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from contextlib import contextmanager

from kass_layer.dictionary.digital_government import (
    load_browse_rows,
    load_raw_records,
    normalize_records,
)
from kass_layer.dictionary.siwar_enumerator import (
    SIWAR_BASE_URL,
    PublicApiClient,
    _read_json,
    atomic_write_json,
    discover_public_dictionaries,
    extract_dictionary,
)

ROOT = Path(__file__).resolve().parents[3]
RAW_ROOT = ROOT / "data" / "dictionaries" / "raw" / "siwar" / "by_dictionary"
CATALOG_PATH = ROOT / "data" / "dictionaries" / "raw" / "siwar_public_catalog.json"
EXPORT_DIR = ROOT / "data" / "dictionaries" / "exports"
ALIASES = {
    "riyadh": "Riyadh",
    "digital_government": "97ac5360-d65f-425f-974f-9118f09d13a6",
}
ACTIVE_WINDOW_SECONDS = 120


# --------------------------------------------------------------------------- catalog


def load_catalog(refresh: bool = False, client: PublicApiClient | None = None) -> list[dict[str, Any]]:
    if refresh or not CATALOG_PATH.exists():
        client = client or PublicApiClient()
        client.load_robots_policy()
        catalog = discover_public_dictionaries(client)
        atomic_write_json(CATALOG_PATH, catalog)
        return catalog
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def resolve_dictionaries(names: list[str], catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Resolve IDs, aliases (riyadh, digital_government) or exact Arabic names to catalog records."""
    by_id = {source["_id"]: source for source in catalog}
    resolved = []
    for name in names:
        key = ALIASES.get(name.strip().lower(), name.strip())
        source = by_id.get(key) or next(
            (s for s in catalog if " ".join(str(s.get("name", "")).split()) == " ".join(key.split())), None
        )
        if source is None:
            raise LookupError(f"Dictionary not found in the SIWAR public catalog: {name}")
        resolved.append(source)
    return resolved


# --------------------------------------------------------------------------- safety


def recently_active(dictionary_id: str, raw_root: Path = RAW_ROOT) -> bool:
    """True when another process wrote this dictionary's checkpoint in the last couple of minutes."""
    progress_path = raw_root / dictionary_id / "progress.json"
    return progress_path.exists() and time.time() - progress_path.stat().st_mtime < ACTIVE_WINDOW_SECONDS


@contextmanager
def dictionary_lock(dictionary_id: str, raw_root: Path = RAW_ROOT) -> Iterator[None]:
    lock_path = raw_root / dictionary_id / ".extract.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        pid = lock_path.read_text().strip()
        if pid.isdigit() and _pid_alive(int(pid)):
            raise RuntimeError(f"{dictionary_id} is already being extracted by process {pid}")
        lock_path.unlink()  # stale lock from a crashed run
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# --------------------------------------------------------------------------- extraction


def extract_with_retries(
    source: dict[str, Any],
    client: PublicApiClient,
    raw_root: Path = RAW_ROOT,
    max_new_entries: int | None = None,
    retries: int = 5,
    retry_wait_seconds: float = 60.0,
    log=print,
) -> dict[str, Any]:
    """Resume extraction; on a transient network error wait and resume from the last checkpoint."""
    attempt = 0
    while True:
        progress = extract_dictionary(source, client, raw_root, max_new_entries=max_new_entries)
        error = progress.get("last_error")
        if progress.get("status") == "complete":
            return progress
        if max_new_entries is not None and progress.get("stop_reason") == "entry_limit_for_this_run":
            return progress
        if not error or "malformed" in error or attempt >= retries:
            return progress
        attempt += 1
        log(f"  network error, retry {attempt}/{retries} in {retry_wait_seconds:.0f}s: {error}")
        time.sleep(retry_wait_seconds)


# --------------------------------------------------------------------------- export


def _flat_record(record: dict[str, Any]) -> dict[str, Any]:
    morphology = record["morphology"]
    return {
        "entry_id": record["entry_id"],
        "sense_id": record["sense_id"],
        "term": record["term"],
        "term_without_diacritics": record["term_without_diacritics"],
        "definition": record["definition"],
        "english_term": record["english_term"],
        "english_definition": record["english_definition"],
        "part_of_speech": record["part_of_speech"],
        "root": morphology["root"],
        "pattern": morphology["pattern"],
        "lemma_type": morphology["lemma_type"],
        "word_forms": morphology["word_forms"],
        "domain": record["domain"],
        "examples": record["examples"],
        "contexts": record["contexts"],
        "translations": record["translations"],
        "relations": record["semantics"]["relations"],
        "dictionary_id": record["dictionary_id"],
        "dictionary_name": record["dictionary_name"],
        "dictionary_url": record["source_metadata"]["dictionary_url"],
        "source_url": record["source_metadata"]["entry_api_url"],
    }


def export_dictionary(
    source: dict[str, Any], raw_root: Path = RAW_ROOT, export_dir: Path = EXPORT_DIR
) -> dict[str, Any]:
    """Write ``<export_dir>/<dictionary_id>.json`` from whatever raw records are saved so far."""
    dictionary_id = source["_id"]
    raw_dir = raw_root / dictionary_id
    progress_path = raw_dir / "progress.json"
    progress = _read_json(progress_path) if progress_path.exists() else {}
    records, problems = load_raw_records(raw_dir) if (raw_dir / "records").exists() else ([], [])
    if problems:
        raise ValueError(f"{dictionary_id}: {len(problems)} malformed raw lines, e.g. {problems[0]}")
    browse_rows = load_browse_rows(raw_dir) if (raw_dir / "index").exists() else []
    senses = normalize_records(records, browse_rows)

    browse_ids = {row["lexicalEntryId"] for row in browse_rows if row.get("lexicalEntryId")}
    entry_ids = {record["entry_id"] for record in senses} | {
        r["wrapper"]["entry"]["lexicalEntryId"] for r in records
    }
    index_complete = progress.get("browse_total_rows") is not None and len(browse_rows) == progress["browse_total_rows"]
    complete = progress.get("status") == "complete" and index_complete and browse_ids <= entry_ids
    payload = {
        "dictionary_id": dictionary_id,
        "dictionary_name": source.get("name"),
        "dictionary_url": f"{SIWAR_BASE_URL}/public-dict-information/{dictionary_id}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if complete else "partial",
        "counts": {
            "published_entries": progress.get("metadata_total_entries", source.get("totalEntriesCount")),
            "browse_unique_entry_ids_enumerated": len(browse_ids),
            "browse_index_complete": index_complete,
            "entries_extracted": len(entry_ids),
            "senses": len(senses),
            "senses_with_definition": sum(bool((s.get("definition") or "").strip()) for s in senses),
        },
        "records": [_flat_record(record) for record in senses],
    }
    output_path = export_dir / f"{dictionary_id}.json"
    atomic_write_json(output_path, payload)
    return {"path": output_path, **{k: payload[k] for k in ("status", "counts")}}


def dictionary_status(source: dict[str, Any], raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    progress_path = raw_root / source["_id"] / "progress.json"
    progress = _read_json(progress_path) if progress_path.exists() else {}
    return {
        "id": source["_id"],
        "name": " ".join(str(source.get("name", "")).split()),
        "status": progress.get("status", "not_started"),
        "entries": progress.get("unique_entries_extracted", 0),
        "published": progress.get("metadata_total_entries", source.get("totalEntriesCount")),
        "exported": (EXPORT_DIR / f"{source['_id']}.json").exists(),
    }
