"""Short version of the Kass deck: 8 slides, one idea each. Reuses the helpers and the architecture slide of build_deck.py.

  .venv/Scripts/python reports/presentation/build_deck_short.py
  powershell reports/presentation/export_deck.ps1 -Name kass_layer_deck
"""
from pathlib import Path

SRC = (Path(__file__).resolve().parent / "build_deck.py").read_text(encoding="utf-8")
exec(SRC[:SRC.index("# ───────────────────────── 1. Title")])
OUT = HERE / "kass_layer_deck_raw.pptx"


def big_stat(s, x, y, w, num, lab, col=GREEN):
    text(s, x, y, w, 0.8, num, size=40, color=col, font=BOLD, bold=True)
    text(s, x, y + 0.82, w, 0.5, lab, size=14, color=MUTED)


# 1 ── title (same as the detailed deck)
exec(SRC[SRC.index("# ───────────────────────── 1. Title"):SRC.index("# ───────────────────────── 2. Problem")])

# 2 ── problem
s = frame("الكاتب يكتب بلغته، لا بلغة المعجم", "المشكلة", 2)
rows = [("المودل", "نموذج", "تعريب"), ("LLM", "نموذج لغوي كبير", "اختصار"), ("سولار بانلز", "ألواح كهروضوئية", "إنجليزي بحروف عربية"),
        ("عميل ذكي", "وكيل ذكي", "كلمة عربية عامة")]
x0, rw = 2.4, 8.53
for i, (a, b, kind) in enumerate(rows):
    y = 1.75 + i * 0.98
    last = i == len(rows) - 1
    box(s, x0, y, rw, 0.8, fill=REV_BG if last else SURF, line=REV if last else LINE, lw=1.2 if last else 0.75)
    text(s, x0 + rw - 2.9, y, 2.7, 0.8, a, size=22, font=SEMI, anchor=MSO_ANCHOR.MIDDLE)
    arrow(s, x0 + rw - 3.05, y + 0.4, x0 + rw - 3.65, y + 0.4, color=GREEN, w=2.25)
    text(s, x0 + 1.9, y, 2.9, 0.8, b, size=22, font=SEMI, color=GREEN, anchor=MSO_ANCHOR.MIDDLE)
    pill(s, x0 + 0.2, y + 0.24, 1.55, kind, "ffffff" if last else BG2, REV if last else MUTED, size=10.5, h=0.32)
text(s, x0, 5.85, rw, 0.6, [[("الأصعب: ", {"bold": True, "color": REV}), ("«عميل» في نص عن الذكاء الاصطناعي وكيل، وفي «وقّع العميل العقد» زبون.", {})]],
     size=15, align=PP_ALIGN.CENTER)

# 3 ── how it works
s = frame("كيف تعمل الطبقة؟ ثلاث خطوات", "الفكرة", 3)
steps = [("١", "قاموس جاهز", "لكل مصطلح في سوار، الكلمات التي يكتبها الناس بدلًا منه", "40,102 مصطلح · 87,399 صيغة"),
         ("٢", "البحث في النص", "يقرأ النص ويجد كل كلمة لها مصطلح معتمد", "المودل ← نموذج"),
         ("٣", "قرار الثقة", "معرّب أو اختصار: «مقترح»\nكلمة عربية عامة: «يحتاج تدقيقًا» إذا أيدها السياق", "عميل ← وكيل؟")]
cw, gap = 3.6, 0.62
for i, (n_, t, d, ex) in enumerate(steps):
    x = W - 0.6 - (i + 1) * cw - i * gap
    box(s, x, 1.75, cw, 3.9, fill=SURF, line=LINE)
    box(s, x + cw / 2 - 0.4, 2.0, 0.8, 0.8, fill=GREEN, line=None, radius=0.4, shape=MSO_SHAPE.OVAL)
    text(s, x + cw / 2 - 0.4, 2.0, 0.8, 0.8, n_, size=24, color="ffffff", font=BOLD, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, 3.0, cw - 0.5, 0.5, t, size=21, font=BOLD, bold=True, align=PP_ALIGN.CENTER)
    text(s, x + 0.25, 3.6, cw - 0.5, 1.2, d.split("\n"), size=14, color=MUTED, align=PP_ALIGN.CENTER, spacing=1.3)
    pill(s, x + 0.45, 4.95, cw - 0.9, ex, MINT, GREEN, size=13, h=0.42)
    if i < 2:
        arrow(s, x - 0.08, 3.7, x - gap + 0.08, 3.7, color=GREEN, w=2.5)
text(s, 0.6, 5.95, W - 1.2, 0.5, "لا نموذج لغوي وقت التحليل: كل شيء يعمل داخل المتصفح، والمستخدم يقرر.", size=15, color=MUTED, align=PP_ALIGN.CENTER)

# 4 ── architecture (the detailed slide)
arch = SRC[SRC.index("# ───────────────────────── 5. System architecture"):SRC.index("# ───────────────────────── 6. Worked example")]
exec(arch.replace('"البنية التقنية · System Architecture", 5)', '"البنية التقنية · System Architecture", 4)'))

# 5 ── reading the architecture
s = frame("كيف تُقرأ البنية؟ خطوة خطوة", "شرح البنية", 5)
box(s, W - 0.6 - 3.0, 1.65, 3.0, 4.85, fill="fbf6ea", line="6b5a2e", lw=1.0)
text(s, W - 0.6 - 2.8, 1.8, 2.6, 0.45, "قبل التشغيل · مرة واحدة", size=14, font=BOLD, bold=True, color="6b5a2e")
text(s, W - 0.6 - 2.8, 2.35, 2.6, 4.0, [
    "نبني القاموس:",
    [("مصطلحات سوار", {"bold": True})],
    "+ الصيغ التي ولّدتها النماذج",
    "+ ما يكتبه الناس فعلًا",
    [("مراجعة Claude لكل شيء", {"bold": True})],
    "ثم نحفظه فهارس جاهزة تُحمَّل إلى المتصفح."], size=13.5, spacing=1.25, space_after=7)
steps = [("① التطبيع", "توحيد الكتابة: التشكيل، الهمزات، «ال» و«و»"),
         ("② المطابقة", "البحث عن كل كلمة في القاموس، ومعها الاختصارات والإنجليزي المكتوب بالعربي"),
         ("③ المعجم الأقرب", "أي معاجم المجال المختار أقرب إلى هذا النص"),
         ("④ بوابة السياق", "للكلمة العربية العامة فقط: هل يتكلم النص عن المجال؟"),
         ("⑤ المرشّحات", "حذف الأعلام، والاختصار لاسم قبله، وما يكتبه الكاتب صحيحًا"),
         ("⑥ ترتيب البدائل", "إن كان للكلمة أكثر من مصطلح، أيها الأنسب"),
         ("⑦ التصنيف", "مقترح · يحتاج تدقيقًا · معتمد"),
         ("قرار المستخدم", "يختار المصطلح أو بديلًا أو يُبقي كلمته"),
         ("نموذج الشركة (مخطط)", "يضبط الإفراد والجمع والتذكير والتأنيث")]
gw, gh, gx0 = 2.76, 1.45, W - 0.6 - 3.0 - 0.3
for i, (t, d) in enumerate(steps):
    col, row = i % 3, i // 3
    x = gx0 - (col + 1) * gw - col * 0.2
    y = 1.65 + row * (gh + 0.25)
    last = i == len(steps) - 1
    user = i == len(steps) - 2
    box(s, x, y, gw, gh, fill=GREEN if user else SURF, line=STD if last else (None if user else LINE), dash=last, lw=1.2 if last else 0.75)
    text(s, x + 0.18, y + 0.12, gw - 0.36, 0.42, t, size=15, font=BOLD, bold=True, color="ffffff" if user else (STD if last else GREEN))
    text(s, x + 0.18, y + 0.58, gw - 0.36, 0.82, d, size=12.5, color="d9eadf" if user else MUTED, spacing=1.2)

# 6 ── worked example
s = frame("مثال حقيقي، كما يراه المستخدم", "التجربة", 6)
box(s, 0.6, 1.7, W - 1.2, 1.6, fill=SURF, line=LINE)
runs = [("بنينا ", {}), ("عميل ذكي", {"color": REV, "bold": True}), (" يستخدم ", {}), ("المودل", {"color": REP, "bold": True}),
        (" والـ ", {}), ("LLM", {"color": REP, "bold": True}), (" ", {}), ("لتحليل البيانات", {"color": STD, "bold": True})]
text(s, 0.9, 1.7, W - 1.8, 1.6, [runs], size=30, font=SEMI, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
tiers = [("مقترح", REP, REP_BG, "المودل ← نموذج\nLLM ← نموذج لغوي كبير", "معرّب واختصار: لا معنى آخر لهما"),
         ("يحتاج تدقيقًا", REV, REV_BG, "عميل ذكي ← وكيل ذكي", "كلمة عامة؛ السياق عن الذكاء الاصطناعي"),
         ("معتمد", STD, STD_BG, "تحليل البيانات", "مصطلح معتمد أصلًا، لا يُقترح شيء")]
tw = (W - 1.2 - 2 * 0.3) / 3
for i, (lab, col, fill, what, why) in enumerate(tiers):
    x = W - 0.6 - (i + 1) * tw - i * 0.3
    box(s, x, 3.6, tw, 2.85, fill=fill, line=None)
    text(s, x + 0.25, 3.75, tw - 0.5, 0.5, lab, size=19, font=BOLD, bold=True, color=col)
    text(s, x + 0.25, 4.35, tw - 0.5, 1.1, what.split("\n"), size=17, font=SEMI, spacing=1.25)
    text(s, x + 0.25, 5.55, tw - 0.5, 0.7, why, size=13, color=MUTED)

# 6 ── results
s = frame("النتائج: المؤكد موثوق، والكلمات العربية العامة هي الفجوة", "النتائج", 7)
big_stat(s, W - 0.6 - 3.6, 1.85, 3.6, "91%", "دقة «مقترح» في ملفات الاختبار، و15 من 15 في مقالات جديدة", REP)
big_stat(s, W - 0.6 - 3.6, 3.75, 3.6, "74 إلى 80%", "دقة «يحتاج تدقيقًا»: 74% في المقالات و80% في اختبار الكلمات العربية المستقل", "b07a1a")
cd = CategoryChartData()
cd.categories = ["ملفات الاختبار", "مقالات جديدة"]
cd.add_series("مقترح", (90.9, 100.0))
cd.add_series("يحتاج تدقيقًا", (80.0, 74.0))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.65), Inches(8.0), Inches(4.6), cd)
ch = gf.chart
style_chart(ch, 13)
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
pl = ch.plots[0]
pl.gap_width = 80
pl.overlap = -10
for ser, col in zip(pl.series, (REP, "c9922e")):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = rgb(col)
pl.has_data_labels = True
pl.data_labels.number_format = '0"%"'
pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(14)
pl.data_labels.font.bold = True
va = ch.value_axis
va.maximum_scale, va.minimum_scale, va.major_unit = 100, 0, 25
va.visible = False
va.has_major_gridlines = False
ch.category_axis.reverse_order = True
ch.category_axis.tick_labels.font.size = Pt(14)
text(s, W - 0.6 - 3.6, 5.6, 3.6, 0.7, "الأحكام من Claude؛ المراجعة البشرية جارية.", size=12, color=MUTED)

# 7 ── what we learned
s = frame("ما جرّبناه، وحدود ما قسناه", "بصراحة", 8)
for i, (title, col, fill, items) in enumerate([
        ("جرّبنا لفهم السياق ولم يكفِ", RED, RED_BG, ["نموذج لغوي يحكم على السياق: 60 إلى 62%", "مقارنة المعنى بالأرقام (embeddings): ضعيفة", "مصنّف متعلم: لا يعمّم على نصوص جديدة"]),
        ("حدود التقييم", REV, REV_BG, ["الأحكام من Claude، والمراجعة البشرية جارية", "عينات المقالات الجديدة صغيرة", "بعض القواعد صُمّمت بعد رؤية الأخطاء"])]):
    x = W - 0.6 - (i + 1) * 5.95 - i * 0.23
    box(s, x, 1.75, 5.95, 3.35, fill=SURF, line=LINE)
    box(s, x, 1.75, 5.95, 0.75, fill=fill, line=None, radius=0.08)
    text(s, x + 0.3, 1.75, 5.35, 0.75, title, size=19, font=BOLD, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, x + 0.3, 2.85, 5.35, 2.2, items, size=17, gap=16, mark_color=col)
box(s, 0.6, 5.45, W - 1.2, 0.9, fill=MINT, line=None, radius=0.1)
text(s, 0.6, 5.45, W - 1.2, 0.9, "لذلك صار التصميم صريحًا: ما لا نثق به يُعرض للتدقيق بسببه، ولا يُطبَّق آليًّا.", size=17, color=GREEN, font=SEMI, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# 8 ── next
s = frame("الخطوة التالية: نموذج الشركة يضبط الصيغة فقط", "الخطة", 9)
for i, (lab, sent, fill, line) in enumerate([("ما كتبه المستخدم", "درّبنا المودلز الكبيرة", SURF, LINE),
                                             ("بعد إدراج المصطلح", "درّبنا النموذج الكبيرة", REV_BG, REV),
                                             ("بعد نموذج الشركة", "درّبنا النماذج الكبيرة", REP_BG, REP)]):
    x = W - 0.6 - (i + 1) * 3.75 - i * 0.37
    box(s, x, 1.8, 3.75, 1.55, fill=fill, line=line, lw=1.0)
    text(s, x + 0.2, 1.9, 3.35, 0.4, lab, size=12, color=MUTED, font=SEMI, align=PP_ALIGN.CENTER)
    text(s, x + 0.2, 2.35, 3.35, 0.8, sent, size=21, font=SEMI, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if i < 2:
        arrow(s, x - 0.05, 2.57, x - 0.32, 2.57, color=GREEN, w=2.25)
text(s, 0.6, 3.55, W - 1.2, 0.45, [[("يضبط ", {"color": GREEN, "bold": True}), ("الإفراد والجمع والتذكير والتأنيث فقط  ·  ", {}),
                                   ("لا ", {"color": RED, "bold": True}), ("يختار المصطلح ولا يعيد صياغة النص", {})]], size=15, align=PP_ALIGN.CENTER)
nexts = [("نشر النسخة الأخيرة", "على kass.arai.center"), ("مراجعة بشرية مستقلة", "لعينة من 50 حكمًا"), ("إثراء «وكيل»", "و67 مصطلحًا بلا اسم إنجليزي")]
nw = (W - 1.2 - 2 * 0.3) / 3
for i, (t, d) in enumerate(nexts):
    x = W - 0.6 - (i + 1) * nw - i * 0.3
    box(s, x, 4.3, nw, 1.25, fill=SURF, line=LINE)
    text(s, x + 0.25, 4.42, nw - 0.5, 0.45, t, size=17, font=BOLD, bold=True)
    text(s, x + 0.25, 4.92, nw - 0.5, 0.5, d, size=13.5, color=MUTED)
box(s, 0.6, 5.85, W - 1.2, 0.65, fill=GREEN, line=None, radius=0.1)
text(s, 0.85, 5.85, W - 1.7, 0.65, "الطبقة تعرف المصطلح المعتمد، والمستخدم يقرر، ونموذج الشركة يضبط الصيغة.", size=16, color="ffffff", font=SEMI,
     anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
