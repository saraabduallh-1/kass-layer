# Handoff — Kass Layer (updated 2026-11-12)

## START HERE (2026-11-12)
Kass (خصص) proposes standard SIWAR terms for non-standard Arabic writing and unifies a concept written several ways.
It is close to final. Plain-Arabic overview: `docs/PROJECT_EXPLAINED.md`. **Using Kass from another system (Saleem):
`docs/API.md`** — endpoints, response fields, and the rules (suggestions only; the writer decides every change).

Where things stand:
- Detector + unification: done, page `scripts/demo/kass-lab.html` (copy at `demo_local/index.html`), same logic in
  Python `src/kass_layer/detector/` behind the API. Scores: section "Baseline" below; unify 100/66.7 tuning, 100/71.4 heldout.
- 2026-11-12, writer's choice in unification: each group offers the forms to keep (suggested one first) and «every place»
  or chosen places, with undo (page `drawUnify`; API `/unify` returns `options` and `uses[].replacements`;
  test `tests/test_detector_api.py::test_unify_lets_the_writer_choose`).
- 2026-11-12, extraction of the 9 terminology dictionaries left in SIWAR runs in the background (no Claude, no model):
  `scripts/extract/run_new_dictionaries.py` → `logs/extract-new.log`, finished when `logs/extract-new.done` exists
  (about a day at 5 s per request). Progress: `extract_finance_media.py status legal_glossary theatre sociolinguistics
  stylistics applied_linguistics equestrian camels falcons education_heritage`. Running it again resumes.
  Not extracted on purpose: القاموس المحيط، names, bilingual dictionaries (not term sources).

Next, in order (the user's plan):
0. 2026-11-13: extraction of the 9 done (17,370 entries, commit 718a8db). Stage 1 (Gemma proposals) runs in the
   background: `scripts/enrich/run_new_generation.py` (resumable; log `logs/enrich-new.log`, `logs/enrich-new.done`).
   Stage 2, user's decision: Claude reviews all of the 7 small dictionaries (`session_review.py show/apply`, batches
   of ~120); stylistics (71c16f98) and applied linguistics (d0328aad), ~13k senses, get a sample only for now and
   their unreviewed proposals stay `review`; the user may come back to review them fully later.
   DONE 2026-11-14: all 9 generated and reviewed (legal glossary, theatre 1460/1482, sociolinguistics, equestrian,
   camels, falcons all; education heritage 294/324: Gemma kept failing on the rest; stylistics and applied
   linguistics 250-sense samples). Embeddings rebuilt (153,311 vectors), page data rebuilt (31 dictionaries, 60,493
   senses). Gold numbers unchanged from the 2026-11-08 baseline after one `also` entry (المحكمة الابتدائية → محكمة
   الدرجة الأولى, right, from the new legal glossary); parity 238/238, unify parity 58/58, unify 100/66.7 and
   100/71.4, pytest 42 passed. The 693 old forms that moved accepted → review changed no gold result.
1. When extraction is done: enrichment of the 9 (Gemma proposes, Claude reviews; "Next: everyday-Arabic enrichment
   pass 3" and pass 2 below), then `scripts/embeddings/build_embeddings.py build`, rebuild the page data, run every gold
   set and `parity.py` / `parity_unify.py`, compare with the baseline.
2. معجم الرياض: the user will give it as a JSON file (do not extract it). Use it as a reference for ordinary Arabic and
   for links between forms, NOT as a term dictionary (it would propose replacements for everyday words).
3. Unification rules still wanted by the user (need معجم الرياض for meanings and plurals):
   - inflection is not a conflict (done); derivation may be: حاسوب / حاسب unify, حاسب / حاسبة do not
     (today `same_word("حاسب", "حاسبة")` is True: fix it);
   - broken plurals and the everyday form with the term: عميل، عملاء، وكيل، الوكلاء → one group (today only وكيل is found);
   - spelling of Arabic words: سوريا / سوريه (today the spelling layer covers borrowed words only).
4. Then the project is closed and linked to Saleem in a NEW conversation; Saleem's repository is changing, so wait for
   the new link. Start that conversation from `docs/API.md`.

---

## History: START HERE of 2026-11-01 (office PC)
The user works with Claude Code on the office PC from now on. Do, in order:
1. `git pull` on branch `enrichment-pass1`, then the setup checks in "Office PC setup" below (skip what is already installed).
2. Continue **"Next: everyday-Arabic enrichment pass 3"** below — first the audit of weak pass-1 pairs (step 3 there),
   because it is what lowers the wrong suggestions users see today (precision 50% on `gold-arabic-heldout.json`),
   then the proposals for new everyday forms (steps 1–2).
3. After each dictionary: rebuild the page data, run the tests (step 4), report the numbers to the user, ask before pushing.
Baseline (`node scripts/demo/tests/run_tests.js gold-<set>.json`, bare file names; latest numbers last):
tuning 93.8/86.5 · heldout-1 81.0/63.0 · heldout-2 94.7/100 · ambiguity 71.4/58.8 · arabic-tuning 71.0/56.4 ·
arabic-heldout 83.3/50.0 (recall/precision %); `parity.py` 212/212 identical.
Baseline rebuilt on the office PC (2026-11-01), the one to compare with here (see `reports/pc_decisions.md`):
tuning 93.8/84.9 · heldout-1 81.0/63.0 · heldout-2 94.7/100 · ambiguity 71.4/58.8 · arabic-tuning 67.7/53.8 ·
arabic-heldout 83.3/52.6; parity 212/212.
Baseline from 2026-11-08 on (gold sets now carry an `also` field of right answers they did not list, `reports/gold_also.md`):
tuning 93.8/90.0 · heldout-1 90.5/90.5 · heldout-2 94.7/100 · ambiguity 78.6/78.6 · arabic-tuning 67.7/75.0 · arabic-heldout 66.7/72.7.
After the everyday usage check (2026-11-08, `scripts/enrich/everyday_audit.py`, 960 pairs with 3+ field sentences judged by Gemma on 6 real Wikipedia sentences each, Claude reviewed every pair with 0 or 1 yes; about 125 wrong pairs withdrawn in `variants/topic/everyday-*-{1,2}.txt`, right pairs with off-topic sentences kept; terms with several senses are refused by topic_pass and stay): arabic-tuning 67.7/80.8 · arabic-heldout 66.7/80.0, the rest unchanged.
Everyday/colloquial words from Claude's knowledge of Arabic usage (2026-11-09, `scripts/enrich/everyday_seed.py`, `variants/topic/*-everyday-seed-1.txt` and `*-everyday-k-*.txt`): 104 one-sense terms in 19 dictionaries (aviation, development and non-profit: nothing to add beyond what earlier passes had), 233 forms written (بلنتي → ركلة جزاء، سيرفر → خادم، سي في → السيرة الذاتية، الدوام المرن → العمل المرن ...); gold numbers unchanged. Many everyday concepts (password, browser, credit card) have no SIWAR term. Audit tool: `scripts/enrich/audit_pairs.py` (Gemma yes/no, then Claude
reviews the "no" answers and applies them with `topic_pass.py --audit`). Standing approval on the PC: push to
`enrichment-pass1` without asking when the tests do not get worse; never to `main`.
Audit progress: Data & AI done 2026-11-02 (590 pairs, 117 reviewed, 17 withdrawn; decisions `variants/topic/ai-audit-1.txt`; tests unchanged). Legal done 2026-11-02 (3,259 pairs, 958 reviewed, 53 withdrawn, 19 more chosen but kept because the term has several senses; `variants/topic/legal-audit-1.txt`; tests unchanged). Contracts done 2026-11-02 (1,103 pairs, 132 reviewed, 20 withdrawn; tests unchanged). Finance done 2026-11-02 (952 pairs, 185 reviewed, 28 withdrawn; tests unchanged). Media done 2026-11-02 (339 pairs, 75 reviewed, 23 withdrawn; tuning precision 84.9 -> 86.5, rest unchanged). Energy done 2026-11-02 (727 pairs, 150 reviewed, 27 withdrawn; tests unchanged). Sports done 2026-11-02 (382 pairs, 101 reviewed, 25 withdrawn). Stats done 2026-11-02 (591 pairs, 156 reviewed, ~30 withdrawn). Admin done 2026-11-02 (356 pairs, 87 reviewed, ~21 withdrawn). The 12 small dictionaries done 2026-11-02 (decisions `variants/topic/*-audit-1.txt`; tests unchanged). Aviation done 2026-11-02 (4,434 pairs, 1,011 reviewed, 228 withdrawn). AUDIT COMPLETE: all 22 dictionaries; tuning precision 84.9 -> 86.5, every other number unchanged. The arabic gold errors left are mostly right pairs fired in the wrong context, which withdrawing pairs cannot fix. New everyday forms tried on Data & AI with `scripts/enrich/everyday_propose.py`: 4,962 Gemma proposals, 540 after a Wikipedia presence filter, 1 accepted; stopped there on purpose (`reports/pc_decisions.md`). Next step with real effect: context, not data: the arabic gold errors are right pairs firing in the wrong sentence (بحضور → المواظبة), so look at the detector's context step.
2026-11-02: the user is stopping arabic-dialect-to-msa; the autopilot no longer runs `dialect_watch.sh` and this session no longer monitors that project.

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
- **Term unification (2026-11-09):** one concept written several ways in a text → one form (`reports/unify.md`).
  `src/kass_layer/detector/unify.py` = `unifyTerms` in the page (parity `scripts/demo/tests/parity_unify.py` 58/58), API
  `POST /unify`, page block «توحيد المصطلحات في النص». Scores `run_unify.py`: tuning 100/66.7, heldout 100/71.4
  (precision/recall of merged pairs). Misses are index gaps (الهاكر، ميتنق، السيرفر in tech).
- **Explainer video (2026-11-09):** `reports/presentation/kass_layer_video.mp4` (130 s, 1080p). Source: an animated page
  `reports/presentation/video/kass_video.html` (`render(t)` draws second t), rendered by `video/render_video.py`
  (Edge via Playwright + ffmpeg from `imageio-ffmpeg`; pass seconds as arguments for preview PNGs). Lean and closeness
  numbers are the detector's for its two sentences; the ranking bars are illustrative. Fonts in `reports/presentation/fonts/`.
  Sound effects only (clicks, ticks, pops; no music): run `video/add_sfx.py` after every render; its times mirror the page's
  scene starts and offsets, so change both together.

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

## Context step (2026-11-03)
Two rules for everyday Arabic words, adopted by the user, in `engine.py` and `kass-lab.html`: EVERYDAY_STRONG/EVERYDAY_CLOSE (a weak lean to the
domain needs meaning close to the sentence) and EVERYDAY_COMMON (the written word too frequent in general articles is not proposed).
New baseline (recall/precision %): tuning 93.8/88.2 · heldout-1 81.0/65.4 · heldout-2 94.7/100 · ambiguity 71.4/62.5 · arabic-tuning 67.7/67.7 ·
arabic-heldout 66.7/61.5; parity 212/212. Known cost: arabic-heldout recall fell from 83.3 (الفئة → صنف، ميزة → خاصية no longer proposed).
Article tests: `reports/articles/` (12 Wikipedia extracts: false alarms only; 6 articles written by Claude with its own answers: not independent).
Real articles with independent answers are still missing, and they are the test that decides readiness.
Clef-Flash (open, Jev-compatible, `data/models/clef-flash`, git-ignored; `hf download Cloudflare/clef-flash`), 4-bit, 8.5 GB GPU, ~0.2 s per
suggestion: `scripts/evaluate/decision_clef.py`, `clef_filter.py`, results `reports/clef_filter.md`. As a filter at 0.4 it raises precision (written articles
67.9 -> 79.2) and separates context traps well, but scores 59.7% on the 600 decision cases, so it is NOT wired into the detector. The user has no Jev key and no GPU
server: only the office PC is available, and the academy server is CPU only. Automatic replacement is not wanted for now: suggestion mode only.

Later on 2026-11-03: sound-only matches (`exact`) and one-word colloquial forms are now always `review`, an unstripped word with its article (والقلق) is no longer a sound match, NEVER_FORMS blocks بواسطة and English stop words; 8 bad pairs withdrawn (`variants/topic/*-audit-2.txt`). Gold numbers above unchanged. First test on 16 real published excerpts: `reports/articles/real_results.md` (about 60% of suggestions right, 6 of 15 wanted words found; judged by Claude, not independent). Texts are in git-ignored `logs/real_articles/`. Main gaps: person names, everyday words (الاتجاه، انتهاء، قضية), and forms missing from the data (البودكاست، روبوتات الدردشة، الكود).

Usage mining (2026-11-03, user's direction: search real usage rather than ask a model): `scripts/enrich/mine_usage.py` (Wikidata aliases, Arabic Wikipedia redirects, writers' glosses «X (English)», evidence kept in `variants/raw/usage/`), reviewed by Claude and applied with `topic_pass.py`. Data & AI done: 387 senses with candidates, 62 forms added (`variants/topic/ai-usage-1.txt`), gold numbers unchanged. All mined dictionaries reviewed 2026-11-05 (filter `scripts/enrich/usage_filter.py`: curated source + seen 3+ times in 20 GB of Arabic tweets; Clef judging stopped because arabic-dialect-to-msa needed the GPU): about 300 more forms (`variants/topic/*-usage-1.txt`), 3 withdrawn as too common in another meaning (`*-usage-2.txt`: شخصنة، محجر، إسالة). Added forms occur about 0.7 times per 10,000 tweet words. Gold numbers unchanged; the gold sets do not contain these words, so the gain is not measured yet. Tweets: 20 of 41 GB downloaded (download stopped by low memory; `curl -C -` resumes). Tweet test 2026-11-05 (`reports/usage_tweets_test.md`, `scripts/evaluate/usage_tweets_test.py`): on 310 real tweets the added forms reach recall 54.3%, precision 61.5%, false alarms 37.2% after two fixes (multi-word spelling variants need no context; 9 ambiguous one-word forms withdrawn). 2026-11-05 later: the common-word rule now applies to single words only (a common first word no longer blocks مؤسسة النقد السعودي): tweets recall 57.4% / precision 62.4%; real articles 45 suggestions, 6 new ones right after withdrawing الطاقة الشمسية → طاقة كهروضوئية (`energy-audit-3.txt`); arabic-tuning precision 65.6 and arabic-heldout 53.3 because of three new suggestions that are right but not in the gold lists (see `reports/pc_decisions.md`). 2026-11-07 launch prep (`reports/launch_precision.md`): Arabic synonym/spelling forms go to review, names and bracketed abbreviations of names dropped, sound-alikes of Arabic words dropped, everyday matches dropped when the writer already uses the term; the replace tier is 90.9% on the gold sets and 15/15 on two new article batches, the review tier 73–75%. The live site still has the old engine until it is redeployed from the Mac (Deployment section). Still to do: an independent check of those judgements, and the 68 Data & AI senses without an English name (وكيل) that mining cannot reach.

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
  **Since 2026-11-09 the server deploys straight from GitHub:** `demo_local/` is tracked (rebuild it, copy the page to
  `demo_local/index.html`, commit, push), then from the Mac `ssh renad@arai.center 'sh ~/apps/kass/repo/deploy/update.sh'`
  (first time: the clone command at the top of `deploy/update.sh`). It builds from `~/apps/kass/repo` (branch
  enrichment-pass1 by default; pass another branch as the first argument); the rsync steps above are no longer needed.
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
- Commit and push to `enrichment-pass1` without asking (user, 2026-11-14); never push to `main`. Keys only in `.env`, never in chat. Explain in Arabic; the user is learning.
- Keep Claude usage low (small batches); heavy model work runs locally on the PC GPU (Gemma via Ollama).
- Never modify the original term files. Delete unneeded files. Minimal user involvement.
- Quality over quantity for every variant. Explain each step when teaching (the user wants to learn).
