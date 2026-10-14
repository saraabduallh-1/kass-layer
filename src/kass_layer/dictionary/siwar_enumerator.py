from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.robotparser import RobotFileParser
from typing import Any

import requests

SIWAR_BASE_URL = "https://siwar.ksaa.gov.sa"
API_BASE_URL = f"{SIWAR_BASE_URL}/api"
ROBOTS_URL = f"{SIWAR_BASE_URL}/robots.txt"
ROBOTS_USER_AGENT = "KassLayerPhase1Extractor"
MINIMUM_CRAWL_DELAY_SECONDS = 5.0
DEFAULT_PAGE_SIZE = 1000
DEFAULT_RECORD_BATCH_SIZE = 25


class PublicApiClient:
    def __init__(self, delay_seconds: float = MINIMUM_CRAWL_DELAY_SECONDS) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": ROBOTS_USER_AGENT,
                "Origin": SIWAR_BASE_URL,
                "Accept": "application/json, text/plain, */*",
            }
        )
        self.delay_seconds = max(MINIMUM_CRAWL_DELAY_SECONDS, delay_seconds)
        self._last_request_at: float | None = None
        self.robots: RobotFileParser | None = None

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self.delay_seconds - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def _check_robots(self, url: str) -> None:
        if self.robots is not None and not self.robots.can_fetch(ROBOTS_USER_AGENT, url):
            raise PermissionError(f"Robots policy disallows public request: {url}")

    def get_text(self, url: str, timeout: int = 60) -> str:
        self._check_robots(url)
        self._wait_for_rate_limit()
        response = self.session.get(url, timeout=timeout)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response.text

    def request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 90,
    ) -> Any:
        self._check_robots(url)
        self._wait_for_rate_limit()
        response = self.session.request(method, url, json=payload, timeout=timeout)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response.json()

    def get_json(self, url: str) -> Any:
        return self.request_json("GET", url)

    def post_json(self, url: str, payload: dict[str, Any]) -> Any:
        return self.request_json("POST", url, payload)

    def load_robots_policy(self) -> float:
        contents = self.get_text(ROBOTS_URL)
        parser = RobotFileParser()
        parser.set_url(ROBOTS_URL)
        parser.parse(contents.splitlines())
        self.robots = parser
        published_delay = parser.crawl_delay(ROBOTS_USER_AGENT)
        if published_delay is None:
            published_delay = parser.crawl_delay("*")
        self.delay_seconds = max(
            MINIMUM_CRAWL_DELAY_SECONDS,
            float(published_delay or 0),
            self.delay_seconds,
        )
        return self.delay_seconds


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary_path.replace(path)


def atomic_write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary_path.replace(path)


def discover_public_dictionaries(client: PublicApiClient) -> list[dict[str, Any]]:
    result = client.get_json(f"{API_BASE_URL}/lexicons/findAll/public")
    if not isinstance(result, list):
        raise ValueError("SIWAR public catalog response was not a list")
    return [source for source in result if source.get("isPublic") is True]


def _page_preferences(offset: int, page_size: int) -> dict[str, Any]:
    return {
        "preferences": {
            "first": offset,
            "rows": page_size,
            "filters": {
                "letterQuery": [{"value": "", "matchMode": "equals", "operator": "and"}],
                "languageCode": [{"value": "", "matchMode": "equals", "operator": "and"}],
                "synsetId": [{"value": [], "matchMode": "in", "operator": "and"}],
            },
            "multisortmeta": [],
        }
    }


def _screen_preferences(page_size: int) -> dict[str, Any]:
    return {
        "preferences": {
            "first": 0,
            "rows": page_size,
            "filters": {
                "languageCode": [{"value": "", "matchMode": "equals", "operator": "and"}]
            },
            "multisortmeta": [],
        }
    }


def _index_path(dictionary_path: Path, offset: int) -> Path:
    return dictionary_path / "index" / f"offset-{offset:09d}.json"


def _records_path(dictionary_path: Path, offset: int, batch_index: int) -> Path:
    batch_suffix = "" if batch_index == 0 else f"-batch-{batch_index:04d}"
    return dictionary_path / "records" / f"offset-{offset:09d}{batch_suffix}.jsonl"


def _next_record_batch_index(dictionary_path: Path, offset: int) -> int:
    records_directory = dictionary_path / "records"
    legacy_path = records_directory / f"offset-{offset:09d}.jsonl"
    batch_paths = list(records_directory.glob(f"offset-{offset:09d}-batch-*.jsonl"))
    indices = [0] if legacy_path.exists() else []
    for path in batch_paths:
        try:
            indices.append(int(path.stem.rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return max(indices, default=-1) + 1


def _progress_path(dictionary_path: Path) -> Path:
    return dictionary_path / "progress.json"


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_existing_records(dictionary_path: Path) -> tuple[set[str], int, int]:
    lexical_entry_ids: set[str] = set()
    sense_count = 0
    invalid_lines = 0
    records_directory = dictionary_path / "records"
    if not records_directory.exists():
        return lexical_entry_ids, sense_count, invalid_lines

    for path in sorted(records_directory.glob("offset-*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    wrapper = json.loads(line)
                    entry = wrapper["entry"]
                    lexical_entry_id = entry["lexicalEntryId"]
                    if lexical_entry_id in lexical_entry_ids:
                        continue
                    lexical_entry_ids.add(lexical_entry_id)
                    sense_count += len(entry.get("senses", []))
                except (KeyError, TypeError, json.JSONDecodeError):
                    invalid_lines += 1
    return lexical_entry_ids, sense_count, invalid_lines


def _new_progress(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "dictionary_id": source["_id"],
        "dictionary_name": source["name"],
        "method": "SIWAR public catalog, paginated lexical IDs, public entry-by-ID API",
        "next_offset": 0,
        "browse_total_rows": None,
        "metadata_total_entries": None,
        "pages_completed": 0,
        "unique_entries_extracted": 0,
        "sense_records_extracted": 0,
        "duplicate_browse_rows": None,
        "status": "partial",
        "last_error": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_progress(source: dict[str, Any], dictionary_path: Path) -> dict[str, Any]:
    path = _progress_path(dictionary_path)
    if path.exists():
        return _read_json(path)
    return _new_progress(source)


def _save_progress(
    progress: dict[str, Any],
    dictionary_path: Path,
    lexical_entry_ids: set[str],
    sense_count: int,
) -> None:
    progress["unique_entries_extracted"] = len(lexical_entry_ids)
    progress["sense_records_extracted"] = sense_count
    progress["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_json(_progress_path(dictionary_path), progress)


def _validate_entry(source_id: str, browse_row: dict[str, Any], entry: Any) -> dict[str, Any]:
    lexical_entry_id = browse_row.get("lexicalEntryId")
    if not isinstance(entry, dict):
        raise ValueError("Public entry response was not an object")
    if entry.get("lexiconId") != source_id:
        raise ValueError("Public entry dictionary ID did not match the browse source")
    if entry.get("lexicalEntryId") != lexical_entry_id:
        raise ValueError("Public entry lexical ID did not match the browse ID")
    if not isinstance(entry.get("senses"), list):
        raise ValueError("Public entry response omitted its senses array")
    return entry


def _dataset_record(
    source: dict[str, Any], browse_row: dict[str, Any], entry: dict[str, Any]
) -> dict[str, Any]:
    dictionary_id = source["_id"]
    dictionary_url = f"{SIWAR_BASE_URL}/public-dict-information/{quote(dictionary_id, safe='')}"
    entry_url = f"{API_BASE_URL}/v2/search/{quote(entry['lexicalEntryId'], safe='')}/get-public-entry"
    return {
        "source": {
            "platform": "SIWAR",
            "dictionary_id": dictionary_id,
            "dictionary_name": source["name"],
            "dictionary_url": dictionary_url,
            "source_url": dictionary_url,
            "entry_api_url": entry_url,
        },
        "browse_index_record": browse_row,
        "entry": entry,
    }


def _request_initial_page(
    client: Any, source_id: str, page_size: int
) -> dict[str, Any]:
    url = (
        f"{API_BASE_URL}/screens/public/get-lexicon-search-screen-data/"
        f"{quote(source_id, safe='')}?languageCode="
    )
    return client.post_json(url, _screen_preferences(page_size))


def _request_page(client: Any, source_id: str, offset: int, page_size: int) -> dict[str, Any]:
    url = f"{API_BASE_URL}/lexicons/{quote(source_id, safe='')}/paginate-words?isPublic=true"
    return client.post_json(url, _page_preferences(offset, page_size))


def _request_entry(client: Any, lexical_entry_id: str) -> dict[str, Any]:
    url = f"{API_BASE_URL}/v2/search/{quote(lexical_entry_id, safe='')}/get-public-entry"
    return client.get_json(url)


def extract_dictionary(
    source: dict[str, Any],
    client: Any,
    output_root: Path,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_new_entries: int | None = None,
    record_batch_size: int = DEFAULT_RECORD_BATCH_SIZE,
) -> dict[str, Any]:
    if record_batch_size < 1:
        raise ValueError("record_batch_size must be greater than zero")
    dictionary_id = source["_id"]
    dictionary_path = output_root / dictionary_id
    dictionary_path.mkdir(parents=True, exist_ok=True)
    progress = _load_progress(source, dictionary_path)
    lexical_entry_ids, sense_count, invalid_lines = _load_existing_records(dictionary_path)
    if invalid_lines:
        progress["status"] = "partial"
        progress["last_error"] = f"Found {invalid_lines} malformed checkpoint record lines"
        _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
        return progress

    new_entries_this_run = 0
    offset = int(progress.get("next_offset", 0))
    if progress.get("browse_total_rows") is not None and offset >= progress["browse_total_rows"]:
        return _finalize_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
    while True:
        index_path = _index_path(dictionary_path, offset)
        if index_path.exists():
            index_page = _read_json(index_path)
        elif offset == 0 and progress.get("browse_total_rows") is None:
            screen_data = _request_initial_page(client, dictionary_id, page_size)
            lexicon = screen_data.get("lexicon", {})
            paginated = screen_data.get("paginated", {})
            index_page = {
                "offset": 0,
                "page_size": page_size,
                "browse_total_rows": paginated.get("totalCount"),
                "metadata_total_entries": lexicon.get("totalEntriesCount"),
                "words": paginated.get("words", []),
            }
            atomic_write_json(index_path, index_page)
        else:
            page_data = _request_page(client, dictionary_id, offset, page_size)
            index_page = {
                "offset": offset,
                "page_size": page_size,
                "browse_total_rows": page_data.get("totalCount"),
                "metadata_total_entries": progress.get("metadata_total_entries"),
                "words": page_data.get("words", []),
            }
            atomic_write_json(index_path, index_page)

        page_total = index_page.get("browse_total_rows")
        words = index_page.get("words", [])
        if not isinstance(page_total, int) or not isinstance(words, list):
            progress["status"] = "partial"
            progress["last_error"] = "Browse API omitted totalCount or words"
            _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
            return progress

        if progress.get("browse_total_rows") is None:
            progress["browse_total_rows"] = page_total
            progress["metadata_total_entries"] = index_page.get("metadata_total_entries")
        elif progress["browse_total_rows"] != page_total:
            progress["browse_total_changed"] = True
            progress["observed_browse_total_rows"] = page_total

        if not words:
            if offset >= page_total:
                progress["next_offset"] = offset
                return _finalize_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
            else:
                progress["status"] = "partial"
                progress["last_error"] = f"Empty browse page before reported total at offset {offset}"
            _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
            return progress

        batch_index = _next_record_batch_index(dictionary_path, offset)
        page_records: list[dict[str, Any]] = []
        page_failure: str | None = None
        for browse_row in words:
            lexical_entry_id = browse_row.get("lexicalEntryId")
            if not lexical_entry_id:
                page_failure = "Browse row omitted lexicalEntryId"
                break
            if lexical_entry_id in lexical_entry_ids:
                continue
            if max_new_entries is not None and new_entries_this_run >= max_new_entries:
                break

            try:
                entry = _validate_entry(
                    dictionary_id,
                    browse_row,
                    _request_entry(client, lexical_entry_id),
                )
            except PermissionError:
                raise
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code in {401, 403}:
                    raise
                page_failure = f"{lexical_entry_id}: {error}"
                break
            except (requests.RequestException, ValueError) as error:
                page_failure = f"{lexical_entry_id}: {error}"
                break

            wrapper = _dataset_record(source, browse_row, entry)
            page_records.append(wrapper)
            lexical_entry_ids.add(lexical_entry_id)
            sense_count += len(entry.get("senses", []))
            new_entries_this_run += 1
            if len(page_records) >= record_batch_size:
                atomic_write_jsonl(_records_path(dictionary_path, offset, batch_index), page_records)
                batch_index += 1
                page_records = []
                progress["current_page_offset"] = offset
                progress["current_page_rows"] = len(words)
                progress["current_page_entries_saved"] = len(lexical_entry_ids)
                _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)

        if page_records:
            atomic_write_jsonl(_records_path(dictionary_path, offset, batch_index), page_records)

        progress["current_page_offset"] = offset
        progress["current_page_rows"] = len(words)
        if page_failure:
            progress["status"] = "partial"
            progress["last_error"] = page_failure
            _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
            return progress

        if max_new_entries is not None and new_entries_this_run >= max_new_entries:
            progress["status"] = "partial"
            progress["stop_reason"] = "entry_limit_for_this_run"
            _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
            return progress

        offset += len(words)
        progress["next_offset"] = offset
        progress["pages_completed"] = int(progress.get("pages_completed", 0)) + 1
        progress["last_error"] = None
        progress.pop("stop_reason", None)
        if offset >= page_total:
            return _finalize_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
        progress["status"] = "partial"
        _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)


def _index_summary(dictionary_path: Path) -> tuple[int, int]:
    total_rows = 0
    unique_ids: set[str] = set()
    index_directory = dictionary_path / "index"
    if not index_directory.exists():
        return total_rows, 0
    for path in sorted(index_directory.glob("offset-*.json")):
        page = _read_json(path)
        for row in page.get("words", []):
            lexical_entry_id = row.get("lexicalEntryId")
            if lexical_entry_id:
                total_rows += 1
                unique_ids.add(lexical_entry_id)
    return total_rows, total_rows - len(unique_ids)


def _finalize_progress(
    progress: dict[str, Any],
    dictionary_path: Path,
    lexical_entry_ids: set[str],
    sense_count: int,
) -> dict[str, Any]:
    index_rows, duplicate_rows = _index_summary(dictionary_path)
    browse_total = progress.get("browse_total_rows")
    unique_browse_entries = index_rows - duplicate_rows
    metadata_total = progress.get("metadata_total_entries")
    progress["index_rows_enumerated"] = index_rows
    progress["unique_browse_entry_ids"] = unique_browse_entries
    progress["duplicate_browse_rows"] = duplicate_rows
    all_pages_indexed = browse_total is not None and index_rows == browse_total
    all_entries_fetched = len(lexical_entry_ids) == unique_browse_entries
    metadata_matches = metadata_total is None or metadata_total == unique_browse_entries
    if (
        int(progress.get("next_offset", 0)) >= int(browse_total or 0)
        and all_pages_indexed
        and all_entries_fetched
        and not progress.get("browse_total_changed")
    ):
        progress["status"] = "complete"
        progress["last_error"] = None
        if not metadata_matches:
            progress["count_warning"] = (
                f"Full public browse index has {unique_browse_entries} unique IDs but lexicon metadata reports "
                f"{metadata_total}; coverage estimate withheld"
            )
        else:
            progress.pop("count_warning", None)
    else:
        progress["status"] = "partial"
        if not all_pages_indexed:
            progress["last_error"] = "Browse index enumeration has not reached its reported total"
        elif not all_entries_fetched:
            progress["last_error"] = "Some unique browse entry IDs are not present in extracted records"
        elif progress.get("browse_total_changed"):
            progress["last_error"] = "Browse total changed during extraction"
    _save_progress(progress, dictionary_path, lexical_entry_ids, sense_count)
    return progress


def build_extraction_report(
    catalog: list[dict[str, Any]], output_root: Path, crawl_delay: float
) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for source in catalog:
        dictionary_id = source["_id"]
        dictionary_path = output_root / dictionary_id
        progress_path = _progress_path(dictionary_path)
        progress = _read_json(progress_path) if progress_path.exists() else _new_progress(source)
        browse_total = progress.get("browse_total_rows")
        metadata_total = progress.get("metadata_total_entries")
        index_rows, duplicate_rows = _index_summary(dictionary_path)
        unique_browse_entries = index_rows - duplicate_rows
        index_complete = browse_total is not None and index_rows == browse_total
        output_location = (
            dictionary_path.relative_to(output_root.parent.parent).as_posix() + "/records/*.jsonl"
        )
        coverage = None
        if (
            progress.get("status") == "complete"
            and not progress.get("browse_total_changed")
            and browse_total is not None
            and metadata_total == unique_browse_entries
            and index_rows == browse_total
            and progress.get("unique_entries_extracted", 0) == unique_browse_entries
        ):
            coverage = 1.0 if unique_browse_entries == 0 else min(
                1.0, progress.get("unique_entries_extracted", 0) / unique_browse_entries
            )
        source_report = {
                "dictionary_name": source.get("name"),
                "dictionary_id": dictionary_id,
                "extraction_method": progress.get("method"),
                "number_of_entries": progress.get("unique_entries_extracted", 0),
                "number_of_senses": progress.get("sense_records_extracted", 0),
                "total_published_entries": metadata_total,
                "public_browse_total_rows": browse_total,
                "unique_browse_entry_ids": unique_browse_entries if index_complete else None,
                "estimated_coverage": coverage,
                "status": progress.get("status", "partial"),
                "json_output_location": output_location,
                "next_browse_offset": progress.get("next_offset", 0),
                "last_error": progress.get("last_error"),
                "total_count_discrepancy": (
                    metadata_total != unique_browse_entries
                    if metadata_total is not None and index_complete
                    else None
                ),
                "count_warning": progress.get("count_warning"),
            }
        if dictionary_id == "Riyadh":
            source_report["alternate_public_interface_url"] = "https://dictionary.ksaa.gov.sa/"
            source_report["alternate_interface_note"] = (
                "The separate Riyadh Dictionary site resolves to the same Riyadh catalog entry; "
                "it is not counted as a second dictionary."
            )
        sources.append(source_report)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": "SIWAR public catalog",
        "public_dictionary_count": len(catalog),
        "rate_limit_seconds": crawl_delay,
        "method": "Enumerate public paginated lexical IDs, then GET each public entry by lexicalEntryId.",
        "coverage_note": "Status complete means every public browse row and distinct lexical-entry ID was enumerated and fetched. Percentage coverage is withheld unless the unique browse IDs reconcile with published metadata.",
        "sources": sources,
    }