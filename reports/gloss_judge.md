# ArabGlossBERT as a context-gloss judge (2026-11-17): not adopted

Model: SinaLab/ArabGlossBERT (Al-Hajj & Jarrar, RANLP 2021; CC BY-SA 4.0), the context-gloss model SinaTools uses for
Arabic WSD, input as in SinaTools: «sentence with [UNUSED0]word[UNUSED1] [SEP] word: gloss». Score = logit(same sense)
− logit(other). The model only scores existing SIWAR candidates; it never proposes. Script:
`scripts/evaluate/gloss_judge.py` (model files in `data/models/arabglossbert`, not in git). CPU, ~30 ms per pair.

Adoption rule set before the run: adopt only if it clearly raises precision without lowering recall.

| Test | Cases | AUC | Effect of the best threshold |
|---|---|---|---|
| 600 decision cases (same form, right term vs another term) | 600 (300 right) | 0.637 | score ≥ 2: precision 0.50 → 0.58, recall 0.94. Gemma 3 12B on the same cases: precision 0.615, recall 0.853 |
| review-tier suggestions on the gold sets | 102 (87 right) | 0.675 | score ≥ 0: precision 0.853 → 0.875, recall 0.966 (drops 3 wrong, 3 right) |

- Scores saturate near +6 for most pairs, so the model separates only gross errors (الجوالات → المشروعية −6.6,
  تشارجر → حاملة −4.9, الضوضاء → تشويش −2.2). It also scores right ones low (الموديل → نموذج −5.6, بالفئة → صنف −4.0,
  للدوام → ساعات العمل −3.0).
- Several "wrong" review suggestions in the gold sets are near-synonyms the gold does not list (الميتافور → استعارة).
- Same range as the sentence/definition embeddings tried before (AUC 0.55–0.67). The model was trained on general Arabic
  word senses (Arabic Ontology and Birzeit lexicon); most Kass decisions are borrowed words and specialist terms.
- It would also break the page/Python parity (540 MB model, Python only).

Decision: not adopted. The open route stays the one in the paper: a context judge fine-tuned on Arabic terminology
decisions, and an independent human review (`logs/review_sample_200.xlsx`) to measure where the review tier fails.
