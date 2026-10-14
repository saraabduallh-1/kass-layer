import json

from kass_layer.dictionary.siwar_enumerator import (
    build_extraction_report,
    extract_dictionary,
)


class FakePublicApiClient:
    def __init__(self, published_total=2):
        self.published_total = published_total
        self.entries = {
            "lexical-one": {
                "_id": "mongo-one",
                "lexicalEntryId": "lexical-one",
                "lexiconId": "dict-one",
                "lemma": "مدخل",
                "senses": [{"definition": "تعريف أول"}, {"definition": "تعريف ثان"}],
            },
            "lexical-two": {
                "_id": "mongo-two",
                "lexicalEntryId": "lexical-two",
                "lexiconId": "dict-one",
                "lemma": "مثال",
                "senses": [{"definition": "تعريف ثالث"}],
            },
        }
        self.entry_calls = []

    def post_json(self, url, payload):
        return {
            "lexicon": {"totalEntriesCount": self.published_total},
            "paginated": {
                "totalCount": 2,
                "words": [
                    {"word": "مدخل", "languageCode": "ar", "lexicalEntryId": "lexical-one", "belongsTo": "lemma"},
                    {"word": "مثال", "languageCode": "ar", "lexicalEntryId": "lexical-two", "belongsTo": "lemma"},
                ],
            },
        }

    def get_json(self, url):
        lexical_entry_id = url.split("/")[-2]
        self.entry_calls.append(lexical_entry_id)
        return self.entries[lexical_entry_id]


def test_enumerator_resumes_without_duplicate_records_and_keeps_all_senses(tmp_path):
    source = {"_id": "dict-one", "name": "معجم اختباري", "isPublic": True}
    client = FakePublicApiClient()

    first_run = extract_dictionary(source, client, tmp_path, page_size=2, max_new_entries=1)
    assert first_run["status"] == "partial"
    assert first_run["unique_entries_extracted"] == 1
    assert first_run["next_offset"] == 0

    second_run = extract_dictionary(source, client, tmp_path, page_size=2)
    assert second_run["status"] == "complete"
    assert second_run["unique_entries_extracted"] == 2
    assert second_run["sense_records_extracted"] == 3
    assert client.entry_calls == ["lexical-one", "lexical-two"]

    output_files = sorted((tmp_path / "dict-one" / "records").glob("offset-*.jsonl"))
    records = [
        json.loads(line)
        for output in output_files
        for line in output.read_text(encoding="utf-8").splitlines()
    ]
    records.sort(key=lambda record: record["entry"]["lexicalEntryId"])
    assert len(records) == 2
    assert records[0]["entry"]["senses"][0]["definition"] == "تعريف أول"
    assert records[0]["entry"]["senses"][1]["definition"] == "تعريف ثان"
    assert records[0]["source"]["dictionary_id"] == "dict-one"


def test_report_withholds_coverage_when_published_and_browse_totals_disagree(tmp_path):
    source = {"_id": "dict-one", "name": "معجم اختباري", "isPublic": True}
    client = FakePublicApiClient(published_total=3)
    extract_dictionary(source, client, tmp_path, page_size=2)

    report = build_extraction_report([source], tmp_path, 5.0)

    assert report["sources"][0]["total_published_entries"] == 3
    assert report["sources"][0]["public_browse_total_rows"] == 2
    assert report["sources"][0]["status"] == "complete"
    assert report["sources"][0]["estimated_coverage"] is None
    assert report["sources"][0]["total_count_discrepancy"] is True