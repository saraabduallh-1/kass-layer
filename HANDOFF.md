# Handoff — Kass Layer (updated 2026-11-01)

## START HERE (office PC, 2026-11-01)
The user works with Claude Code on the office PC from now on. Do, in order:
1. `git pull` on branch `enrichment-pass1`, then the setup checks in "Office PC setup" below (skip what is already installed).
2. Continue **"Next: everyday-Arabic enrichment pass 3"** below — first the audit of weak pass-1 pairs (step 3 there),
   because it is what lowers the wrong suggestions users see today (precision 50% on `gold-arabic-heldout.json`),
   then the proposals for new everyday forms (steps 1–2).
3. After each dictionary: rebuild the page data, run the tests (step 4), report the numbers to the user, ask before pushing.
Baseline to beat (`node scripts/demo/tests/run_tests.js <gold file>`, 2026-11-01):
tuning 93.8/86.5 · heldout-1 81.0/63.0 · heldout-2 94.7/100 · ambiguity 71.4/58.8 · arabic-tuning 71.0/56.4 ·
arabic-heldout 83.3/50.0 (recall/precision %); `parity.py` 212/212 identical.
Baseline rebuilt on the office PC (2026-11-01), the one to compare with here (see `reports/pc_decisions.md`):
tuning 93.8/84.9 · heldout-1 81.0/63.0 · heldout-2 94.7/100 · ambiguity 71.4/58.8 · arabic-tuning 67.7/53.8 ·
arabic-heldout 83.3/52.6; parity 212/212. Audit tool: `scripts/enrich/audit_pairs.py` (Gemma yes/no, then Claude
reviews the "no" answers and applies them with `topic_pass.py --audit`). Standing approval on the PC: push to
`enrichment-pass1` without asking when the tests do not get worse; never to `main`.
Audit progress: Data & AI done 2026-11-02 (590 pairs, 117 reviewed, 17 withdrawn; decisions `variants/topic/ai-audit-1.txt`; tests unchanged). Legal done 2026-11-02 (3,259 pairs, 958 reviewed, 53 withdrawn, 19 more chosen but kept because the term has several senses; `variants/topic/legal-audit-1.txt`; tests unchanged). Contracts done 2026-11-02 (1,103 pairs, 132 reviewed, 20 withdrawn; tests unchanged). Finance done 2026-11-02 (952 pairs, 185 reviewed, 28 withdrawn; tests unchanged). Media done 2026-11-02 (339 pairs, 75 reviewed, 23 withdrawn; tuning precision 84.9 -> 86.5, rest unchanged). Energy done 2026-11-02 (727 pairs, 150 reviewed, 27 withdrawn; tests unchanged). Next: the rest (sports next); then new everyday forms.

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

## Term detector API (2026-10-26)
`src/kass_layer/detector/engine.py` is a line-by-line port of the demo page's engine (`scripts/demo/kass-lab.html`);
`api.py` serves it with FastAPI. CPU only, no model at query time: ~1 s load, ~200 MB RAM, 2–150 ms per sentence.
Data (`KASS_DATA_DIR`, default `demo_local/`): `index.json`, `context.json`, `senses.txt` from `scripts/demo/build_*.py`.
```
.venv/bin/pip install -r requirements-api.txt
.venv/bin/uvicorn kass_layer.detector.api:app --app-dir src --port 8000     (docs: /docs)
```
`POST /analyse {"text", "domain"}` → items (position, state replace/review/std, suggestion, choices, reasons),
`unknown` borrowed-looking words, `suggested_text` (confident replacements only). Also `GET /domains`, `GET /health`.
Keep page and Python in step: `scripts/demo/tests/parity.py` must report every gold sentence identical.
Everyday Arabic words (عميل → وكيل, التوقع → تنبؤ, القضية → الدعوى) are proposed (state review) only when the words
around them lean towards the chosen domain: `words.json`/`words.txt` from `scripts/demo/build_word_index.py`, built on
~3,540 Arabic Wikipedia articles (`scripts/corpus/fetch_wikipedia.py --per-domain 500`: 500 per domain + ~1,500
general) plus the dictionary definitions. One-word terms common in general articles (يجب، مجموعة) are never proposed
this way, nor a term the text already uses in another form (الشبكات العصبية / شبكة عصبية); colloquial forms (دوام) are
always ordinary matches. Remaining errors come mostly from weak everyday→term pairs in the enrichment data
(e.g. بحضور → المواظبة): next step is an audit of those ~11k pairs.
Gold sets for this: `gold-arabic-tuning.json`, `gold-arabic-heldout.json`; Python scores: `tests/run_tests.py`.
Live site: **https://kass.arai.center** (academy server, see "Deployment"). The old GitHub Pages copy
(`gh-pages`) is outdated — leave it, the server replaces it.

## Next (2026-10-28, office PC): everyday-Arabic enrichment pass 3
Goal (user): for every specialist term, the everyday Arabic word writers use instead (عميل → وكيل, غلاء الأسعار → تضخم).
Done by hand so far: `scripts/enrich/topic_pass.py` + decision files in `data/dictionaries/enriched/variants/topic/`
(~70 forms over the 1,128 most-used terms; most common words were already covered by passes 1–2).
Plan on the PC (Gemma proposes, Claude reviews in small batches, as in pass 2):
1. Proposals: Gemma 3 12B gives, per term (term + definition + English), everyday Arabic words used with the same
   meaning in reports/articles; deterministic filters (Arabic script, not the term or an existing form, not another
   sense's standard term). Start with the dictionaries of the six demo domains; skip generic words defined per law.
2. Review: Claude keeps only real same-meaning usage → `topic_pass.py <dict> <file>`.
3. Audit of weak everyday→term pairs from pass 1 (~11k, e.g. بحضور → المواظبة, الكود → الشفرات المصدرية): Gemma yes/no +
   review; drop rejected pairs with `topic_pass.py <dict> <file> --audit` and a chunk `!form` (done 2026-10-28:
   withdrawn forms are listed in the row's `audit_withdrawn`; try `--dry-run` first). Judge in context: «الحضور» is a
   fine form of المواظبة, only the sentence «بحضور المحامي» was wrong — drop a pair only when it is never the same meaning.
   Keep Claude usage low: small batches, one dictionary at a time, Data & AI / Legal / Contracts first.
4. Then rebuild `build_demo_index.py demo_local` (and `build_word_index.py` if words changed), run
   `node scripts/demo/tests/run_tests.js <gold file>` for every gold set and `parity.py`, compare with the baseline at the
   top. Copy `scripts/demo/kass-lab.html` to `demo_local/index.html` if the page changed. Push (after asking); the user
   updates the live site from the Mac (see "Deployment").

## Demo page and Deployment (2026-10-29)
- Page source: `scripts/demo/kass-lab.html` (full HTML document). `demo_local/` (git-ignored) holds the built data and a
  copy as `index.html`. UI: logo right, name left, dark/light toggle, clear button, every proposed term opens a
  dropdown (choices + «إبقاء الكلمة الأصلية»); the result card shows the dictionary, English and definition of the
  chosen term. Test harnesses in `scripts/demo/tests/*.js` stub the DOM (incl. theme) — keep them in step with the page.
- Server: `ssh renad@arai.center` (no sudo, podman, shared network `siwar_default`; other apps live there — touch only
  kass). One container `kass_app` = `Dockerfile` (FastAPI API + the page at `/`, `KASS_SERVE_PAGE=1`), compose file
  `deploy/docker-compose.yml` (127.0.0.1:3945), nginx site `deploy/kass.conf` in `~/docker-nginx/conf.d/` (no-cache
  header so updates show at once). Build context on the server: `~/apps/kass/src/` (Dockerfile, requirements-api.txt,
  `src/kass_layer`, `demo_local`). Update:
  ```
  rsync -a demo_local/ renad@arai.center:apps/kass/src/demo_local/      (and src/kass_layer if the engine changed)
  ssh renad@arai.center 'cd ~/apps/kass && podman build -q --format docker -t kass:latest src && podman compose up -d --force-recreate app'
  ```
  The SSH key lives on the user's Mac, so deployment is done from the Mac unless the user sets up a key on the PC.
- Report for the academy: `reports/تقرير_طبقة_خصص.docx/.pdf` (Arabic progress report dated ١٧ جمادى الأولى ١٤٤٨ هـ).

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
- Ask before every git commit/push. Keys only in `.env`, never in chat. Explain in Arabic; the user is learning.
- Keep Claude usage low (small batches); heavy model work runs locally on the PC GPU (Gemma via Ollama).
- Never modify the original term files. Delete unneeded files. Minimal user involvement.
- Quality over quantity for every variant. Explain each step when teaching (the user wants to learn).
