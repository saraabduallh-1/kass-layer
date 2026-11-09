# Term unification inside one text (2026-11-09)

The idea (from a reviewer): one concept written in several forms in the same text (المودل، الموديل، نموذج) should be
written one way: the SIWAR term when there is one, otherwise the form used most.

## What others do, and the choice

Terminology QA and clean-up tools start from a glossary, add spelling/inflection normalisation for variants, and pick the
most frequent form when no approved term exists; meaning-closeness (embeddings) helps confirm synonyms but on its own also
joins related words and opposites. Sources: glossary-driven term-variation checks in MT evaluation
(arXiv 2609.08779), terminology clean-up tools (Congree: spelling, hyphenation, derivation, synonymy), a count-based
manuscript checker (most frequent spelling as canonical), edit-distance clustering of variants (arXiv 1309.6185),
hybrid lemmatisation + embeddings for variant clustering (EVALITA, CEUR-WS Vol-4195), and term-variation recognition
in ATR (Nenadić & Ananiadou, COLING 2004; FASTR). Our own trials agree: definition/sentence embeddings separated senses
only at AUC 0.55–0.67.

So Kass's way is the right base, and unification reuses it:
1. **Dictionary groups**: every form the detector links to one SIWAR term, plus the term itself written anywhere in the
   text. When a form has several terms, the one the writer also uses wins (الإنفرتر → عاكس التيار when «عاكس التيار» is there).
2. **Spelling groups**: borrowed words outside the dictionaries with one sound skeleton (الدرايف / Drive, داشبورد /
   dashboard); ordinary Arabic is excluded (frequent in general articles or in the dictionaries' Arabic, or few long vowels).
   Always marked for review; the most frequent form is kept.
3. Not a group: one word in different inflections (النظام / للنظام، الاستثمار / الاستثمارات، LLM / LLMs), a shortened
   mention (للفيدرالي / الاحتياطي الفيدرالي), a gloss in brackets («الذكاء الاصطناعي (AI)»), an English word inside an
   English phrase (software as a service).

Code: `src/kass_layer/detector/unify.py`, the page (`unifyTerms` in kass-lab.html, same results: `parity_unify.py` 58/58),
API `POST /unify` (same body as `/analyse`). The page shows a «توحيد المصطلحات في النص» block with a button that applies
the term to every suggestion in a dictionary group.

## Results

Gold sets written before tuning (`scripts/demo/tests/gold-unify-*.json`, pairs of forms that should be merged;
`run_unify.py`):

| Set | Texts | Precision | Recall |
|---|---|---|---|
| tuning | 16 | 100% (12/12) | 66.7% (12/18) |
| heldout | 10 | 100% (5/5) | 71.4% (5/7) |

Misses are words the index does not know (الهاكر، ميتنق، السيرفر in tech, الفيرموير، البلوق), an English phrase split in
two (الإنترست ريت), and a spelled-out acronym (البي دي اف) — enrichment gaps, not unification logic.

On the 32 real articles (no gold; read by hand) it raised 6 groups: الذكاء الاصطناعي / AI, تيار متردد / AC,
بانقضاء / لانتهاء, البورصة / سوق الأسهم (right); الألواح الشمسية / لوحة شمسية (a broken plural, inflection only) and
السعودية / المملكة (a wrong link of the detector) are wrong but both are marked «تحقّق قبل التوحيد».
Speed: ~0.23 s per article in Python including the analysis (the analysis is most of it).
