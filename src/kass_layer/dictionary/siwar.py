from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

SIWAR_BASE_URL = "https://siwar.ksaa.gov.sa"
RIYADH_DICTIONARY_ID = "Riyadh"
RIYADH_DICTIONARY_NAME = "معجم الرياض للغة العربية المعاصرة"


def search_url(query: str) -> str:
    return f"{SIWAR_BASE_URL}/result-page-public/{quote(query, safe='')}?searchType=lemma"


def _text(node: Tag | None) -> str | None:
    if node is None:
        return None
    value = " ".join(node.stripped_strings)
    return value or None


def _sense_number(sense: Tag) -> str | None:
    label = sense.select_one(".text-justify")
    if label is None:
        return None
    match = re.match(r"\s*([٠-٩0-9]+)\s*[.)]", label.get_text(" ", strip=True))
    return match.group(1) if match else None


def parse_siwar_entries(
    html: str,
    query: str,
    dictionary_id: str | None = None,
) -> list[dict[str, Any]]:
    """Parse source-identified senses from SIWAR's rendered public result page."""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict[str, Any]] = []

    for card in soup.select(".lexical-entry-card"):
        lemma = _text(card.select_one(".lemma"))
        if not lemma:
            continue

        for details in card.select(".lexical-entry-card__details"):
            dictionary_link = details.select_one('a[href*="/public-dict-information/"]')
            if dictionary_link is None:
                continue
            dictionary_href = urlparse(dictionary_link.get("href", "")).path.rstrip("/")
            source_dictionary_id = dictionary_href.rsplit("/", 1)[-1]
            if not source_dictionary_id or (
                dictionary_id is not None and source_dictionary_id != dictionary_id
            ):
                continue

            details_id = details.get("id", "")
            entry_id, marker, details_dictionary_id = details_id.partition("_DICT_")
            if not marker or details_dictionary_id != source_dictionary_id or not entry_id:
                continue

            morphology = [
                value
                for item in details.select(".pos-style .item")
                if (value := _text(item))
            ]

            for sense in details.select(".lexical-entry-card__details__sense"):
                definition = _text(sense.select_one('[ptooltip="التعريف"]'))
                if not definition:
                    continue

                translations = []
                for translation in sense.select(
                    ".lexical-entry-card__details__sense__translation"
                ):
                    language = _text(translation.select_one(".trans-flag"))
                    value = _text(translation.select_one(".trans-text"))
                    if language and value:
                        translations.append({"language": language, "text": value})

                dictionary_href = f"/public-dict-information/{source_dictionary_id}"
                records.append(
                    {
                        "entry_id": entry_id,
                        "sense_number": _sense_number(sense),
                        "term": lemma,
                        "definition": definition,
                        "dictionary_id": source_dictionary_id,
                        "dictionary_name": _text(dictionary_link),
                        "source_url": search_url(query),
                        "dictionary_url": f"{SIWAR_BASE_URL}{dictionary_href}",
                        "domain": None,
                        "semantic_field": _text(sense.select_one(".synset-badge")),
                        "morphology": morphology or None,
                        "example": _text(sense.select_one(".lexical-entry-example")),
                        "translations": translations,
                        "extraction_query": query,
                    }
                )

    return records


def limit_entries(records: list[dict[str, Any]], max_entries: int) -> list[dict[str, Any]]:
    """Limit by unique source entry while retaining every parsed sense per entry."""
    selected_ids: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for record in records:
        dictionary_id = record["dictionary_id"]
        identity = (dictionary_id, record["entry_id"])
        if identity in selected_ids:
            continue
        if counts.get(dictionary_id, 0) < max_entries:
            selected_ids.add(identity)
            counts[dictionary_id] = counts.get(dictionary_id, 0) + 1
    return [
        record
        for record in records
        if (record["dictionary_id"], record["entry_id"]) in selected_ids
    ]