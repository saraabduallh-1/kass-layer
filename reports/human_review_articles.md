# Blind human review of the article suggestions (2026-11-19)

All 103 Kass suggestions on the real articles, judged by the project owner on a phone review page (one card per
suggestion: text with the word marked, proposed term, definition, dictionary; no tier, no earlier judgement).
Judgements: correct / wrong / unsure. The 97 tweet rows of the 200 sample stay in `logs/review_sample_200.xlsx`
(tweets are not published). Script: `scripts/evaluate/score_human_review.py`.

| | Correct | Wrong | Unsure | Precision (unsure left out), Wilson 95% CI |
|---|---|---|---|---|
| All | 86 | 12 | 5 | 87.8% (86/98, 80–93%) |
| Replace tier | 27 | 1 | 0 | 96.4% (27/28, 82–99%) |
| Review tier | 59 | 11 | 5 | 84.3% (59/70, 74–91%) |

By domain: tech 31/32, engineering 22/25, finance 17/21, media 6/7, legal 5/5, culture 5/8.

## ChatGPT as a third judge (comparison only, not ground truth)

Same file without the owner's judgements. ChatGPT: 72 correct, 17 wrong, 14 unsure, precision 80.9% (72/89).
Agreement with the owner 77/103; on the 86 rows both decided, 75 agree, Cohen's kappa 0.55 (moderate). Most
disagreements are ChatGPT being more cautious (12 rows the owner judged correct, it marked unsure). The owner's own
judgements are not always consistent across contexts (البث الصوتي → مدونة صوتية wrong once, correct twice; الأسهم →
long statistics term wrong 3 times, correct once), so a second human judge is needed.

## Error patterns and fixes

1. Names taken as borrowed words (3, both judges): جائزة بوشكاش → الحركات الأساسية, لوس أنغلوس → نواة,
   ألبيرتو زاكيروني → ملعب التدريب. All from the sound match alone (short consonant skeletons such as bsks, nkls fit many
   English words). Fix (`name_context` in engine.py / `nameContext` in the page): no sound match when a cue word comes
   before it (جائزة، اللاعب، المدرب، ولاية، مدينة، نادي، كل من …), a foreign-name particle (لوس، سان، دي، فان …), or
   another unknown foreign-looking word stands beside it; not for a word with the article (الشاعر الميتافور).
2. A form that is one part of a longer coordinated term (3): الأسهم → «الأسهم وحصص (حقوق) رأس المال الأخرى». Of the 19
   such forms in the enrichment, 5 were withdrawn as narrower or far more general (الأسهم، البدلات، التتبع، تأكيد،
   هندسة الطيران); 14 kept because they are used for the whole term (كراسة الشروط، حقوق الطبع، نظام المنافسات …).
3. Sense differences in context (6): أشعة الشمس → تصوير بالأشعة, التيار → تيار كهربائي, الشِّباك → الشبكة,
   سوق العملات المشفّرة → سوق صرف العملات الأجنبية. Left to the review tier; no rule.

Effect: every gold number unchanged (the 22 right answers that come from the sound match stay), parity 352/352 and
120/120, pytest 42 passed. On all 370 real suggestions the name rule removed only names and product names. On the
103 reviewed rows (full articles) 6 wrong and 1 correct suggestion are gone: precision 87.8% → 93.4% (85/91). This is
measured on the sample the fixes came from; the independent check is the next sample of 300 new suggestions judged by
two people separately.
