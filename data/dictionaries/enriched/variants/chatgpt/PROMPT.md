# إثراء المعاجم عبر ChatGPT

لكل جزء: افتحي محادثة ChatGPT، والصقي الرسالة الجاهزة تحت الجزء، ونزّلي الملف اللي يرجعه،
واحفظيه بنفس الاسم في `data/dictionaries/enriched/variants/chatgpt/outputs/<نفس اسم المجلد>/`.

## البرومبت (مشترك لكل الأجزاء)

```
You are enriching an Arabic specialised-terminology dictionary for a rewriting layer.

The terminology layer finds non-standard wording in ordinary Arabic text and replaces it with the standard dictionary term, for example «المودل تدرب على بيانات وحقق نتائج جيدة» becomes «النموذج تدرب على بيانات وحقق نتائج جيدة». It needs, for each standard term, the other ways Arabic writers actually refer to the same concept in real text: news, social media, reports, workplace and student writing.

Variant types:
- transliteration: the English or other foreign word written in Arabic letters (مودل، داتا، كاش فلو، ترند، بودكاست).
- foreign: the English word or acronym written in Latin letters inside Arabic text (model, cash flow, KPI).
- abbreviation: a shortened form or acronym used in Arabic writing.
- informal_synonym: a non-standard Arabic wording in common use for the same concept, such as a literal translation, an older term or a regional term.
- colloquial: a Saudi, Gulf or widely used dialect form.
- spelling_variant: a common alternative spelling of the term itself (hamza, taa marbuta, alif maqsura, joined or separated words).

Rules for a valid variant:
1. Real usage only. Arabic writers must really use the form for this concept. Never invent forms. An empty list is the right answer for many terms, especially long multi-word technical terms that nobody rephrases.
2. Same concept only: not a broader, narrower or related concept. If the form's usual meaning has its own standard term, it is not a variant.
3. Base form only: no plurals, duals, added definite article ال, possessive suffixes or verb conjugations; a later stage handles inflection. Match the grammatical form of the term.
4. Not the standard term itself, and not a difference in diacritics only.
5. foreign: the English term as people commonly write it; an English acronym only when the acronym itself is common.
6. ambiguous is true when the form also commonly means something unrelated in everyday text (for example موديل also means a fashion model or a car's model year); ambiguity_note then says briefly in Arabic when the form does not refer to this term, otherwise it is empty.
7. example: one short, natural Arabic sentence, as a non-specialist would write it, using the form with this meaning.
8. confidence: high when the form is very common, medium when it is used but less common, low when it is rare.

Input: the JSONL file at the link below. Each line is one dictionary sense with sense_id, term, definition and english.

For every input line, list the term's valid variants. Aim for both: include every form you are confident Arabic writers really use (English words and acronyms in Latin letters, English words in Arabic letters, looser Arabic wordings, dialect and spelling variants), and never invent forms. An empty list is correct when nobody rephrases the term.

Output: a downloadable file named exactly like the input file, in JSONL (one JSON object per line, UTF-8, no markdown), with exactly one line per input line, in the same order, never skipping a line:
{"sense_id": "<copied unchanged from the input>", "variants": [{"form": "مودل", "type": "transliteration", "confidence": "high", "ambiguous": false, "ambiguity_note": "", "example": "درّبنا المودل على بيانات العملاء."}]}
type is one of transliteration (Arabic letters), foreign (Latin letters), abbreviation, informal_synonym, colloquial, spelling_variant. confidence is high, medium or low. Use exactly these field names. Process the whole file; if it is long, work through it in parts but return one complete file.
```

## 01. معجم البيانات والذكاء الاصطناعي — 1443 معنى، 8 أجزاء

- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-001.jsonl`
- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-002.jsonl`
- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-003.jsonl`
- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-004.jsonl`
- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-005.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-005.jsonl`
- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-006.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-006.jsonl`
- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-007.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-007.jsonl`
- `01-4cd164a7-7160-4de8-af5c-34382f5da657/part-008.jsonl` (43 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/01-4cd164a7-7160-4de8-af5c-34382f5da657/part-008.jsonl`

## 02. معجم مصطلحات الحكـومــة الـرقميـــة — 130 معنى، 1 أجزاء

- `02-97ac5360-d65f-425f-974f-9118f09d13a6/part-001.jsonl` (130 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/02-97ac5360-d65f-425f-974f-9118f09d13a6/part-001.jsonl`

## 03. معجم المصطلحات المالية والاقتصادية — 1893 معنى، 10 أجزاء

- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-001.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-002.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-003.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-004.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-005.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-005.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-006.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-006.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-007.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-007.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-008.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-008.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-009.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-009.jsonl`
- `03-4264f8ae-7c51-437d-a6e4-877abad57325/part-010.jsonl` (93 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/03-4264f8ae-7c51-437d-a6e4-877abad57325/part-010.jsonl`

## 04. معجم مصطلحات الإعلام — 833 معنى، 5 أجزاء

- `04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-001.jsonl`
- `04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-002.jsonl`
- `04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-003.jsonl`
- `04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-004.jsonl`
- `04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-005.jsonl` (33 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/04-928f4f87-b98c-4b2d-b31d-0b45c6747644/part-005.jsonl`

## 05. معجم مصطلحات مركز قياس أداء الأجهزة العامة — 320 معنى، 2 أجزاء

- `05-7806f9cf-4bdb-4c10-b9e5-2705d8945603/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/05-7806f9cf-4bdb-4c10-b9e5-2705d8945603/part-001.jsonl`
- `05-7806f9cf-4bdb-4c10-b9e5-2705d8945603/part-002.jsonl` (120 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/05-7806f9cf-4bdb-4c10-b9e5-2705d8945603/part-002.jsonl`

## 06. معجم المصطلحات الإحصائية — 1390 معنى، 7 أجزاء

- `06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-001.jsonl`
- `06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-002.jsonl`
- `06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-003.jsonl`
- `06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-004.jsonl`
- `06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-005.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-005.jsonl`
- `06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-006.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-006.jsonl`
- `06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-007.jsonl` (190 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/06-ee392446-a5df-4b0c-b1e2-f0002b74342d/part-007.jsonl`

## 07. معجم المصطلحات الإدارية في المملكة العربية السعودية — 825 معنى، 5 أجزاء

- `07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-001.jsonl`
- `07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-002.jsonl`
- `07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-003.jsonl`
- `07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-004.jsonl`
- `07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-005.jsonl` (25 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/07-c59be8de-20c3-482b-ab57-ce923dfb4cee/part-005.jsonl`

## 08. معجم المصطلحات الإنمائية — 791 معنى، 4 أجزاء

- `08-2932b042-933a-4d5b-af72-8585027ddb6f/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/08-2932b042-933a-4d5b-af72-8585027ddb6f/part-001.jsonl`
- `08-2932b042-933a-4d5b-af72-8585027ddb6f/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/08-2932b042-933a-4d5b-af72-8585027ddb6f/part-002.jsonl`
- `08-2932b042-933a-4d5b-af72-8585027ddb6f/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/08-2932b042-933a-4d5b-af72-8585027ddb6f/part-003.jsonl`
- `08-2932b042-933a-4d5b-af72-8585027ddb6f/part-004.jsonl` (191 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/08-2932b042-933a-4d5b-af72-8585027ddb6f/part-004.jsonl`

## 09. معجم المصطلحات الرياضية — 981 معنى، 5 أجزاء

- `09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-001.jsonl`
- `09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-002.jsonl`
- `09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-003.jsonl`
- `09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-004.jsonl`
- `09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-005.jsonl` (181 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/09-ae041c6d-79e6-42c3-b54b-ffbf28c88b9a/part-005.jsonl`

## 10. معجم المصطلحات الموسيقية — 700 معنى، 4 أجزاء

- `10-b4759d02-40ef-4df5-a818-4081a11c338c/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/10-b4759d02-40ef-4df5-a818-4081a11c338c/part-001.jsonl`
- `10-b4759d02-40ef-4df5-a818-4081a11c338c/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/10-b4759d02-40ef-4df5-a818-4081a11c338c/part-002.jsonl`
- `10-b4759d02-40ef-4df5-a818-4081a11c338c/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/10-b4759d02-40ef-4df5-a818-4081a11c338c/part-003.jsonl`
- `10-b4759d02-40ef-4df5-a818-4081a11c338c/part-004.jsonl` (100 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/10-b4759d02-40ef-4df5-a818-4081a11c338c/part-004.jsonl`

## 11. معجم مصطلحات الحياة الفطرية — 632 معنى، 4 أجزاء

- `11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-001.jsonl`
- `11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-002.jsonl`
- `11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-003.jsonl`
- `11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-004.jsonl` (32 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/11-6a6b2873-4ad1-4a9f-89c7-1f07ccbb476d/part-004.jsonl`

## 12. معجم مصطلحات الخطوط الحديدية — 856 معنى، 5 أجزاء

- `12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-001.jsonl`
- `12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-002.jsonl`
- `12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-003.jsonl`
- `12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-004.jsonl`
- `12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-005.jsonl` (56 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/12-2813060b-8eda-4c7b-8b10-1fc3255305cb/part-005.jsonl`

## 13. معجم مصطلحات الرياضات الإلكترونية — 507 معنى، 3 أجزاء

- `13-54a32a50-2b7e-49c2-9aa4-897f58fae786/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/13-54a32a50-2b7e-49c2-9aa4-897f58fae786/part-001.jsonl`
- `13-54a32a50-2b7e-49c2-9aa4-897f58fae786/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/13-54a32a50-2b7e-49c2-9aa4-897f58fae786/part-002.jsonl`
- `13-54a32a50-2b7e-49c2-9aa4-897f58fae786/part-003.jsonl` (107 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/13-54a32a50-2b7e-49c2-9aa4-897f58fae786/part-003.jsonl`

## 14. معجم مصطلحات الطرق — 387 معنى، 2 أجزاء

- `14-94d205e3-6e93-4b6b-a245-1d5304b3ed7d/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/14-94d205e3-6e93-4b6b-a245-1d5304b3ed7d/part-001.jsonl`
- `14-94d205e3-6e93-4b6b-a245-1d5304b3ed7d/part-002.jsonl` (187 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/14-94d205e3-6e93-4b6b-a245-1d5304b3ed7d/part-002.jsonl`

## 15. معجم مصطلحات القطاع غير الربحي — 521 معنى، 3 أجزاء

- `15-2885a7fb-c347-4390-92c9-808c9b9b17c2/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/15-2885a7fb-c347-4390-92c9-808c9b9b17c2/part-001.jsonl`
- `15-2885a7fb-c347-4390-92c9-808c9b9b17c2/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/15-2885a7fb-c347-4390-92c9-808c9b9b17c2/part-002.jsonl`
- `15-2885a7fb-c347-4390-92c9-808c9b9b17c2/part-003.jsonl` (121 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/15-2885a7fb-c347-4390-92c9-808c9b9b17c2/part-003.jsonl`

## 16. معجم مصطلحات الموارد البشرية والتنمية الاجتماعية — 446 معنى، 3 أجزاء

- `16-4fc63968-9cd8-47d9-a32e-aadc6c6a265b/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/16-4fc63968-9cd8-47d9-a32e-aadc6c6a265b/part-001.jsonl`
- `16-4fc63968-9cd8-47d9-a32e-aadc6c6a265b/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/16-4fc63968-9cd8-47d9-a32e-aadc6c6a265b/part-002.jsonl`
- `16-4fc63968-9cd8-47d9-a32e-aadc6c6a265b/part-003.jsonl` (46 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/16-4fc63968-9cd8-47d9-a32e-aadc6c6a265b/part-003.jsonl`

## 17. معجم مصطلحات تصنيع السيارات الكهربائية وصيانتها — 1061 معنى، 6 أجزاء

- `17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-001.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-001.jsonl`
- `17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-002.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-002.jsonl`
- `17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-003.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-003.jsonl`
- `17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-004.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-004.jsonl`
- `17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-005.jsonl` (200 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-005.jsonl`
- `17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-006.jsonl` (61 معنى): الرسالة ← البرومبت أعلاه ثم: `Input file: https://raw.githubusercontent.com/saraabduallh-1/kass-layer/main/data/dictionaries/enriched/variants/chatgpt/inputs/17-0f0ad290-0fa5-4983-bb56-7144c641cc8c/part-006.jsonl`
