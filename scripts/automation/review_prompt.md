You are running unattended (the user is away for days). Do the Arabic enrichment pass-2 review below, then stop.
Never ask questions, never commit or push (the autopilot script does that), never edit code or any file other than
your decision files under logs/decisions/.

## Goal
Add Arabic-script variants that non-specialists REALLY write instead of each standard dictionary term, so a later
layer can rewrite «المودل تدرب على بيانات» → «النموذج تدرب على بيانات». Two kinds matter:
- transliterations of the English term (مودل، داتا، داشبورد، إيجنت)
- common everyday Arabic words / common non-standard translations used for the same concept
  (عميل for وكيل/Agent; مكننة for أتمتة; احتمال مشروط for احتمال شرطي; عينة ميسرة for أخذ عينات سهلة)

Quality is the top priority. Adding nothing is the right answer for most terms.
- Only forms actually used in real Arabic writing, with EXACTLY the term's meaning — not broader, narrower or related.
  Rejected examples: فرصة for احتمال (different meaning); فرص متساوية for Equalized Odds (a different metric);
  أتمتة ذكية for أتمتة إدراكية (another term in the dictionary); تغبيش البيانات (not real usage);
  الإجابة على الأسئلة for Question Answering (an everyday phrase: replacing it would break normal text).
- A form must map to the term whose meaning it matches. If it belongs to a different term, skip it here.
- Base form only: no plural, no added «ال», no pronouns. Arabic script only (Latin forms already exist from pass 1).
- Never repeat the term itself or a form already listed after `||`.
- Gemma's proposals (after `|| gemma:`) are only suggestions from a small local model; most are wrong. Judge each one.
  You may add a good form Gemma missed.
- If a form also commonly means something else in everyday text, add `|amb=<short Arabic note>`.

## Procedure (repeat for up to {BATCHES} batches, then stop)
1. Run: `.venv/Scripts/python scripts/enrich/arabic_pass.py ready`
   Each line is `<ready> TAB <pending> TAB <dictionary id prefix>`. Pick the first dictionary in this priority order
   with ready > 0: 4cd164a7, 0f465c61, 89af196b, then any other. If every ready count is 0, stop.
2. Run: `.venv/Scripts/python scripts/enrich/arabic_pass.py show <prefix> --ready --limit 100 --width 160`
   Each line: `<n> TAB term | english | definition || current variants || gemma: proposals`.
3. Write a decisions file `logs/decisions/<prefix>-<YYYYMMDD-HHMMSS>.txt` with EXACTLY one line per shown term,
   numbered 1..N in order:  `<n> TAB -`  (add nothing)  or  `<n> TAB form|type|confidence ; form|type|confidence`
   type: t transliteration, i informal_synonym, c colloquial, s spelling_variant, a abbreviation
   confidence: h, m, l.  Example lines:  `4	تناسق زمني|i|m`   `7	مكننة|s|m`   `9	-`
4. Run: `.venv/Scripts/python scripts/enrich/arabic_pass.py apply <prefix> logs/decisions/<file>`
   It prints how many senses were covered and forms added. If it fails, fix the decisions file and re-apply.
5. Go back to step 1.

End with one line: batches done, senses covered, forms added.
