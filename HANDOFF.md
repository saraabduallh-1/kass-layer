# Handoff — Kass Layer (2026-10-20)

Arabic terminology layer: rewrites non-specialist Arabic text to the standard SIWAR dictionary terms.
Pipeline: extract → enrich variants → EmbeddingGemma embeddings → Jev decides → Qwen minimal edit.

## Done
- **Extraction:** 22 complete dictionaries, 37,124 entries, 40,102 senses (`data/dictionaries/exports/`).
- **Enrichment pass 1:** every sense reviewed (40,102/40,102); 82,204 variants
  (47,259 accepted, 34,943 need review — mostly forms shared by several terms; never auto-replace those).
  Output: `data/dictionaries/enriched/<dictionary_id>.enriched.json` (originals untouched),
  report `data/dictionaries/enriched/variants/report.json`.
  Raw rows: `variants/raw/generation/` (Qwen drafts), `variants/raw/claude_review/` (final reviews — never edit by hand).
- **Embeddings tool:** `scripts/embeddings/build_embeddings.py` (EmbeddingGemma-300m, resumable, cached by sha256).
  Vectors live in `data/embeddings/` (git-ignored, rebuild in minutes on a GPU).

## In progress / next
1. **Arabic enrichment pass 2** — the user wants many more Arabic-script variants (مودل، داتا، داشبورد…),
   precision first: add only real, useful forms; no addition is fine.
   Tool: `scripts/enrich/arabic_auto.py` (adds on top of current reviews, never deletes; 2 independent generations →
   deterministic filters → judge; every candidate logged in `variants/raw/arabic_auto/`).
   Qwen3.5-4B proved too weak in Arabic (pilot rejected/invented forms), so run it with a stronger local model:
   **Gemma 3 12B** or **ALLaM-7B** via Ollama on the office PC. Pilot 30 senses of the Data & AI dictionary
   (`4cd164a7`) first and audit before any full run. Auto-added forms stay status `review`
   (`AUTO_ARABIC_TRUSTED = False` in `src/kass_layer/dictionary/enrichment.py`) until an audit clears them.
   Planned additions: EmbeddingGemma similarity filter (term vs candidate), several senses per request.
2. Then: Jev replacement decisions, then Qwen minimal edits.

## Office PC setup (Windows 11, RTX 3080 10 GB, Python 3.11)
```
git clone https://github.com/saraabduallh-1/kass-layer.git && cd kass-layer
py -3.11 -m venv .venv
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu130
.venv\Scripts\pip install "sentence-transformers>=5" requests numpy
.venv\Scripts\hf auth login          (Read token; Gemma license accepted on the same HF account)
ollama pull gemma3:12b               (install Ollama for Windows first)
```
`.env` (never commit):
```
QWEN_BASE_URL=http://localhost:11434/v1
QWEN_API_KEY=ollama
QWEN_MODEL=gemma3:12b
```

## Working rules from the user
- Ask before every git commit/push. Keys only in `.env`, never in chat.
- Never modify the original term files. Delete unneeded files. Minimal user involvement.
- Quality over quantity for every variant.
