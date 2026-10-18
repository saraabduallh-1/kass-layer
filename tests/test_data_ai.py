import json

from kass_layer.dictionary.data_ai import (
    DICTIONARY_ID,
    build_report,
    strip_diacritics,
    write_flat_export,
    write_normalized,
)


def _source(entries):
    counts = {}
    for entry in entries:
        counts[entry["language"]] = counts.get(entry["language"], 0) + 1
    return {
        "metadata": {
            "name": "معجم البيانات والذكاء الاصطناعي",
            "lexiconId": DICTIONARY_ID,
            "retrievedAt": "2026-10-01T00:00:00Z",
            "totalEntries": len(entries),
            "entriesByLanguage": counts,
        },
        "entries": entries,
    }


ENTRIES = [
    {"id": "a", "lemma": "تعلم آلي", "language": "ar", "lemmaType": "MWE", "definition": "تعريف عربي.",
     "translations": [{"language": "eng", "lemma": "Machine Learning", "id": "e"},
                      {"language": "frn", "lemma": "Apprentissage automatique", "id": "f"}]},
    {"id": "e", "lemma": "Machine Learning", "language": "eng", "lemmaType": "MWE", "definition": "English def.",
     "translations": [{"language": "ar", "lemma": "تعلم آلي", "id": "a"}]},
    {"id": "f", "lemma": "Apprentissage automatique", "language": "frn", "lemmaType": "MWE",
     "definition": "Définition.", "translations": [{"language": "ar", "lemma": "تعلم آلي", "id": "a"}]},
]


def _write(tmp_path, entries):
    source = tmp_path / "source.json"
    source.write_text(json.dumps(_source(entries), ensure_ascii=False), encoding="utf-8")
    return source


def test_normalizes_one_sense_per_arabic_entry(tmp_path):
    source = _write(tmp_path, ENTRIES)
    out_dir = tmp_path / "normalized"
    assert write_normalized(source, out_dir) == {"source_entries": 3, "normalized_senses": 1}

    record = json.loads((out_dir / f"{DICTIONARY_ID}.senses.jsonl").read_text(encoding="utf-8"))
    assert record["sense_id"] == "a:0"
    assert record["english_term"] == "Machine Learning"
    assert record["english_definition"] == "English def."
    assert [(t["language"], t["definition"]) for t in record["translations"]] == [
        ("en", "English def."), ("fr", "Définition."),
    ]

    report = build_report(source, out_dir, tmp_path / "no_api")
    assert report["completion_status"] == "complete_verified"
    assert report["counts"]["arabic_concepts"] == 1

    export = tmp_path / "export.json"
    assert write_flat_export(out_dir, export, source) == 1
    assert json.loads(export.read_text(encoding="utf-8"))["records"][0]["term"] == "تعلم آلي"


def test_orphan_translation_makes_report_partial(tmp_path):
    orphan = {"id": "x", "lemma": "Orphan", "language": "eng", "lemmaType": "singleWord",
              "definition": "No Arabic link.", "translations": []}
    source = _write(tmp_path, ENTRIES + [orphan])
    out_dir = tmp_path / "normalized"
    write_normalized(source, out_dir)
    report = build_report(source, out_dir, tmp_path / "no_api")
    assert report["completion_status"] == "partial"
    assert report["validation"]["details"]["orphan_translation_entry_ids"] == ["x"]


def test_strip_diacritics():
    assert strip_diacritics("تَعَلُّم") == "تعلم"
