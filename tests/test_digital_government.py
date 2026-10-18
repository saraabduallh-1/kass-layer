import json

from kass_layer.dictionary.digital_government import (
    DICTIONARY_ID,
    build_report,
    split_translation,
    write_normalized,
)


def _entry(entry_id, lemma, definitions, english="Term|An English definition."):
    return {
        "_id": f"mongo-{entry_id}",
        "lexiconName": "معجم مصطلحات الحكومة الرقمية",
        "lexicalEntryId": entry_id,
        "lexiconId": DICTIONARY_ID,
        "lemma": lemma,
        "lemmaType": "MWE",
        "pos": None,
        "root": None,
        "pattern": " ",
        "senses": [
            {
                "definition": definition,
                "translations": [{"word": english, "language": "en"}],
                "domains": [],
                "theme": {"code": None, "label": None},
                "examples": [],
            }
            for definition in definitions
        ],
    }


def _write_raw(raw_dir, entries, metadata_total=None):
    words = []
    for entry in entries:
        words.append({"word": entry["lemma"], "languageCode": "ar", "lexicalEntryId": entry["lexicalEntryId"], "belongsTo": "lemma"})
        words.append({"word": "Term", "languageCode": "en", "lexicalEntryId": entry["lexicalEntryId"], "belongsTo": "translation"})
    (raw_dir / "index").mkdir(parents=True)
    (raw_dir / "records").mkdir()
    (raw_dir / "index" / "offset-000000000.json").write_text(
        json.dumps({"offset": 0, "browse_total_rows": len(words), "words": words}, ensure_ascii=False), encoding="utf-8"
    )
    with (raw_dir / "records" / "offset-000000000.jsonl").open("w", encoding="utf-8") as handle:
        for entry in entries:
            wrapper = {
                "source": {"dictionary_id": DICTIONARY_ID},
                "browse_index_record": {"lexicalEntryId": entry["lexicalEntryId"], "belongsTo": "lemma"},
                "entry": entry,
            }
            handle.write(json.dumps(wrapper, ensure_ascii=False) + "\n")
    senses = sum(len(entry["senses"]) for entry in entries)
    (raw_dir / "progress.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "browse_total_rows": len(words),
                "metadata_total_entries": metadata_total if metadata_total is not None else len(entries),
                "unique_entries_extracted": len(entries),
                "sense_records_extracted": senses,
            }
        ),
        encoding="utf-8",
    )


def test_split_translation_keeps_definition_after_first_pipe():
    assert split_translation("Open Data|Data that is free | open.") == ("Open Data", "Data that is free | open.")
    assert split_translation("Open Data") == ("Open Data", None)
    assert split_translation(None) == (None, None)


def test_normalize_one_record_per_sense_and_verify(tmp_path):
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "normalized"
    _write_raw(raw_dir, [_entry("a", "البيانات المفتوحة", ["تعريف أول", "تعريف ثان"]), _entry("b", "الحوسبة", ["تعريف"])])

    counts = write_normalized(raw_dir, out_dir)
    assert counts == {"raw_entries": 2, "normalized_senses": 3}

    records = [json.loads(line) for line in (out_dir / f"{DICTIONARY_ID}.senses.jsonl").open(encoding="utf-8")]
    assert [r["sense_id"] for r in records] == ["a:0", "a:1", "b:0"]
    assert records[0]["term"] == "البيانات المفتوحة"
    assert records[0]["english_term"] == "Term"
    assert records[0]["domain"] is None
    assert records[0]["source_metadata"]["raw_entry_object_id"] == "mongo-a"
    assert json.loads((out_dir / f"{DICTIONARY_ID}.senses.json").read_text(encoding="utf-8"))["records"] == records

    report = build_report(raw_dir, out_dir)
    assert report["completion_status"] == "complete_verified"
    assert report["counts"]["unique_browse_entry_ids"] == 2
    assert report["counts"]["browse_rows_enumerated"] == 4
    assert report["counts"]["senses_with_definition"] == 3


def test_report_is_partial_when_browse_id_missing(tmp_path):
    raw_dir = tmp_path / "raw"
    out_dir = tmp_path / "normalized"
    _write_raw(raw_dir, [_entry("a", "الحوسبة", ["تعريف"])])
    index_path = raw_dir / "index" / "offset-000000000.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["words"].append({"word": "مفقود", "lexicalEntryId": "missing", "belongsTo": "lemma"})
    index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    write_normalized(raw_dir, out_dir)
    report = build_report(raw_dir, out_dir)
    assert report["completion_status"] == "partial"
    assert report["missing_or_inaccessible_entry_ids"] == ["missing"]
