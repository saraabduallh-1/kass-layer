# Kass Layer

A source-aware Arabic terminology pipeline for standardization and retrieval work. The repository is intentionally conservative: it does not invent dictionary records, does not rewrite text, and records when public sources are unavailable or not resolvable.

## Current status

Public discovery for the official King Salman Global Academy dictionary platform is incomplete in this environment. The live checks performed during setup show:

- `https://siwar.sa` resolves but is a child hospitality website, not an Arabic dictionary portal.
- `https://arabicacademy.gov.sa` and related Academy domain variants do not resolve from this environment.
- `https://riyadhdictionary.com` and related `riyadh` dictionary domains do not resolve from this environment.

Because the Academy sources are not actually reachable here, the repository records the source state in the discovery report and continues with the pipeline scaffold, validation, and retrieval logic without fabricating missing entries.

## Repository layout

- `data/dictionaries/raw` — raw discovery and extraction manifests.
- `data/dictionaries/cleaned` — normalized, deduplicated dictionary records.
- `data/dictionaries/enriched` — enriched terminology variants and relationships.
- `scripts/` — extraction, cleaning, classification, enrichment, embeddings, and evaluation scripts.
- `src/kass_layer/` — reusable pipeline and retrieval code.
- `reports/` — JSON reports and evaluation output.
- `tests/` — validation and regression checks.

## Quick commands

```bash
/usr/local/bin/python3 -m pytest -q
/usr/local/bin/python3 scripts/extract/discover_sources.py
/usr/local/bin/python3 scripts/clean/run_clean.py
/usr/local/bin/python3 scripts/classify/run_classify.py
/usr/local/bin/python3 scripts/enrich/run_enrich.py
/usr/local/bin/python3 scripts/embeddings/build_embedding_manifest.py
```
