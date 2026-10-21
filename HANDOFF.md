# Handoff — Kass Layer (updated 2026-10-20)

Arabic terminology layer: rewrites non-specialist Arabic text to the standard SIWAR dictionary terms,
e.g. «المودل تدرب على بيانات» → «النموذج تدرب على بيانات».
Pipeline (user's order): extract → enrich variants → EmbeddingGemma embeddings → Jev decides → Qwen minimal edit.

## Done
- **Extraction:** 22 complete dictionaries, 37,124 entries, 40,102 senses (`data/dictionaries/exports/`).
- **Enrichment pass 1:** every sense reviewed (40,102/40,102); 82,204 variants
  (61,498 foreign, 10,284 informal Arabic, 5,684 abbreviations, 2,624 transliterations, 1,345 colloquial, 767 spelling;
  47,259 accepted, 34,943 need review — mostly forms shared by several terms; never auto-replace those).
  Output: `data/dictionaries/enriched/<dictionary_id>.enriched.json` (originals untouched),
  report `data/dictionaries/enriched/variants/report.json`.
  Raw rows: `variants/raw/generation/` (Qwen drafts), `variants/raw/claude_review/` (final reviews — never edit by hand).
- **Embeddings:** `scripts/embeddings/build_embeddings.py` (EmbeddingGemma-300m; resumable, checkpoints every 2,048 texts,
  cached by sha256 so later runs encode only new texts). Built on the Mac: 122,306 texts (100,688 unique), 188 MB,
  ~70 texts/s. Vectors are git-ignored (`data/embeddings/`) — rebuild on the PC with `build` (minutes on the RTX 3080).
  Search trials: «الداتا»→بيانات, «داشبورد»→لوحة المعلومات, «المقاول من الباطن»→مقاول الباطن, and a fashion
  sentence did NOT match «نموذج» (context works). Weak spot: whole-sentence queries dilute the word
  («المودل تدرب…» put «نموذج» 4th) → extract the candidate word first, then rank only its candidate terms.
  Also: same term repeated across dictionaries; a few weak pass-1 variants (e.g. «have numbers») surfaced.

## Status 2026-10-21: pass 2 runs unattended on the office PC (user away for days)
Gemma-only judging failed the pilot (accepted «فرصة» for احتمال, rejected good forms), so pass 2 is now
**Gemma proposes, Claude reviews**: `arabic_auto.py propose` (generations + deterministic filters, no judge, resumable,
`variants/raw/arabic_auto/proposals/<id>.jsonl`) → `arabic_pass.py show --ready` shows them beside each term →
Claude writes decisions → `arabic_pass.py apply`. User rule: Arabic-script forms incl. common everyday words
(عميل for وكيل), only real same-meaning usage, add nothing otherwise.
`scripts/automation/autopilot.sh` (Task Scheduler "KassLayerAutopilot", every 30 min, via autopilot.vbs) keeps
propose running (Data & AI → Legal → Contracts → rest), and at most every 90 min runs the Claude review as one
tool-less `claude -p` call per batch (`review_system.md`, 5×100 senses; ~1 min per batch). A limit pauses the review
until the next slot; a WEEKLY limit stops it for good (`logs/review-stopped.flag`, delete to resume — user's wish:
keep Claude usage low). Commits + pushes to `enrichment-pass1`, then:
all proposals done → decision test `scripts/evaluate/decision_gemma.py` (Gemma yes/no = Jev fallback; user chose
it, Jev itself is unspecified) → `reports/decision_gemma.md` pushed → `logs/gpu-free.flag`, which the
arabic-dialect-to-msa autorun waits for → all reviewed → embeddings rebuild → `logs/autopilot.done`.
Log: `logs/autopilot.log`. Stop: `schtasks /delete /tn KassLayerAutopilot /f`.

## Next: Arabic enrichment pass 2 (start here on the PC)
User wants many more Arabic-script variants (مودل، داتا، داشبورد…), precision first: only real, useful forms;
adding nothing is fine. Tool: `scripts/enrich/arabic_auto.py` — adds on top of current reviews, never deletes.
Checks: 2 independent generations (`--votes 2`) → deterministic filters (Arabic script, length, not term/existing,
transliteration must match the English consonants) → judge call → optional EmbeddingGemma similarity (logged only:
it scored junk like «ليرة بيانات»/«أوتوماتيكا» as high as good forms, so do not use `--min-sim` without calibration).
Auto-added forms stay status `review` (`AUTO_ARABIC_TRUSTED = False` in `src/kass_layer/dictionary/enrichment.py`)
until an audit clears them. Qwen3.5-4B failed (invented forms; thinking mode never finished) → use Gemma 3 12B
(and compare ALLaM-7B) via Ollama.

1. Pilot, changes nothing: `.venv\Scripts\python scripts\enrich\arabic_auto.py run --dictionary 4cd164a7 --limit 30 --dry-run --workers 2`
   → audit `data\dictionaries\enriched\variants\raw\arabic_auto\pilot-4cd164a7-....jsonl` (kept vs rejected + reasons).
   If `--votes 2` rejects nearly everything, try `--votes 1` and compare.
2. If precision is good: run dictionary by dictionary (Data & AI, Legal, Contracts first), audit a sample, then
   consider `AUTO_ARABIC_TRUSTED = True`. Then `build_embeddings.py build` again (encodes only the new forms).
3. Then: candidate detector (lexical match with ال/و/ب/ل prefixes + embeddings to rank candidates in context),
   Jev decision with thresholds (auto / ask user / skip; shared & ambiguous variants always ask), Qwen minimal edit,
   evaluation on real paragraphs. Test Jev on Arabic first; fallback = local Gemma as yes/no judge.

## Office PC setup (Windows 11, RTX 3080 10 GB, Python 3.11)
```
git clone -b enrichment-pass1 https://github.com/saraabduallh-1/kass-layer.git
cd kass-layer
py -3.11 -m venv .venv
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu130
.venv\Scripts\pip install -r requirements-pc.txt
.venv\Scripts\hf auth login          (Read token; Gemma licence accepted on the same HF account)
ollama pull gemma3:12b               (install Ollama for Windows first: https://ollama.com/download)
.venv\Scripts\python -m pytest -q    (expect all tests to pass)
.venv\Scripts\python scripts\embeddings\build_embeddings.py build
```
Create `.env` in the project folder (never commit it):
```
QWEN_BASE_URL=http://localhost:11434/v1
QWEN_API_KEY=ollama
QWEN_MODEL=gemma3:12b
```
(The variable names say QWEN for history; any OpenAI-compatible endpoint works, including Ollama.)

## Working rules from the user
- Ask before every git commit/push. Keys only in `.env`, never in chat.
- Never modify the original term files. Delete unneeded files. Minimal user involvement.
- Quality over quantity for every variant. Explain each step when teaching (the user wants to learn).
