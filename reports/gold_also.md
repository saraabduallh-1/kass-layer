# Gold sets: right suggestions they did not list (2026-11-08)

The gold sets list one expected replacement per sentence, so a right extra suggestion counted as an error. Every extra and
every "wrong term" was judged in its sentence by Claude (not an independent check). Accepted ones are in a new `also`
field; `expect` is unchanged. An accepted extra counts as neither correct nor extra; an accepted alternative for an
expected word counts as correct. Both runners (`run_tests.js`, `run_tests.py`) read `also`.

## Accepted

| Set | Word → term | Sentence |
|---|---|---|
| tuning | لازم → يجب | لازم نحط ستيكر على المنتج قبل التوزيع |
| heldout-1 | الكود → الشفرات المصدرية | المبرمج كتب الكود وراجعه زميله |
| heldout-1 | القضية → الدعوى | القضية راحت للأربتريشن بدل المحكمة |
| heldout-1 | لازم → يجب | الشركة لازم تلتزم بالكومبلاينس |
| heldout-1 | السواق → قائد المركبة; البريك → فرملة | السواق ضغط على البريك فجأة |
| heldout-1 | أوبن سورس → برمجيات مفتوحة المصدر (instead of البرمجيات الحرة ومفتوحة المصدر) | نستخدم برامج أوبن سورس في الجامعة |
| heldout-1 | الليسنق → إيجار (instead of عقد إيجار) | وقعنا عقد الليسنق للسيارات |
| ambiguity | للمسلسل → سلسلة درامية | نزلت القناة تيزر للمسلسل قبل موعد العرض |
| ambiguity | الكود → الشفرات المصدرية | شغلنا الكود في ساندبوكس … |
| ambiguity | التورك → عزم فتل (instead of عزم المحرك الكهربائي) | قسنا التورك حق المحرك الكهربائي في المختبر |
| arabic-tuning | دفعة صغيرة → حزمة صغيرة | قسمنا بيانات التدريب إلى دفعة صغيرة … |
| arabic-tuning | المعالج → وحدة المعالجة المركزية | … شغلنا النموذج اللغوي على المعالج بدل وحدة معالجة الرسومات |
| arabic-tuning | الرؤية الحاسوبية → رؤية الحاسب | … دقة نموذج الرؤية الحاسوبية |
| arabic-tuning | الخبر العاجل → أخبارعاجلة | مقدم النشرة الإخبارية قرأ الخبر العاجل على الهواء |
| arabic-heldout | حجم الدفعة → حجم الحزمة | حجم الدفعة في تدريب الشبكة العصبية … |
| arabic-heldout | النشرة → نشرة أخبار | المذيع ومقدم النشرة قرأ الأخبار العاجلة على القناة |
| arabic-heldout | المحطة الكهربائية → محطة إنتاج الكهرباء | انقطع التيار عن المحطة الكهربائية … |
| arabic-heldout | الكود → الشفرات المصدرية | المبرمج كتب الكود وراجعه مع زملائه |

## Still counted as errors

الإنترست → فائدة and ريت → صندوق الاستثمار العقاري (the phrase is «الإنترست ريت», interest rate), بريزنتيشن → تمثيل,
اللاندنق قير → منطقة الهبوط, تشارجر → حاملة, كلاود → حوسبة سحابية («الجي كلاود» is a name), بحضور → المواظبة,
المنصة → المنصة الرقمية, باستقلالية → تحكم ذاتي, على الهواء → بث على الهواء مباشرة, للمؤتمر الصحفي → المؤتمر الصحفي
الحكومي (narrower), بيان صحفي → تصريح صحفي, استوديو → استوديو إنتاج, الضوضاء → تشويش (neighbours' noise),
الأخبار العاجلة → صحافة فورية; wrong terms بالكومبلاينس → الالتزام, تشل → مسترخ, السكانر → ماسح, ساندبوكس → بيئة الوكيل
المعزولة.

## Scores (recall / precision)

| Set | Before | After |
|---|---|---|
| tuning | 93.8 / 88.2 | 93.8 / 90.0 |
| heldout-1 | 81.0 / 65.4 | 90.5 / 90.5 |
| heldout-2 | 94.7 / 100 | 94.7 / 100 |
| ambiguity | 71.4 / 62.5 | 78.6 / 78.6 |
| arabic-tuning | 67.7 / 65.6 | 67.7 / 75.0 |
| arabic-heldout | 66.7 / 53.3 | 66.7 / 72.7 |
