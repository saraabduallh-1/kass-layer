# Kass Layer

A source-aware Arabic terminology pipeline for standardization and retrieval work. The repository is intentionally conservative: it does not invent dictionary records, does not rewrite text, and records when public sources are unavailable or not resolvable.

## Current status

The public SIWAR catalog endpoint exposes 39 public dictionaries. Its browse API enumerates lexical-entry IDs in pages of up to 1,000 rows, and a public entry-by-ID endpoint returns each complete record and its senses. The separate Riyadh Dictionary site also exposes letter-browse and word-search APIs. A matching lemma and definition were verified in both interfaces; the standalone site is treated as an alternate interface to SIWAR's `Riyadh` catalog entry, not as a second dictionary.

The resumable enumerator writes each source dictionary separately to `data/dictionaries/raw/siwar/by_dictionary/{dictionary_id}/records/`, with page indexes and progress checkpoints beside each dataset. Per-dictionary totals, denominator fields, coverage, and status are in `data/dictionaries/raw/siwar_enumeration_report.json`. The earlier verified Riyadh query sample (`siwar_riyadh.json`) and 28-dictionary query sample (`siwar_public_senses.json`) remain intact and are reported separately to avoid overlap.

All 39 dictionaries are currently partial after bounded extraction. The enumerator marks a dictionary `complete` only after every public browse row and distinct lexical-entry ID is fetched. SIWAR's `robots.txt` sets `Crawl-delay: 5`; the enumerator checks that policy and waits at least five seconds between requests. The public API's advertised `totalEntriesCount` values currently sum to 246,241, while the paginator's `totalCount` values sum to 339,091 browse rows. Since those denominators disagree and browse rows may include multiple forms for one lexical entry, percentage coverage is withheld unless the fully enumerated distinct IDs reconcile with the advertised total. The full record API is one-entry-per-request; the browse-row upper-bound implies about 19.6 days of detail requests at the published delay, before overhead. The process is designed to checkpoint and resume, not to label a bounded run complete.

Seed and test fixtures are kept under `tests/fixtures/` and are not included in extraction outputs or statistics.

## Repository layout

- `data/dictionaries/raw` — raw discovery and extraction manifests.
- `data/dictionaries/cleaned` — normalized, deduplicated dictionary records.
- `data/dictionaries/enriched` — enriched terminology variants and relationships.
- `scripts/` — extraction, cleaning, classification, enrichment, embeddings, and evaluation scripts.
- `src/kass_layer/` — reusable pipeline and retrieval code.
- `reports/` — JSON reports and evaluation output.
- `tests/` — validation and regression checks; seed-only fixtures are kept in `tests/fixtures/`.

## Quick commands

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m pytest -q
python scripts/extract/extract_siwar.py
python scripts/extract/enumerate_siwar.py --max-entries-per-dictionary 1
python scripts/extract/enumerate_siwar.py --dictionary-id Riyadh
python scripts/extract/enumerate_siwar.py
python scripts/extract/discover_sources.py
```

`--max-entries-per-dictionary` limits new detail records per source for that invocation. Rerunning the command resumes from saved browse indexes, JSONL datasets, and per-source progress files; omitting the limit runs until the public source is exhausted or an access/data inconsistency stops that dictionary.
