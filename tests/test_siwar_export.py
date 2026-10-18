import json

import pytest

from kass_layer.dictionary import siwar_export
from kass_layer.dictionary.siwar_export import (
    dictionary_lock,
    export_dictionary,
    extract_with_retries,
    resolve_dictionaries,
)

CATALOG = [
    {"_id": "Riyadh", "name": "معجم الرياض للغة العربية المعاصرة"},
    {"_id": "dict-one", "name": "معجم  تجريبي"},
]


def _write_raw(raw_root, dictionary_id, entries, status="complete"):
    raw_dir = raw_root / dictionary_id
    (raw_dir / "index").mkdir(parents=True)
    (raw_dir / "records").mkdir()
    words = [{"word": e["lemma"], "lexicalEntryId": e["lexicalEntryId"], "belongsTo": "lemma"} for e in entries]
    (raw_dir / "index" / "offset-000000000.json").write_text(json.dumps({"words": words}), encoding="utf-8")
    with (raw_dir / "records" / "offset-000000000.jsonl").open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps({"source": {}, "browse_index_record": words[0], "entry": entry}, ensure_ascii=False) + "\n")
    (raw_dir / "progress.json").write_text(
        json.dumps({"status": status, "browse_total_rows": len(words), "metadata_total_entries": len(entries)}),
        encoding="utf-8",
    )


def _entry(entry_id, lemma, definition):
    return {
        "_id": f"mongo-{entry_id}",
        "lexicalEntryId": entry_id,
        "lexiconId": "Riyadh",
        "lexiconName": "معجم الرياض للغة العربية المعاصرة",
        "lemma": lemma,
        "root": "ك⦁ت⦁ب",
        "senses": [
            {
                "definition": definition,
                "examples": [{"word": "قرأت الكتاب", "source": "مصدر"}],
                "translations": [{"word": "book", "language": "en"}],
            }
        ],
    }


def test_resolve_aliases_ids_and_names():
    assert resolve_dictionaries(["riyadh"], CATALOG)[0]["_id"] == "Riyadh"
    assert resolve_dictionaries(["dict-one"], CATALOG)[0]["_id"] == "dict-one"
    assert resolve_dictionaries(["معجم تجريبي"], CATALOG)[0]["_id"] == "dict-one"
    with pytest.raises(LookupError):
        resolve_dictionaries(["missing"], CATALOG)


def test_export_writes_one_json_per_dictionary(tmp_path):
    _write_raw(tmp_path / "raw", "Riyadh", [_entry("a", "كِتَاب", "صحف مجموعة"), _entry("b", "كَاتِب", "من يكتب")])
    result = export_dictionary(CATALOG[0], raw_root=tmp_path / "raw", export_dir=tmp_path / "exports")

    payload = json.loads((tmp_path / "exports" / "Riyadh.json").read_text(encoding="utf-8"))
    assert result["status"] == payload["status"] == "complete"
    assert payload["counts"]["entries_extracted"] == 2
    assert [r["term"] for r in payload["records"]] == ["كِتَاب", "كَاتِب"]
    assert payload["records"][0]["examples"][0]["word"] == "قرأت الكتاب"
    assert payload["records"][0]["english_term"] == "book"
    assert payload["records"][0]["root"] == "ك⦁ت⦁ب"


def test_export_marks_partial_extraction(tmp_path):
    _write_raw(tmp_path / "raw", "Riyadh", [_entry("a", "كِتَاب", "صحف")], status="partial")
    result = export_dictionary(CATALOG[0], raw_root=tmp_path / "raw", export_dir=tmp_path / "exports")
    assert result["status"] == "partial"


def test_lock_blocks_second_run(tmp_path):
    with dictionary_lock("Riyadh", raw_root=tmp_path):
        with pytest.raises(RuntimeError):
            with dictionary_lock("Riyadh", raw_root=tmp_path):
                pass
    assert not (tmp_path / "Riyadh" / ".extract.lock").exists()


def test_retries_resume_after_network_error(monkeypatch):
    results = iter([
        {"status": "partial", "last_error": "x: connection reset"},
        {"status": "complete", "last_error": None},
    ])
    calls = []
    monkeypatch.setattr(siwar_export, "extract_dictionary", lambda *a, **k: calls.append(1) or next(results))
    monkeypatch.setattr(siwar_export.time, "sleep", lambda seconds: None)
    progress = extract_with_retries({"_id": "Riyadh"}, client=None, log=lambda message: None)
    assert progress["status"] == "complete"
    assert len(calls) == 2
