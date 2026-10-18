"""Phase 1B: extraction, normalization and validation for the SIWAR Digital Government Dictionary.

Raw records are produced by ``siwar_enumerator.extract_dictionary`` and are never rewritten here.
Normalized records are derived one-per-sense, keyed by ``<lexicalEntryId>:<sense index>``.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from kass_layer.dictionary.siwar_enumerator import (
    API_BASE_URL,
    SIWAR_BASE_URL,
    PublicApiClient,
    _index_summary,
    _read_json,
    atomic_write_json,
    atomic_write_jsonl,
    discover_public_dictionaries,
    extract_dictionary,
)

ROOT = Path(__file__).resolve().parents[3]
DICTIONARY_ID = "97ac5360-d65f-425f-974f-9118f09d13a6"
DICTIONARY_SLUG = "digital_government"
RAW_ROOT = ROOT / "data" / "dictionaries" / "raw" / "siwar" / "by_dictionary"
NORMALIZED_DIR = ROOT / "data" / "dictionaries" / "normalized" / DICTIONARY_SLUG
REPORT_PATH = ROOT / "data" / "dictionaries" / "reports" / f"{DICTIONARY_SLUG}_extraction.json"
NORMALIZED_SCHEMA_VERSION = "1.0"
DICTIONARY_URL = f"{SIWAR_BASE_URL}/public-dict-information/{DICTIONARY_ID}"


# --------------------------------------------------------------------------- extraction


def run_extraction(raw_root: Path, delay_seconds: float) -> dict[str, Any]:
    """Resume extraction for this dictionary only, honouring robots.txt and its crawl delay."""
    client = PublicApiClient(delay_seconds)
    client.load_robots_policy()
    catalog = discover_public_dictionaries(client)
    matches = [source for source in catalog if source.get("_id") == DICTIONARY_ID]
    if not matches:
        raise LookupError(f"Dictionary {DICTIONARY_ID} is not in the public SIWAR catalog")
    source = matches[0]
    dictionary_path = raw_root / DICTIONARY_ID
    atomic_write_json(
        dictionary_path / "catalog_entry.json",
        {"retrieved_at": datetime.now(timezone.utc).isoformat(), "catalog_record": source},
    )
    return extract_dictionary(source, client, raw_root, max_new_entries=None)


# --------------------------------------------------------------------------- raw loading


def load_raw_records(raw_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (records, problems). Records keep file/line provenance; duplicates are reported."""
    records: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    for path in sorted((raw_dir / "records").glob("offset-*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                location = f"{path.relative_to(raw_dir).as_posix()}:{line_number}"
                try:
                    wrapper = json.loads(line)
                    wrapper["entry"]["lexicalEntryId"]
                except (json.JSONDecodeError, KeyError, TypeError) as error:
                    problems.append({"location": location, "problem": f"malformed: {error}"})
                    continue
                records.append(
                    {
                        "wrapper": wrapper,
                        "raw_file": path.relative_to(raw_dir).as_posix(),
                        "raw_line": line_number,
                        "raw_sha256": hashlib.sha256(line.rstrip("\n").encode("utf-8")).hexdigest(),
                    }
                )
    return records, problems


def load_browse_rows(raw_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((raw_dir / "index").glob("offset-*.json")):
        rows.extend(_read_json(path).get("words", []))
    return rows


# --------------------------------------------------------------------------- normalization


def split_translation(word: str | None) -> tuple[str | None, str | None]:
    """SIWAR stores English as ``"<term>|<definition>"``; split on the first pipe only."""
    if not word:
        return None, None
    term, separator, definition = word.partition("|")
    term = term.strip() or None
    definition = definition.strip() or None if separator else None
    return term, definition


def _domain(sense: dict[str, Any]) -> str | None:
    labels: list[str] = []
    for domain in sense.get("domains") or []:
        label = domain.get("label") or domain.get("name") if isinstance(domain, dict) else domain
        if label:
            labels.append(str(label))
    theme_label = (sense.get("theme") or {}).get("label")
    if theme_label:
        labels.append(theme_label)
    return " | ".join(dict.fromkeys(labels)) or None


def normalize_records(
    records: list[dict[str, Any]], browse_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    translation_rows: dict[str, list[str]] = {}
    for row in browse_rows:
        if row.get("belongsTo") == "translation" and row.get("lexicalEntryId"):
            translation_rows.setdefault(row["lexicalEntryId"], []).append(row.get("word"))

    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for record in records:
        wrapper = record["wrapper"]
        entry = wrapper["entry"]
        entry_id = entry["lexicalEntryId"]
        if entry_id in seen:
            continue
        seen.add(entry_id)
        entry_api_url = f"{API_BASE_URL}/v2/search/{quote(entry_id, safe='')}/get-public-entry"
        for sense_index, sense in enumerate(entry.get("senses") or []):
            translations = sense.get("translations") or []
            english = [t for t in translations if t.get("language") == "en"]
            english_term, english_definition = split_translation(english[0]["word"] if english else None)
            normalized.append(
                {
                    "schema_version": NORMALIZED_SCHEMA_VERSION,
                    "entry_id": entry_id,
                    "sense_id": f"{entry_id}:{sense_index}",
                    "sense_index": sense_index,
                    "term": entry.get("lemma"),
                    "term_without_diacritics": entry.get("nonDiacriticsLemma"),
                    "definition": sense.get("definition"),
                    "english_term": english_term,
                    "english_definition": english_definition,
                    "dictionary_id": entry.get("lexiconId"),
                    "dictionary_name": entry.get("lexiconName"),
                    "domain": _domain(sense),
                    "source_url": DICTIONARY_URL,
                    "part_of_speech": entry.get("pos"),
                    "morphology": {
                        "lemma_type": entry.get("lemmaType"),
                        "root": entry.get("root"),
                        "auto_generated_root": entry.get("autoGeneratedRoot"),
                        "pattern": entry.get("pattern"),
                        "word_forms": entry.get("wordForms") or [],
                        "lemma_forms": entry.get("lammaDetails") or [],
                    },
                    "grammar": {
                        "transitivity": sense.get("transitivity"),
                        "level": sense.get("level"),
                    },
                    "semantics": {
                        "synset": sense.get("synset"),
                        "theme": sense.get("theme"),
                        "domains": sense.get("domains") or [],
                        "tags": sense.get("tags") or [],
                        "relations": sense.get("relations") or [],
                        "entry_relations": entry.get("entryRelations") or [],
                    },
                    "examples": sense.get("examples") or [],
                    "contexts": sense.get("contexts") or [],
                    "translations": translations,
                    "source_metadata": {
                        "platform": "SIWAR",
                        "dictionary_url": DICTIONARY_URL,
                        "entry_api_url": entry_api_url,
                        "raw_entry_object_id": entry.get("_id"),
                        "raw_file": record["raw_file"],
                        "raw_line": record["raw_line"],
                        "raw_record_sha256": record["raw_sha256"],
                        "lemma_language": entry.get("lemmaLanguage"),
                        "browse_index_record": wrapper.get("browse_index_record"),
                        "browse_translation_rows": translation_rows.get(entry_id, []),
                        "entry_metadata": entry.get("metaData"),
                        "entry_dynamic_props": entry.get("dynamicProps"),
                        "sense_dynamic_props": sense.get("dynamicProps"),
                    },
                    # Placeholders for later phases; intentionally empty in Phase 1B.
                    "extensions": {
                        "synonyms": [],
                        "aliases": [],
                        "variants": {"foreign": [], "non_standard": []},
                        "number_forms": {"singular": [], "dual": [], "plural": []},
                        "gender_forms": {"masculine": [], "feminine": []},
                        "contextual_examples": [],
                        "verification_status": "source_extracted_unverified",
                        "embedding_refs": [],
                    },
                }
            )
    return normalized


def write_normalized(raw_dir: Path, output_dir: Path) -> dict[str, int]:
    records, problems = load_raw_records(raw_dir)
    if problems:
        raise ValueError(f"Refusing to normalize: {len(problems)} malformed raw lines: {problems[:3]}")
    normalized = normalize_records(records, load_browse_rows(raw_dir))
    jsonl_path = output_dir / f"{DICTIONARY_ID}.senses.jsonl"
    json_path = output_dir / f"{DICTIONARY_ID}.senses.json"
    atomic_write_jsonl(jsonl_path, normalized)
    atomic_write_json(
        json_path,
        {
            "schema_version": NORMALIZED_SCHEMA_VERSION,
            "dictionary_id": DICTIONARY_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(normalized),
            "records": normalized,
        },
    )
    raw_entries = [record["wrapper"] for record in records]
    atomic_write_json(
        raw_dir / "export" / "entries.json",
        {
            "dictionary_id": DICTIONARY_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Verbatim concatenation of records/*.jsonl wrappers; source data is not rewritten.",
            "record_count": len(raw_entries),
            "records": raw_entries,
        },
    )
    return {"raw_entries": len(raw_entries), "normalized_senses": len(normalized)}


# --------------------------------------------------------------------------- validation


def _arabic_problems(text: str | None) -> list[str]:
    if text is None:
        return []
    issues = []
    if "�" in text:
        issues.append("replacement character")
    if any(unicodedata.category(char) == "Cc" and char not in "\n\t" for char in text):
        issues.append("control character")
    if "Ø" in text or "Ù" in text:
        issues.append("possible mojibake")
    return issues


def _has_arabic(text: str | None) -> bool:
    return bool(text) and any("؀" <= char <= "ۿ" for char in text)


def build_report(raw_dir: Path, normalized_dir: Path) -> dict[str, Any]:
    progress = _read_json(raw_dir / "progress.json")
    records, malformed = load_raw_records(raw_dir)
    browse_rows = load_browse_rows(raw_dir)
    index_rows, duplicate_browse_rows = _index_summary(raw_dir)
    browse_ids = {row["lexicalEntryId"] for row in browse_rows if row.get("lexicalEntryId")}
    lemma_ids = {row["lexicalEntryId"] for row in browse_rows if row.get("belongsTo") == "lemma"}
    translation_ids = {row["lexicalEntryId"] for row in browse_rows if row.get("belongsTo") == "translation"}

    raw_id_counts = Counter(record["wrapper"]["entry"]["lexicalEntryId"] for record in records)
    raw_ids = set(raw_id_counts)
    duplicate_raw_ids = sorted(i for i, n in raw_id_counts.items() if n > 1)
    entries = {}
    for record in records:
        entries.setdefault(record["wrapper"]["entry"]["lexicalEntryId"], record["wrapper"])

    attribution_errors = []
    id_mismatch = []
    arabic_issues = []
    for entry_id, wrapper in entries.items():
        entry = wrapper["entry"]
        if entry.get("lexiconId") != DICTIONARY_ID or wrapper["source"].get("dictionary_id") != DICTIONARY_ID:
            attribution_errors.append(entry_id)
        if (wrapper.get("browse_index_record") or {}).get("lexicalEntryId") != entry_id:
            id_mismatch.append(entry_id)
        texts = [entry.get("lemma")] + [s.get("definition") for s in entry.get("senses") or []]
        for text in texts:
            issues = _arabic_problems(text)
            if issues:
                arabic_issues.append({"entry_id": entry_id, "issues": issues})
        if not _has_arabic(entry.get("lemma")):
            arabic_issues.append({"entry_id": entry_id, "issues": ["lemma has no Arabic script"]})

    raw_senses = sum(len(w["entry"].get("senses") or []) for w in entries.values())
    entries_with_definition = sum(
        any((s.get("definition") or "").strip() for s in w["entry"].get("senses") or [])
        for w in entries.values()
    )
    entries_without_senses = sorted(i for i, w in entries.items() if not w["entry"].get("senses"))

    jsonl_path = normalized_dir / f"{DICTIONARY_ID}.senses.jsonl"
    json_path = normalized_dir / f"{DICTIONARY_ID}.senses.json"
    normalized = [json.loads(line) for line in jsonl_path.open(encoding="utf-8")]
    json_export = _read_json(json_path)
    sense_id_counts = Counter(record["sense_id"] for record in normalized)
    duplicate_sense_ids = sorted(i for i, n in sense_id_counts.items() if n > 1)
    expected_sense_ids = {
        f"{entry_id}:{index}" for entry_id, w in entries.items() for index in range(len(w["entry"].get("senses") or []))
    }
    # Raw-to-normalized correspondence: each sense must reproduce the raw text byte-for-byte.
    correspondence_errors = []
    for record in normalized:
        wrapper = entries.get(record["entry_id"])
        if wrapper is None:
            correspondence_errors.append({"sense_id": record["sense_id"], "problem": "no raw entry"})
            continue
        entry = wrapper["entry"]
        sense = (entry.get("senses") or [])[record["sense_index"]]
        if record["term"] != entry.get("lemma") or record["definition"] != sense.get("definition"):
            correspondence_errors.append({"sense_id": record["sense_id"], "problem": "text differs from raw"})
        if record["dictionary_id"] != DICTIONARY_ID:
            correspondence_errors.append({"sense_id": record["sense_id"], "problem": "dictionary_id"})
        if record["source_metadata"]["raw_entry_object_id"] != entry.get("_id"):
            correspondence_errors.append({"sense_id": record["sense_id"], "problem": "raw object id"})

    senses_with_definition = sum(bool((r.get("definition") or "").strip()) for r in normalized)
    senses_with_english = sum(bool(r.get("english_term")) for r in normalized)
    senses_with_domain = sum(bool(r.get("domain")) for r in normalized)
    senses_with_pos = sum(bool(r.get("part_of_speech")) for r in normalized)
    senses_with_examples = sum(bool(r.get("examples")) for r in normalized)

    missing_ids = sorted(browse_ids - raw_ids)
    extra_ids = sorted(raw_ids - browse_ids)
    metadata_total = progress.get("metadata_total_entries")
    browse_total = progress.get("browse_total_rows")

    checks = {
        "browse_index_fully_enumerated": index_rows == browse_total,
        "all_browse_ids_extracted": not missing_ids,
        "no_extracted_ids_outside_browse_index": not extra_ids,
        "no_malformed_raw_lines": not malformed,
        "no_duplicate_raw_entries": not duplicate_raw_ids,
        "dictionary_attribution_correct": not attribution_errors,
        "browse_row_matches_entry_id": not id_mismatch,
        "arabic_text_integrity": not arabic_issues,
        "checkpoint_entry_count_consistent": progress.get("unique_entries_extracted") == len(raw_ids),
        "checkpoint_sense_count_consistent": progress.get("sense_records_extracted") == raw_senses,
        "checkpoint_status_complete": progress.get("status") == "complete",
        "normalized_sense_ids_unique": not duplicate_sense_ids,
        "normalized_covers_every_raw_sense": set(sense_id_counts) == expected_sense_ids,
        "raw_to_normalized_correspondence": not correspondence_errors,
        "json_export_matches_jsonl": json_export.get("records") == normalized,
    }
    all_passed = all(checks.values())
    status = "complete_verified" if all_passed else "partial"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "1B",
        "dictionary_id": DICTIONARY_ID,
        "dictionary_name": progress.get("dictionary_name"),
        "source_url": DICTIONARY_URL,
        "method": progress.get("method"),
        "crawl_delay_seconds": 5,
        "completion_status": status,
        "counts": {
            "published_total_entries_metadata": metadata_total,
            "browse_total_rows": browse_total,
            "browse_rows_enumerated": index_rows,
            "browse_lemma_rows": sum(r.get("belongsTo") == "lemma" for r in browse_rows),
            "browse_translation_rows": sum(r.get("belongsTo") == "translation" for r in browse_rows),
            "duplicate_browse_rows": duplicate_browse_rows,
            "unique_browse_entry_ids": len(browse_ids),
            "unique_entries_extracted": len(raw_ids),
            "raw_record_lines": len(records),
            "total_senses": raw_senses,
            "normalized_sense_records": len(normalized),
            "entries_with_definition": entries_with_definition,
            "senses_with_definition": senses_with_definition,
            "senses_with_english_term": senses_with_english,
            "senses_with_source_domain": senses_with_domain,
            "senses_with_part_of_speech": senses_with_pos,
            "senses_with_examples": senses_with_examples,
            "entries_without_senses": len(entries_without_senses),
        },
        "count_reconciliation": (
            f"The public browse API reports {browse_total} rows. They are {len(lemma_ids)} Arabic lemma rows and "
            f"{len(translation_ids)} English translation rows that point at the same lexical-entry IDs, "
            f"giving {len(browse_ids)} unique IDs. Lexicon metadata reports {metadata_total} entries."
            + (" Unique IDs reconcile with the published count." if metadata_total == len(browse_ids) else
               " Unique IDs do NOT reconcile with the published count; no coverage percentage is claimed.")
        ),
        "missing_or_inaccessible_entry_ids": missing_ids,
        "validation": {
            "all_checks_passed": all_passed,
            "checks": checks,
            "details": {
                "malformed_raw_lines": malformed,
                "duplicate_raw_entry_ids": duplicate_raw_ids,
                "extracted_ids_outside_browse_index": extra_ids,
                "attribution_errors": attribution_errors,
                "browse_id_mismatches": id_mismatch,
                "arabic_text_issues": arabic_issues,
                "duplicate_sense_ids": duplicate_sense_ids,
                "correspondence_errors": correspondence_errors[:50],
                "entries_without_senses": entries_without_senses,
            },
        },
        "checkpoint": {
            key: progress.get(key)
            for key in ("status", "next_offset", "unique_entries_extracted", "sense_records_extracted",
                        "last_error", "updated_at", "count_warning")
        },
        "outputs": {
            "raw_records_jsonl": f"{_rel(raw_dir)}/records/*.jsonl",
            "raw_browse_index": f"{_rel(raw_dir)}/index/*.json",
            "raw_export_json": f"{_rel(raw_dir)}/export/entries.json",
            "normalized_jsonl": _rel(jsonl_path),
            "normalized_json": _rel(json_path),
        },
        "notes": [
            "english_term/english_definition are split from SIWAR translations[].word ('term|definition'); "
            "the unsplit source string is kept in translations.",
            "domain is taken only from sense.domains / sense.theme.label in the source; null when absent.",
            "No enrichment, synonym generation, or embeddings were performed in Phase 1B.",
        ],
    }


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()
