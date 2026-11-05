# اختبار الصيغ المضافة على تغريدات حقيقية (2026-11-05)

310 تغريدة، واحدة لكل صيغة أضافها البحث عن الاستخدام الحقيقي. حكم Claude على كل تغريدة قبل تشغيل الكاشف: هل الصيغة فيها بمعنى المصطلح؟ (162 نعم، 148 لا). الأحكام من Claude وليست تصحيحًا مستقلًا. التغريدات من pain/Arabic-Tweets وتبقى على الجهاز.

| | الاستدعاء | الإنذارات الكاذبة | الدقة |
|---|---|---|---|
| الصيغ كما أضيفت | 41.4% | 32.4% | 58.3% |
| بعد قبول الصيغة متعددة الكلمات من نوع «إملاء آخر» دون دليل من السياق (دارة كهربائية) | 54.3% | 40.5% | 59.5% |
| بعد سحب 9 كلمات مفردة لها معنى آخر شائع (غرانت، جسون، حكامة، كنبان، نفثا، إثين، لجنيت) | 54.3% | 37.2% | 61.5% |

السطر الأخير ضُبط على هذا الاختبار نفسه، فهو متفائل قليلًا. أرقام الاختبارات الستة لم تتغير، والتطابق 212/212.
أكبر مصدر للأخطاء الباقية: كلمات يومية تأتي بمعنى آخر في جمل قصيرة بلا سياق (سهم ممتاز = اختيار جيد، مقاطعة = حديث).

## 2026-11-05: the common-word rule applies to single words only

A common first word (مؤسسة، وسائل) no longer blocks a whole phrase: recall 57.4%, precision 62.4%, false alarms 37.8% (93 tp, 69 fn, 56 fp, 92 tn).
Error analysis of the 74 misses before this step: 50 were blocked by the context rules, 21 sat on a word that is a standard term elsewhere (some of these are already SIWAR terms, so not real misses), and 3 matched a second SIWAR term for the same concept (بلوك تشين / سلسلة الكتل).
Tried and rejected: letting every multi-word phrase skip the context check (recall 76.5% but false alarms 68.2%).
