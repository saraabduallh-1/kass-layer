# Decision test — gemma3:12b as yes/no judge (Jev fallback)

600 cases (300 should replace, 300 should not: same form, different term). Errors: 0.
Some negatives pair a form with a near-synonymous term from another dictionary, so a few 'wrong replacements' may be acceptable: check the sample below.

Accuracy 0.66 · precision 0.615 · recall 0.853 (tp 256, fp 160, fn 44, tn 140)

| confidence ≥ | auto-replaced | share | precision | wrong replacements |
|---|---|---|---|---|
| 0.5 | 416 | 0.693 | 0.615 | 160 |
| 0.6 | 416 | 0.693 | 0.615 | 160 |
| 0.7 | 416 | 0.693 | 0.615 | 160 |
| 0.8 | 416 | 0.693 | 0.615 | 160 |
| 0.9 | 414 | 0.69 | 0.614 | 160 |
| 0.95 | 414 | 0.69 | 0.614 | 160 |

## Sample of wrong answers

- kept «DEP» → مغادرة (DEP), conf 0.95: الوقت DEP هو 10 صباحاً.
- kept «تراش» → هطف (trash), conf 0.95: لا تدع التراش يجمع عليك.
- kept «RPH» → طائرة عمودية مقادة من بعد (RPH), conf 0.95: تم تسليم أول RPH في الموقع الأسبوع الماضي.
- kept «recovery» → استخلاص (recovery), conf 0.8: تاريخ استرجاع (recovery) الطائرة.
- kept «إثبات الفكرة» → إثبات المفهوم (Proof of Concept (PoC)), conf 0.8: قبل الاستثمار، يجب إثبات الفكرة أولاً.
- kept «BOM» → فاتورة اللوازم والمعدات ((BOM)   Bill Of Materials), conf 0.95: نظامنا يستخدم BOM لإدارة المخزون.
- kept «تقييد» → التكبيل (), conf 0.8: تم تقييد حركة المشتبه به في المكان.
- kept «المثليات» → الأشياء المثلية (), conf 0.8: في هذه الوثيقة، تم التعامل مع المثليات ككيان واحد.
- kept «pass» → تمرير (Pass), conf 0.95: الـ pass كان سريعاً جداً.
- kept «سلوكيات» → سلوك (behavior), conf 0.8: دراسة السلوكيات البشرية.
- kept «صاج» → صاجة (), conf 0.95: يحتوي الصاج على قطعتين.
- kept «مشتعل» → ملتهب (ablaze), conf 0.8: المنطقة أصبحت مشتعل من الدخان.
- kept «الجهة» → الهيئة (), conf 0.8: الجهة المختصة ستقوم بالتحقيق.
- kept «القانون» → النظام (Law), conf 0.95: يجب علينا دراسة القانون الجديد.
- kept «بوست» → تعزيز (Boosting), conf 0.95: أرسلني لبوست في اللعبة.
