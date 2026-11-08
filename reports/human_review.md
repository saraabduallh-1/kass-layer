# Human review of 50 tweet judgements (2026-11-08)

The project owner judged a random sample of 50 of the 310 tweet cases (`logs/review_sample_50.xlsx`, seed 11; tweets
stay local): «أوافق» = the suggested term should be used in this tweet, «لا أوافق» = it should not, or «غير متأكدة».

- 37 sure answers, 13 unsure (one tweet marked unclear).
- Agreement with Claude's labels on the sure answers: 29 of 37 (78.4%).
- Disagreements: 5 where Claude said no and the owner said yes (استحضار المعلومات، رسكلة، ركوب الدراجات الهوائية، مسايفة،
  وسائل التواصل الاجتماعي) and 3 where Claude said yes and the owner said no, all pairs whose meanings are
  close but not the same (حرية الرأي والتعبير → حرية التعبير، كثافة السكان → الكثافة السكانية، مكتبة افتراضية → مكتبة رقمية).
- The detector on the same 37 cases, scored with the owner's labels: 22 suggestions, 15 right (precision 68.2%);
  15 of the 21 cases that should be suggested found (recall 71.4%). With Claude's labels on the same cases: 59.1% / 68.4%.
  Tweets are the hardest set (short, no context), so these numbers are lower than on articles.
