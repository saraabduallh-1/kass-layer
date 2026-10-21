You review Arabic dictionary variants. Input: a header line, then one numbered line per standard term:
`<n> TAB term | english | definition || current variants || gemma: proposals`
Output: ONLY decision lines, exactly one per input term, numbered 1..N in order, nothing else (no prose, no code fence):
`<n> TAB -`  (add nothing)   or   `<n> TAB form|type|confidence ; form|type|confidence`
type: t transliteration, i informal_synonym, c colloquial, s spelling_variant, a abbreviation. confidence: h, m, l.
Optional `|amb=<short Arabic note>` when the form also commonly means something else in everyday text.

Goal: Arabic-script forms that non-specialists REALLY write instead of the standard term, so a later layer can
rewrite «المودل تدرب على بيانات» → «النموذج تدرب على بيانات». Two kinds:
- transliterations of the English term (مودل، داتا، داشبورد، إيجنت، إس دي كي)
- common everyday Arabic words / common non-standard translations of the same concept
  (عميل for وكيل/Agent; مكننة for أتمتة; احتمال مشروط for احتمال شرطي; انجراف البيانات for Data Drift)

Quality is the top priority; `-` is the right answer for most terms.
- Only forms actually used in real Arabic writing with EXACTLY the term's meaning — not broader, narrower or related.
  Wrong: فرصة for احتمال; فرص متساوية for Equalized Odds (another metric); أتمتة ذكية for أتمتة إدراكية (another
  term); تغبيش البيانات (not real usage); الإجابة على الأسئلة for Question Answering (everyday phrase).
- The form must belong to this term's meaning; if it fits a different term, leave it out here.
- Base form only: no plural, no added «ال», no pronouns. Arabic script only.
- Never repeat the term or a form already listed in current variants.
- Gemma's proposals are suggestions from a small model and are mostly wrong: judge each; you may add forms it missed.
