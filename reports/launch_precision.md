# Precision before launch (2026-11-07)

Judgements are Claude's, not an independent check. "Replace" (مقترح) is what the page applies with «تطبيق الكل»;
"review" (يحتاج تدقيقًا) is shown with its reason and never applied on its own.

## What changed

1. Arabic synonym and spelling forms (types s, i) are review, not replace: they can carry their everyday sense
   (سهم ممتاز، حد الفقر، سباق تتابع). Only borrowed words, acronyms and English stay replace.
2. No English sound-alike candidates for an Arabic synonym (غاز النشادر → أسطوانة غاز).
3. An English abbreviation in brackets is dropped when the words before it do not share a stem with its term
   (بورصة الدار البيضاء (CSE) → «استغلال جنسي»); a Latin word next to another capitalised Latin word is dropped as part
   of a name (Maroc Telecom).
4. A sound-alike match is dropped when the word is an Arabic word with a particle or an ending (بتقنيات، استراتيجيتك).
5. An everyday match is dropped for a term the writer already uses: «وكيل الذكاء الاصطناعي» starts with it,
   «السيارات ذاتية القيادة» goes on into it, and a one-word term written twice or more elsewhere in the text means the
   everyday word is something else («سيطرح الوكيل أسئلة على العميل»: the customer).
6. Data: withdrawn الطاقة الشمسية → طاقة كهروضوئية (energy-audit-3), بورصة / سوق مالية → الصرف (finance-audit-3).

The six gold sets are unchanged by steps 1–6; parity 212/212; pytest 38 passed.

## Results

| Set | Replace tier | Review tier |
|---|---|---|
| Gold sets (all six, pooled) | 50/55 (90.9%) | 80/103 (77.7%) |
| Real articles, first batch (16) | 11/13 (84.6%; both wrong are «GPT → محول توليدي مدرب سابقا») | 18/31 (58.1%) |
| Second batch (6 articles; rules 3–4 were made after reading it) | 7/7 | 19/26 (73%) |
| Third batch (9 articles, judged before any change) | 8/8 | 18/29 (62%) before step 5, 18/24 (75%) after |
| Tweets (adversarial: one random tweet per mined form) | 5/10 | 95/156 (61%) |

## Tried and not used

- Sentence embedding against the term's definition (embeddinggemma-300m, bge-m3, multilingual-e5-large,
  Qwen3-Embedding-0.6B): AUC 0.55–0.67 for right vs wrong suggestions.
- A classifier on the detector's features (logistic regression, gradient boosting), trained on two kinds of text and
  tested on the third: AUC 0.46–0.48, so it does not carry over between kinds of text.
- Letting every multi-word phrase skip the context check: recall 76.5% on tweets but false alarms 68%.

## Still weak

Review tier on everyday Arabic words (عوائد → ريع، القادم → متجه إلى الداخل، الأسهم → «الأسهم وحصص (حقوق) رأس المال
الأخرى»). The context signal the page has (static word vectors) does not separate right from wrong here; a model that
reads the sentence is needed (Clef-Flash or Gemma on a GPU server).
