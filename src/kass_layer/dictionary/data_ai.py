"""Normalization and validation for the SIWAR Data and AI Dictionary (معجم البيانات والذكاء الاصطناعي).

The source is a full SIWAR export saved verbatim at ``data/dictionaries/raw/siwar_data_ai_dictionary.json``
and is never rewritten here. It lists every lemma as its own entry in one of four languages (ar, eng,
frn, esp); non-Arabic entries link back to Arabic ones through ``translations``. Each Arabic entry is
one concept and becomes one normalized sense record, keyed by ``<entry id>:0`` and using the same
schema as the Digital Government Dictionary.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from kass_layer.dictionary.digital_government import (
    NORMALIZED_SCHEMA_VERSION,
    _arabic_problems,
    _has_arabic,
    _rel,
    load_raw_records,
)
from kass_layer.dictionary.siwar_enumerator import (
    API_BASE_URL,
    SIWAR_BASE_URL,
    _read_json,
    atomic_write_json,
    atomic_write_jsonl,
)
from kass_layer.dictionary.siwar_export import _flat_record

ROOT = Path(__file__).resolve().parents[3]
DICTIONARY_ID = "4cd164a7-7160-4de8-af5c-34382f5da657"
DICTIONARY_SLUG = "data_ai"
SOURCE_PATH = ROOT / "data" / "dictionaries" / "raw" / "siwar_data_ai_dictionary.json"
API_RAW_DIR = ROOT / "data" / "dictionaries" / "raw" / "siwar" / "by_dictionary" / DICTIONARY_ID
NORMALIZED_DIR = ROOT / "data" / "dictionaries" / "normalized" / DICTIONARY_SLUG
EXPORT_PATH = ROOT / "data" / "dictionaries" / "exports" / f"{DICTIONARY_ID}.json"
REPORT_PATH = ROOT / "data" / "dictionaries" / "reports" / f"{DICTIONARY_SLUG}_extraction.json"
MANIFEST_PATH = ROOT / "data" / "dictionaries" / "manifests" / "technology_engineering_science.json"
DICTIONARY_URL = f"{SIWAR_BASE_URL}/public-dict-information/{DICTIONARY_ID}"
LANGUAGE_CODES = {"ar": "ar", "eng": "en", "frn": "fr", "esp": "es"}
ARABIC_DIACRITICS = re.compile("[ً-ْٰـ]")


# --------------------------------------------------------------------------- source loading


def load_source(source_path: Path = SOURCE_PATH) -> dict[str, Any]:
    payload = _read_json(source_path)
    if payload.get("metadata", {}).get("lexiconId") != DICTIONARY_ID:
        raise ValueError(f"{source_path} is not the Data and AI Dictionary ({DICTIONARY_ID})")
    return payload


def _sha256(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strip_diacritics(text: str | None) -> str | None:
    return ARABIC_DIACRITICS.sub("", text) if text else text


# --------------------------------------------------------------------------- normalization


def _resolve_translations(entry: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    resolved = []
    for link in entry.get("translations") or []:
        target = by_id.get(link.get("id"))
        resolved.append(
            {
                "language": LANGUAGE_CODES.get(link.get("language"), link.get("language")),
                "word": link.get("lemma"),
                "definition": target.get("definition") if target else None,
                "entry_id": link.get("id"),
                "lemma_type": target.get("lemmaType") if target else None,
                "resolved": target is not None,
            }
        )
    return resolved


def normalize_source(payload: dict[str, Any], source_file: str) -> list[dict[str, Any]]:
    metadata = payload["metadata"]
    entries = payload["entries"]
    by_id = {entry["id"]: entry for entry in entries}
    normalized: list[dict[str, Any]] = []
    for position, entry in enumerate(entries):
        if entry.get("language") != "ar":
            continue
        entry_id = entry["id"]
        translations = _resolve_translations(entry, by_id)
        english = [t for t in translations if t["language"] == "en"]
        normalized.append(
            {
                "schema_version": NORMALIZED_SCHEMA_VERSION,
                "entry_id": entry_id,
                "sense_id": f"{entry_id}:0",
                "sense_index": 0,
                "term": entry.get("lemma"),
                "term_without_diacritics": strip_diacritics(entry.get("lemma")),
                "definition": entry.get("definition"),
                "english_term": english[0]["word"] if english else None,
                "english_definition": english[0]["definition"] if english else None,
                "dictionary_id": metadata["lexiconId"],
                "dictionary_name": metadata.get("name"),
                "domain": None,
                "source_url": DICTIONARY_URL,
                "part_of_speech": entry.get("pos"),
                "morphology": {
                    "lemma_type": entry.get("lemmaType"),
                    "root": None,
                    "auto_generated_root": None,
                    "pattern": None,
                    "word_forms": [],
                    "lemma_forms": [],
                },
                "grammar": {"transitivity": None, "level": None},
                "semantics": {
                    "synset": None,
                    "theme": None,
                    "domains": [],
                    "tags": [],
                    "relations": [],
                    "entry_relations": [],
                },
                "examples": [],
                "contexts": [],
                "translations": translations,
                "source_metadata": {
                    "platform": "SIWAR",
                    "dictionary_url": DICTIONARY_URL,
                    "entry_api_url": f"{API_BASE_URL}/v2/search/{quote(entry_id, safe='')}/get-public-entry",
                    "raw_entry_object_id": entry_id,
                    "raw_file": source_file,
                    "raw_entry_index": position,
                    "raw_record_sha256": _sha256(entry),
                    "lemma_language": entry.get("language"),
                    "source_retrieved_at": metadata.get("retrievedAt"),
                    "source_translation_links": entry.get("translations") or [],
                    "authors": metadata.get("authors") or [],
                    "partners": metadata.get("partners") or [],
                },
                # Placeholders for later phases; intentionally empty here.
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


def write_normalized(source_path: Path = SOURCE_PATH, output_dir: Path = NORMALIZED_DIR) -> dict[str, int]:
    payload = load_source(source_path)
    normalized = normalize_source(payload, _rel(source_path))
    atomic_write_jsonl(output_dir / f"{DICTIONARY_ID}.senses.jsonl", normalized)
    atomic_write_json(
        output_dir / f"{DICTIONARY_ID}.senses.json",
        {
            "schema_version": NORMALIZED_SCHEMA_VERSION,
            "dictionary_id": DICTIONARY_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(normalized),
            "records": normalized,
        },
    )
    return {"source_entries": len(payload["entries"]), "normalized_senses": len(normalized)}


def _load_normalized(normalized_dir: Path) -> list[dict[str, Any]]:
    jsonl_path = normalized_dir / f"{DICTIONARY_ID}.senses.jsonl"
    return [json.loads(line) for line in jsonl_path.open(encoding="utf-8")]


# --------------------------------------------------------------------------- validation


def build_report(
    source_path: Path = SOURCE_PATH, normalized_dir: Path = NORMALIZED_DIR, api_raw_dir: Path = API_RAW_DIR
) -> dict[str, Any]:
    payload = load_source(source_path)
    metadata = payload["metadata"]
    entries = payload["entries"]
    id_counts = Counter(entry.get("id") for entry in entries)
    by_id = {entry["id"]: entry for entry in entries}
    arabic = [entry for entry in entries if entry.get("language") == "ar"]
    language_counts = Counter(entry.get("language") for entry in entries)

    linked_from_arabic = {link["id"] for entry in arabic for link in entry.get("translations") or []}
    orphan_translations = sorted(
        entry["id"] for entry in entries if entry.get("language") != "ar" and entry["id"] not in linked_from_arabic
    )
    unresolved_links = [
        {"entry_id": entry["id"], "term": entry["lemma"], "link": link}
        for entry in arabic
        for link in entry.get("translations") or []
        if link.get("id") not in by_id
    ]
    multiple_english = [
        {"entry_id": entry["id"], "term": entry["lemma"],
         "english_terms": [l["lemma"] for l in entry["translations"] if l.get("language") == "eng"]}
        for entry in arabic
        if sum(l.get("language") == "eng" for l in entry.get("translations") or []) > 1
    ]
    arabic_issues = []
    for entry in arabic:
        for text in (entry.get("lemma"), entry.get("definition")):
            issues = _arabic_problems(text)
            if issues:
                arabic_issues.append({"entry_id": entry["id"], "issues": issues})
        if not _has_arabic(entry.get("lemma")):
            arabic_issues.append({"entry_id": entry["id"], "issues": ["lemma has no Arabic script"]})
    duplicate_arabic_terms = sorted(t for t, n in Counter(e["lemma"] for e in arabic).items() if n > 1)

    normalized = _load_normalized(normalized_dir)
    json_export = _read_json(normalized_dir / f"{DICTIONARY_ID}.senses.json")
    sense_id_counts = Counter(record["sense_id"] for record in normalized)
    correspondence_errors = []
    for record in normalized:
        entry = by_id.get(record["entry_id"])
        if entry is None:
            correspondence_errors.append({"sense_id": record["sense_id"], "problem": "no source entry"})
        elif record["term"] != entry.get("lemma") or record["definition"] != entry.get("definition"):
            correspondence_errors.append({"sense_id": record["sense_id"], "problem": "text differs from source"})
        elif record["source_metadata"]["raw_record_sha256"] != _sha256(entry):
            correspondence_errors.append({"sense_id": record["sense_id"], "problem": "source hash"})

    # The earlier API sample must agree with this export: same IDs, same lemma once diacritics are removed.
    api_records, _ = load_raw_records(api_raw_dir) if (api_raw_dir / "records").exists() else ([], [])
    api_entries = {r["wrapper"]["entry"]["lexicalEntryId"]: r["wrapper"]["entry"] for r in api_records}
    api_disagreements = [
        {"entry_id": entry_id, "api_lemma": api_entry.get("lemma"),
         "export_lemma": by_id.get(entry_id, {}).get("lemma")}
        for entry_id, api_entry in api_entries.items()
        if entry_id not in by_id
        or strip_diacritics(api_entry.get("nonDiacriticsLemma") or api_entry.get("lemma")).strip()
        != strip_diacritics(by_id[entry_id]["lemma"]).strip()
    ]

    checks = {
        "entry_count_matches_metadata": len(entries) == metadata.get("totalEntries"),
        "language_counts_match_metadata": dict(language_counts) == metadata.get("entriesByLanguage"),
        "source_entry_ids_unique": all(n == 1 for n in id_counts.values()),
        "every_entry_has_definition": all((e.get("definition") or "").strip() for e in entries),
        "every_translation_entry_linked_to_arabic": not orphan_translations,
        "arabic_text_integrity": not arabic_issues,
        "normalized_sense_ids_unique": all(n == 1 for n in sense_id_counts.values()),
        "normalized_covers_every_arabic_entry": set(sense_id_counts) == {f"{e['id']}:0" for e in arabic},
        "source_to_normalized_correspondence": not correspondence_errors,
        "json_export_matches_jsonl": json_export.get("records") == normalized,
        "agrees_with_siwar_api_sample": not api_disagreements,
    }
    all_passed = all(checks.values())
    english_linked = sum(bool(r["english_term"]) for r in normalized)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dictionary_id": DICTIONARY_ID,
        "dictionary_name": metadata.get("name"),
        "source_url": metadata.get("source", DICTIONARY_URL),
        "method": "Complete SIWAR dictionary export supplied as one JSON file; normalized locally.",
        "source_retrieved_at": metadata.get("retrievedAt"),
        "completion_status": "complete_verified" if all_passed else "partial",
        "counts": {
            "published_total_entries_metadata": metadata.get("totalEntries"),
            "source_entries": len(entries),
            "source_entries_by_language": dict(language_counts),
            "arabic_concepts": len(arabic),
            "normalized_sense_records": len(normalized),
            "senses_with_definition": sum(bool((r.get("definition") or "").strip()) for r in normalized),
            "senses_with_english_term": english_linked,
            "senses_with_french_term": sum(any(t["language"] == "fr" for t in r["translations"]) for r in normalized),
            "senses_with_spanish_term": sum(any(t["language"] == "es" for t in r["translations"]) for r in normalized),
            "senses_with_part_of_speech": sum(bool(r.get("part_of_speech")) for r in normalized),
            "lemma_types": dict(Counter(r["morphology"]["lemma_type"] for r in normalized)),
            "siwar_api_sample_entries_cross_checked": len(api_entries),
        },
        "count_reconciliation": (
            f"The source lists {len(entries)} entries across four languages "
            f"({', '.join(f'{k}={v}' for k, v in language_counts.items())}). Non-Arabic entries are translations "
            f"linked to Arabic entries, so the dictionary holds {len(arabic)} Arabic concepts, each normalized "
            "as one sense record."
        ),
        "validation": {
            "all_checks_passed": all_passed,
            "checks": checks,
            "details": {
                "orphan_translation_entry_ids": orphan_translations,
                "arabic_text_issues": arabic_issues,
                "correspondence_errors": correspondence_errors[:50],
                "siwar_api_disagreements": api_disagreements,
            },
        },
        "source_data_warnings": {
            "unresolved_translation_links": unresolved_links,
            "entries_with_multiple_english_terms": multiple_english,
            "duplicate_arabic_terms": duplicate_arabic_terms,
            "arabic_entries_without_english": [r["entry_id"] for r in normalized if not r["english_term"]],
        },
        "outputs": {
            "source_json": _rel(source_path),
            "normalized_jsonl": _rel(normalized_dir / f"{DICTIONARY_ID}.senses.jsonl"),
            "normalized_json": _rel(normalized_dir / f"{DICTIONARY_ID}.senses.json"),
            "flat_export_json": _rel(EXPORT_PATH),
        },
        "notes": [
            "Language codes are mapped to ISO 639-1 (eng→en, frn→fr, esp→es); each translation keeps its own "
            "definition and SIWAR entry ID.",
            "english_term/english_definition come from the first linked English entry; entries with several "
            "English terms are listed under source_data_warnings.",
            "The source has no domain, root, pattern or example fields; those stay empty rather than inferred.",
            "No enrichment, synonym generation, or embeddings were performed.",
        ],
    }


# --------------------------------------------------------------------------- exports


def write_flat_export(normalized_dir: Path = NORMALIZED_DIR, output_path: Path = EXPORT_PATH,
                      source_path: Path = SOURCE_PATH) -> int:
    """Write the flat export in the same layout as ``siwar_export.export_dictionary``."""
    metadata = load_source(source_path)["metadata"]
    senses = _load_normalized(normalized_dir)
    payload = {
        "dictionary_id": DICTIONARY_ID,
        "dictionary_name": metadata.get("name"),
        "dictionary_url": DICTIONARY_URL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete",
        "counts": {
            "published_entries": metadata.get("totalEntries"),
            "source_entries": metadata.get("totalEntries"),
            "arabic_concepts": len(senses),
            "entries_extracted": len(senses),
            "senses": len(senses),
            "senses_with_definition": sum(bool((s.get("definition") or "").strip()) for s in senses),
        },
        "records": [_flat_record(record) for record in senses],
    }
    atomic_write_json(output_path, payload)
    return len(senses)


def update_manifest(report: dict[str, Any], manifest_path: Path = MANIFEST_PATH) -> None:
    manifest = _read_json(manifest_path)
    counts = report["counts"]
    for item in manifest["dictionaries"]:
        if item["dictionary_id"] != DICTIONARY_ID:
            continue
        item.update(
            {
                "normalized_jsonl": report["outputs"]["normalized_jsonl"],
                "source_json": report["outputs"]["source_json"],
                "entries_extracted": counts["arabic_concepts"],
                "senses_extracted": counts["normalized_sense_records"],
                "senses_with_definitions": counts["senses_with_definition"],
                "status": "complete" if report["completion_status"] == "complete_verified" else "partial",
                "notes": "Normalized from the complete SIWAR export (siwar_data_ai_dictionary.json); "
                         f"{counts['source_entries']} entries across ar/en/fr/es, "
                         f"{counts['arabic_concepts']} Arabic concepts.",
            }
        )
        break
    else:
        raise LookupError(f"{DICTIONARY_ID} is not listed in {manifest_path}")
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(manifest_path, manifest)
