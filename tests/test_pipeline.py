import json
from pathlib import Path

from kass_layer.dictionary.pipeline import (
    classify_term,
    deduplicate_entries,
    normalize_arabic,
)


def test_normalize_arabic_preserves_content():
    assert normalize_arabic('  المودل\t عندي  ') == 'المودل عندي'


def test_deduplicate_entries_removes_exact_duplicates():
    entries = [
        {
            'entry_id': 'A-1',
            'term': 'نموذج',
            'definition': 'أمثلة',
            'dictionary_name': 'seed',
            'source_url': 'https://example.org',
        },
        {
            'entry_id': 'A-2',
            'term': 'نموذج',
            'definition': 'أمثلة',
            'dictionary_name': 'seed',
            'source_url': 'https://example.org',
        },
    ]
    assert len(deduplicate_entries(entries)) == 1


def test_classify_term_marks_technical_entries_as_high_priority():
    assert classify_term('نموذج') == 'high_priority'
    assert classify_term('قهوة') == 'general_vocabulary'


def test_pipeline_manifest_writes_json(tmp_path):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'entries': [{'term': 'نموذج'}]}), encoding='utf-8')
    assert json.loads(manifest.read_text(encoding='utf-8'))['entries'][0]['term'] == 'نموذج'
