from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

TECHNICAL_TERMS = {
    "نموذج",
    "تطبيق",
    "تحليل",
    "مؤشر",
    "خوارزمية",
    "بيانات",
    "مستند",
    "بحث",
    "مقاييس",
    "سياسة",
    "مستندات",
    "نظام",
    "إدارة",
    "إحصاء",
    "تقارير",
}

GENERAL_TERMS = {
    "قهوة",
    "كتاب",
    "بيت",
    "مدينة",
    "طفل",
    "طريق",
    "وردة",
}


def normalize_arabic(text: str) -> str:
    """Normalize whitespace and Unicode while preserving original Arabic tokens."""
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    normalized = re.sub("[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]", "", normalized)  # invisible bidi/zero-width marks
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def deduplicate_entries(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for entry in entries:
        term = normalize_arabic(str(entry.get("term", "")))
        definition = normalize_arabic(str(entry.get("definition", "")))
        signature = f"{term}|{definition}|{entry.get('dictionary_name', '')}|{entry.get('source_url', '')}"
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(entry)
    return deduped


def classify_term(term: str) -> str:
    normalized = normalize_arabic(term)
    if not normalized:
        return "general_vocabulary"
    if any(token in normalized for token in TECHNICAL_TERMS):
        return "high_priority"
    if any(token in normalized for token in GENERAL_TERMS):
        return "general_vocabulary"
    if any(token in normalized for token in ("مؤسسة", "عقد", "قانون", "تقرير", "عمل", "أداء")):
        return "medium_priority"
    return "general_vocabulary"


@dataclass
class DictionaryRecord:
    entry_id: str
    term: str
    definition: str
    dictionary_name: str
    source_url: str
    domain: str | None = None
    morphology: dict[str, Any] | None = None
    examples: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "term": self.term,
            "definition": self.definition,
            "dictionary_name": self.dictionary_name,
            "source_url": self.source_url,
            "domain": self.domain,
            "morphology": self.morphology,
            "examples": self.examples,
        }


def write_json_file(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    return target
