"""Builds the Kass Layer technical deck (RTL, editable shapes and native charts).

  .venv/Scripts/python reports/presentation/build_deck.py
Writes reports/presentation/kass_layer_deck_raw.pptx; export_deck.ps1 embeds the fonts and writes the final PPTX and PDF.
Every number on the slides comes from the repository: HANDOFF.md, reports/launch_precision.md, reports/gold_also.md,
reports/usage_tweets_test.md, data/dictionaries/enriched/variants/report.json and the detector itself.
"""
import re
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.dml import MSO_LINE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
OUT = HERE / "kass_layer_deck_raw.pptx"

# identity of the Kass page (scripts/demo/kass-lab.html)
BG, BG2, SURF, INK, MUTED, LINE = "f6f7f2", "eef2ea", "ffffff", "14231d", "5b6b63", "dde5dd"
GREEN, GREEN2, MINT, MINT2 = "0b4b33", "12633f", "e5efe7", "d5e6da"
REP, REP_BG, REV, REV_BG, STD, STD_BG = "1b7448", "e1f1e7", "94620a", "f8edd6", "3d5d74", "e4ecf2"
RED, RED_BG = "8a3b2a", "f6e4df"
BODY, BOLD = "IBM Plex Sans Arabic", "IBM Plex Sans Arabic"
SEMI = "IBM Plex Sans Arabic SemiBold"

W, H = 13.333, 7.5
_W = r"[A-Za-z0-9][A-Za-z0-9.+_/\-]*"
LATIN = re.compile(r"[A-Za-z][A-Za-z0-9.+_/\-]*(?:[ ](?:" + _W + r"|\(" + _W + r"(?:[ ]" + _W + r")*\)))*")
prs = Presentation()
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
BLANK = prs.slide_layouts[6]


def rgb(h):
    return RGBColor.from_string(h)


def rtl(p, align=PP_ALIGN.RIGHT):
    p.alignment = align
    p._p.get_or_add_pPr().set("rtl", "1")


def text(slide, x, y, w, h, paras, size=16, color=INK, font=BODY, bold=False, align=PP_ALIGN.RIGHT,
         anchor=MSO_ANCHOR.TOP, spacing=1.15, space_after=0, margin=0.0):
    """paras: str, or list of paragraphs; a paragraph is a str or a list of runs (text, {size,color,bold,font})."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, side, Inches(margin))
    if isinstance(paras, str):
        paras = [paras]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        rtl(p, align)
        p.line_spacing = spacing
        p.space_after = Pt(space_after)
        runs = para if isinstance(para, list) else [(para, {})]
        for t0, st in runs:
            # Latin names (Qwen3.5-4B) get runs of their own marked English, or PowerPoint reorders their parts
            for k, t in enumerate(re.split("(" + LATIN.pattern + ")", t0)):
                if not t:
                    continue
                latin = k % 2 == 1
                r = p.add_run()
                r.text = t
                f = r.font
                f.name = st.get("font", font)
                f.size = Pt(st.get("size", size))
                f.bold = st.get("bold", bold)
                f.color.rgb = rgb(st.get("color", color))
                rPr = r._r.get_or_add_rPr()
                rPr.set("lang", "en-US" if latin else "ar-SA")
                for tag in ("a:cs", "a:ea"):
                    el = rPr.find(qn(tag))
                    if el is None:
                        el = etree.SubElement(rPr, qn(tag))
                    el.set("typeface", st.get("font", font))
    return tb


def box(slide, x, y, w, h, fill=SURF, line=LINE, radius=0.08, dash=False, lw=1.0, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(0.5, radius / min(w, h))
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
        if dash:
            s.line.dash_style = MSO_LINE.DASH
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    s.text_frame.text = ""
    return s


def arrow(slide, x1, y1, x2, y2, color=MUTED, w=1.5, dash=False, head=True):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(w)
    if dash:
        c.line.dash_style = MSO_LINE.DASH
    if head:
        ln = c.line._get_or_add_ln()
        t = etree.SubElement(ln, qn("a:tailEnd"))
        t.set("type", "triangle")
        t.set("w", "med")
        t.set("len", "med")
    return c


def bg(slide, color=BG):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = rgb(color)


def pill(slide, x, y, w, label, fill, color, size=11, h=0.3):
    box(slide, x, y, w, h, fill=fill, line=None, radius=h / 2)
    text(slide, x, y, w, h, label, size=size, color=color, font=SEMI, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def frame(title, kicker, n, subtitle=None):
    s = prs.slides.add_slide(BLANK)
    bg(s)
    box(s, W - 0.6 - 0.08, 0.55, 0.08, 0.62 if not subtitle else 0.98, fill=GREEN, line=None, radius=0.0, shape=MSO_SHAPE.RECTANGLE)
    text(s, 4.0, 0.3, W - 0.6 - 0.25 - 4.0, 0.3, kicker, size=12, color=GREEN2, font=SEMI)
    text(s, 1.2, 0.58, W - 0.6 - 0.25 - 1.2, 0.6, title, size=28, color=INK, font=BOLD, bold=True)
    if subtitle:
        text(s, 1.2, 1.18, W - 0.6 - 0.25 - 1.2, 0.4, subtitle, size=15, color=MUTED)
    # footer: brand on the right, page number on the left
    s.shapes.add_picture(str(HERE / "wordmark_green.png"), Inches(W - 0.6 - 0.62), Inches(H - 0.47), height=Inches(0.2))
    text(s, W - 0.6 - 4.2, H - 0.5, 3.45, 0.26, "طبقة المصطلحات العربية المعتمدة", size=10, color=MUTED)
    text(s, 0.6, H - 0.5, 1.0, 0.26, f"{n:02d}", size=10, color=MUTED, align=PP_ALIGN.LEFT, font=SEMI)
    s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.6), Inches(H - 0.58), Inches(W - 0.6), Inches(H - 0.58)).line.color.rgb = rgb(LINE)
    return s


def bullets(slide, x, y, w, h, items, size=14, color=INK, gap=6, mark="•", mark_color=GREEN):
    paras = [[(mark + " ", {"color": mark_color, "bold": True}), *(it if isinstance(it, list) else [(it, {})])] for it in items]
    return text(slide, x, y, w, h, paras, size=size, color=color, space_after=gap)


def style_chart(chart, size=12):
    chart.font.name = BODY
    chart.font.size = Pt(size)
    chart.font.color.rgb = rgb(INK)


# ───────────────────────── 1. Title
s = prs.slides.add_slide(BLANK)
bg(s)
box(s, W - 5.3, 0, 5.3, H, fill=GREEN, line=None, radius=0, shape=MSO_SHAPE.RECTANGLE)
s.shapes.add_picture(str(HERE / "wordmark_white.png"), Inches(W - 5.3 + 0.95), Inches(2.35), width=Inches(3.4))
text(s, W - 5.3 + 0.5, 3.75, 4.3, 0.5, "Kass Layer", size=20, color="cfe3d7", font=SEMI, align=PP_ALIGN.CENTER)
text(s, W - 5.3 + 0.5, 4.3, 4.3, 0.9, "طبقة مصطلحات عربية فوق معاجم سوار", size=16, color="ffffff", align=PP_ALIGN.CENTER)
text(s, 0.8, 1.55, 6.9, 1.6, "من لغة الكاتب إلى المصطلح المعتمد", size=38, color=INK, font=BOLD, bold=True, spacing=1.05)
text(s, 0.8, 3.15, 6.9, 1.2, "طبقة تقرأ النص الذي يكتبه غير المتخصص، وتقترح لكل لفظ دخيل أو عامي أو عام المصطلحَ المعتمد في معاجم سوار، ويبقى القرار للمستخدم.",
     size=17, color=MUTED, spacing=1.3)
box(s, 0.8 + 6.9 - 2.6, 4.55, 2.6, 0.05, fill=GREEN, line=None, radius=0, shape=MSO_SHAPE.RECTANGLE)
text(s, 0.8, 4.75, 6.9, 0.8, [[("عرض تقني", {"bold": True, "color": INK}), ("  ·  نوفمبر 2026  ·  فرع ", {}), ("enrichment-pass1", {"font": BODY})]],
     size=14, color=MUTED)
s.shapes.add_picture(str(HERE / "academy.png"), Inches(0.8 + 6.9 - 3.4), Inches(6.2), height=Inches(0.93))

# ───────────────────────── 2. Problem
s = frame("الكاتب غير المتخصص يكتب بلغته، لا بلغة المعجم", "المشكلة", 2)
rows = [("المودل", "نموذج", "تعريب"), ("الداتا", "بيانات", "تعريب"), ("LLM", "نموذج لغوي كبير", "اختصار إنجليزي"),
        ("سولار بانلز", "ألواح كهروضوئية", "إنجليزي بحروف عربية"), ("عميل ذكي", "وكيل ذكي", "كلمة عربية عامة")]
x0, y0, rw = 5.2, 1.75, 7.53
text(s, x0 + rw - 2.6, y0, 2.6, 0.35, "ما يُكتب", size=13, color=MUTED, font=SEMI)
text(s, x0 + 1.95, y0, 2.6, 0.35, "المعتمد في سوار", size=13, color=MUTED, font=SEMI)
for i, (a, b, kind) in enumerate(rows):
    y = y0 + 0.45 + i * 0.82
    last = i == len(rows) - 1
    box(s, x0, y, rw, 0.68, fill=REV_BG if last else SURF, line=REV if last else LINE, lw=1.2 if last else 0.75)
    text(s, x0 + rw - 2.75, y, 2.55, 0.68, a, size=19, font=SEMI, anchor=MSO_ANCHOR.MIDDLE)
    arrow(s, x0 + rw - 2.85, y + 0.34, x0 + rw - 3.35, y + 0.34, color=GREEN, w=2)
    text(s, x0 + 1.65, y, 2.5, 0.68, b, size=19, font=SEMI, color=GREEN, anchor=MSO_ANCHOR.MIDDLE)
    pill(s, x0 + 0.18, y + 0.19, 1.35, kind, REV_BG if not last else "ffffff", REV if last else MUTED, size=10)
text(s, 0.6, 1.75, 4.3, 0.4, "لماذا هي مشكلة؟", size=18, font=BOLD, bold=True)
bullets(s, 0.6, 2.3, 4.3, 2.4, [
    "المعاجم المتخصصة موجودة ومعتمدة، لكن الكاتب لا يعرف المصطلح أو لا يجده وقت الكتابة",
    "النص الناتج يخلط بين التعريب والإنجليزية والعامية، فيضعف توحيد المصطلح",
    "المدقق الإملائي والنحوي لا يعرف أن «المودل» له مقابل معتمد"], size=14, gap=8)
box(s, 0.6, 4.95, 4.3, 1.55, fill=REV_BG, line=None)
text(s, 0.8, 5.05, 3.95, 1.4, [[("الأصعب: ", {"bold": True, "color": REV}), ("الكلمة العربية العادية التي لها معنى تخصصي في سياق ومعنى عام في غيره. «عميل» في نص عن الذكاء الاصطناعي وكيل، وفي «وقّع العميل العقد» زبون.", {})]],
     size=14, spacing=1.3)

# ───────────────────────── 3. Goal and principles
s = frame("الهدف: اقتراح المصطلح المعتمد بدقة، والقرار للمستخدم", "الهدف والنطاق", 3)
stats = [("22", "معجمًا متخصصًا من سوار"), ("40,102", "مصطلح بتعريفه ومقابله الإنجليزي"), ("6", "مجالات في الواجهة"), ("87,399", "صيغة بديلة مراجَعة")]
sw = (W - 1.2 - 3 * 0.25) / 4
for i, (num, lab) in enumerate(stats):
    x = W - 0.6 - (i + 1) * sw - i * 0.25
    box(s, x, 1.65, sw, 1.55, fill=SURF, line=LINE)
    text(s, x + 0.2, 1.8, sw - 0.4, 0.75, num, size=36, color=GREEN, font=BOLD, bold=True)
    text(s, x + 0.2, 2.55, sw - 0.4, 0.5, lab, size=13, color=MUTED)
princ = [("المصطلح من سوار فقط", "لا يُخترع مصطلح ولا يُقترح لفظ ليس في معجم معتمد."),
         ("اقتراح لا استبدال", "النص لا يتغير إلا باختيار المستخدم، كلمةً كلمة."),
         ("لكل اقتراح سبب ومصدر", "المعجم، المقابل الإنجليزي، التعريف، وسبب الحاجة للتدقيق."),
         ("الدقة قبل التغطية", "ما لا نثق به يُعرض للتدقيق أو يُحذف، ولا يُطبَّق آليًّا.")]
pw = (W - 1.2 - 3 * 0.25) / 4
for i, (t, d) in enumerate(princ):
    x = W - 0.6 - (i + 1) * pw - i * 0.25
    box(s, x, 3.55, pw, 2.75, fill=MINT if i == 0 else SURF, line=None if i == 0 else LINE)
    box(s, x + pw - 0.55, 3.8, 0.34, 0.34, fill=GREEN, line=None, radius=0.17)
    text(s, x + pw - 0.55, 3.8, 0.34, 0.34, str(i + 1), size=12, color="ffffff", font=SEMI, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.2, 4.3, pw - 0.4, 0.5, t, size=17, font=BOLD, bold=True)
    text(s, x + 0.2, 4.85, pw - 0.4, 1.3, d, size=13.5, color=MUTED, spacing=1.3)

# ───────────────────────── 4. Data and enrichment
s = frame("الإثراء: ماذا يكتب الناس بدل كل مصطلح؟", "البيانات", 4, "خمس مراحل تُنفَّذ مرة واحدة قبل التشغيل، وكل ما تقترحه النماذج يراجَع قبل أن يدخل الفهرس")
steps = [("سوار", "40,102", "مصطلح في 22 معجمًا؛ الملفات الأصلية لا تُعدَّل"),
         ("توليد الصيغ", "87,399 صيغة", "Qwen3.5-4B يولّد البدائل لكل مصطلح"),
         ("مراجعة Claude", "100%", "روجعت المعاني كلها؛ 50,621 صيغة مؤكدة و36,778 مشروطة بالسياق"),
         ("صيغ عربية وتدقيق", "825 رابطًا سُحب", "Gemma 3 12B يقترح ويصنّف العلاقة، وClaude يقرر"),
         ("الاستعمال الحقيقي", "≈360 صيغة", "ويكي بيانات وويكيبيديا، مفلترة بـ 20 GB تغريدات")]
cw, gap = 2.27, 0.18
for i, (t, num, d) in enumerate(steps):
    x = W - 0.6 - (i + 1) * cw - i * gap
    box(s, x, 1.85, cw, 2.35, fill=SURF, line=LINE)
    box(s, x, 1.85, cw, 0.07, fill=GREEN if i else STD, line=None, radius=0, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 0.18, 2.0, cw - 0.36, 0.35, f"{i + 1}  {t}", size=14, font=SEMI, color=GREEN)
    text(s, x + 0.18, 2.4, cw - 0.36, 0.55, num, size=21, font=BOLD, bold=True)
    text(s, x + 0.18, 3.0, cw - 0.36, 1.15, d, size=12, color=MUTED, spacing=1.25)
    if i < len(steps) - 1:
        arrow(s, x - 0.02, 3.02, x - gap + 0.02, 3.02, color=GREEN, w=1.5)
cd = CategoryChartData()
types = [("صيغة إنجليزية", 61498), ("مرادف عامي", 13410), ("اختصار", 5711), ("تعريب", 3652), ("إملاء آخر", 1743), ("عامية", 1385)]
cd.categories = [t for t, _ in types][::-1]
cd.add_series("الصيغ", [v for _, v in types][::-1])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(5.6), Inches(4.45), Inches(7.13), Inches(2.4), cd)
ch = gf.chart
style_chart(ch, 11)
ch.has_legend = False
ch.has_title = False
pl = ch.plots[0]
pl.gap_width = 45
pl.series[0].format.fill.solid()
pl.series[0].format.fill.fore_color.rgb = rgb(GREEN2)
pl.has_data_labels = True
pl.data_labels.number_format = "#,##0"
pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(10)
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.reverse_order = True
ch.category_axis.format.line.fill.background()
ch.category_axis.tick_labels.font.size = Pt(11)
text(s, 0.6, 4.55, 4.7, 0.4, "أنواع الصيغ البديلة", size=16, font=BOLD, bold=True)
text(s, 0.6, 5.0, 4.7, 1.8, [
    "أكثرها صيغ إنجليزية (Model، Dataset)، ثم المرادفات العامية والاختصارات.",
    [("الصيغة «المشروطة» ", {"bold": True}), ("لا تُقترح إلا إذا أيّدها سياق النص.", {})]], size=13, color=MUTED, spacing=1.3, space_after=6)

# ───────────────────────── 5. System architecture
s = frame("رحلة النص: من الإدخال إلى قرار المستخدم", "البنية التقنية · System Architecture", 5)
# lane backgrounds
box(s, 0.6, 1.4, W - 1.2, 1.35, fill=BG2, line=None, radius=0.1)
box(s, 0.6, 2.95, W - 1.2, 3.3, fill=MINT, line=None, radius=0.1)
text(s, W - 0.6 - 3.2, 1.45, 3.05, 0.3, "قبل التشغيل · مرة واحدة", size=11, color="6b5a2e", font=SEMI)
text(s, W - 0.6 - 3.2, 3.0, 3.05, 0.3, "لكل نص · داخل المتصفح", size=11, color=GREEN, font=SEMI)


def node(x, y, w, h, title, sub="", fill=SURF, line=LINE, tcolor=INK, dash=False, tsize=12.5, ssize=10):
    box(s, x, y, w, h, fill=fill, line=line, dash=dash, lw=1.25 if dash else 0.9, radius=0.07)
    paras = [[(title, {"bold": True, "size": tsize, "color": tcolor})]]
    if sub:
        paras.append([(sub, {"size": ssize, "color": "cfe3d7" if tcolor == "ffffff" else MUTED})])
    text(s, x + 0.06, y + 0.02, w - 0.12, h - 0.04, paras, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.05, font=SEMI)


BUILD = "6b5a2e"
# build lane, right to left
bw, by, bh = 2.05, 1.8, 0.8
bx = [W - 0.6 - 0.2 - bw - i * (bw + 0.36) for i in range(5)]
node(bx[0], by, bw, bh, "معاجم سوار", "22 معجمًا · 40,102 مصطلح", line=BUILD)
node(bx[1], by, bw, bh, "توليد الصيغ", "Qwen3.5-4B · Gemma 3 12B", line=BUILD)
node(bx[2], by, bw, bh, "مراجعة Claude", "قبول · رفض · سحب الخاطئ", line=BUILD)
node(bx[3], by, bw, bh, "الاستعمال الحقيقي", "ويكي بيانات · ويكيبيديا · تغريدات", line=BUILD)
node(bx[4], by, bw, bh, "الفهارس الجاهزة", "الصيغ · ميل السياق · متجهات embeddinggemma", fill="fbf6ea", line=BUILD)
for i in range(4):
    arrow(s, bx[i] - 0.02, by + bh / 2, bx[i + 1] + bw + 0.02, by + bh / 2, color=BUILD)
arrow(s, bx[4] + bw / 2, by + bh + 0.02, bx[4] + bw / 2, 3.42, color=BUILD, w=1.75)
text(s, bx[4] + bw / 2 + 0.06, 2.67, 1.5, 0.25, "تُحمَّل للمتصفح", size=9.5, color=BUILD, align=PP_ALIGN.LEFT)

# run lane row A (right to left): input → normalise → match → domain → context gate
rw_, rh = 1.95, 0.95
ya = 3.45
ax = [W - 0.6 - 0.2 - rw_ - i * (rw_ + 0.33) for i in range(5)]
node(ax[0], ya, rw_, rh, "إدخال النص", "مع اختيار المجال", fill=GREEN, line=None, tcolor="ffffff")
node(ax[1], ya, rw_, rh, "① التطبيع", "التشكيل · الهمزات · السوابق")
node(ax[2], ya, rw_, rh, "② المطابقة", "قاموس · اختصار · صوت · يومي")
node(ax[3], ya, rw_, rh, "③ المعجم الأقرب", "داخل المجال المختار")
gx, gw = ax[4] - 0.5, rw_ + 0.5
node(gx, ya, gw, rh, "④ بوابة السياق", "ميل النص للمجال + قرب المعنى")
for i in range(4):
    arrow(s, ax[i] - 0.02, ya + rh / 2, ax[i + 1] + rw_ + 0.02, ya + rh / 2, color=GREEN)
# row B (left to right): filters → rank → classify → user → company model → output
yb = 4.95
bxs = [0.85 + i * (rw_ + 0.17) for i in range(5)]
node(bxs[0], yb, rw_, rh, "⑤ المرشّحات", "أعلام · اختصار لاسم · مصطلح مستعمل")
node(bxs[1], yb, rw_, rh, "⑥ ترتيب البدائل", "الصوت · السياق · معجم المجال")
node(bxs[2], yb, rw_, rh, "⑦ التصنيف", "مقترح · يحتاج تدقيقًا · معتمد", fill=REP_BG, line=REP)
node(bxs[3], yb, rw_, rh, "قرار المستخدم", "المصطلح أو بديل أو الأصل", fill=GREEN, line=None, tcolor="ffffff")
node(bxs[4], yb, rw_, rh, "نموذج الشركة", "ضبط الإفراد والجمع والتذكير والتأنيث", fill="ffffff", line=STD, dash=True, tcolor=STD)
arrow(s, gx + gw / 2, ya + rh + 0.02, bxs[0] + rw_ / 2, yb - 0.02, color=GREEN)
for i in range(4):
    arrow(s, bxs[i] + rw_ + 0.02, yb + rh / 2, bxs[i + 1] - 0.02, yb + rh / 2, color=STD if i == 3 else GREEN, dash=i == 3)
node(bxs[4] + rw_ + 0.17, yb + 0.12, 1.15, rh - 0.24, "النص النهائي", "", fill=SURF, line=GREEN, tcolor=GREEN)
arrow(s, bxs[4] + rw_ + 0.02, yb + rh / 2, bxs[4] + rw_ + 0.15, yb + rh / 2, color=STD, dash=True)
# tried and not adopted: an LLM judge on the context gate
node(gx + 0.05, 2.98, 2.4, 0.36, "حكم بنموذج لغوي (Clef · Gemma)", "", fill="ffffff", line=RED, dash=True, tcolor=RED, tsize=10)
arrow(s, gx + 1.25, 3.34, gx + 1.25, ya + 0.02, color=RED, dash=True, head=False)
# legend
lx = 0.75
for lab, fill, line, dash in [("منفَّذ ويعمل", SURF, GREEN, False), ("مخطط له", SURF, STD, True), ("جُرِّب ولم يُعتمد", SURF, RED, True)]:
    box(s, lx + 1.55, 6.47, 0.38, 0.22, fill=fill, line=line, dash=dash, lw=1.2, radius=0.04)
    text(s, lx, 6.43, 1.5, 0.3, lab, size=10.5, color=MUTED)
    lx += 2.15
text(s, 7.2, 6.43, 5.55, 0.3, "الكاشف نسختان متطابقتان: JavaScript في المتصفح وPython في الخادم (212 من 212 جملة)", size=10.5, color=MUTED)

# ───────────────────────── 6. Worked example
s = frame("مثال حقيقي من الكاشف، كما يراه المستخدم", "القرار", 6)
box(s, 4.9, 1.65, 7.83, 2.1, fill=SURF, line=LINE)
text(s, 5.1, 1.75, 7.4, 0.3, "النص المُدخل · مجال تقني", size=11, color=MUTED, font=SEMI)
runs = [("بنينا ", {}), (" عميل ذكي ", {"color": REV, "bold": True}), (" يستخدم ", {}), (" المودل ", {"color": REP, "bold": True}),
        (" والـ ", {}), (" LLM ", {"color": REP, "bold": True}), (" ", {}), (" لتحليل البيانات ", {"color": STD, "bold": True})]
text(s, 5.1, 2.25, 7.4, 0.7, [runs], size=22, font=SEMI)
for lab, fill, col, x in [("مقترح", REP_BG, REP, 11.45), ("يحتاج تدقيقًا", REV_BG, REV, 10.05), ("مصطلح معتمد", STD_BG, STD, 8.65)]:
    pill(s, x, 3.2, 1.25, lab, fill, col, size=11)
res = [("المودل", "نموذج", "مقترح", REP, REP_BG, "تعريب له مصطلح واحد في معجم البيانات والذكاء الاصطناعي (Model)"),
       ("LLM", "نموذج لغوي كبير", "مقترح", REP, REP_BG, "اختصار إنجليزي (Large Language Model)"),
       ("عميل ذكي", "وكيل ذكي", "يحتاج تدقيقًا", REV, REV_BG, "كلمة عامة لها مصطلح تخصصي في هذا السياق"),
       ("لتحليل البيانات", "—", "معتمد", STD, STD_BG, "مصطلح معتمد أصلًا، لا يُقترح له شيء")]
for i, (a, b, st, col, fill, why) in enumerate(res):
    y = 4.0 + i * 0.62
    box(s, 4.9, y, 7.83, 0.52, fill=SURF, line=LINE, lw=0.6)
    text(s, 10.6, y, 1.95, 0.52, a, size=14, font=SEMI, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 8.75, y, 1.85, 0.52, b, size=14, font=SEMI, color=col, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 5.05, y, 3.65, 0.52, why, size=11, color=MUTED, anchor=MSO_ANCHOR.MIDDLE)
# side card: what the user sees for the review item
box(s, 0.6, 1.65, 4.0, 4.85, fill=SURF, line=REV, lw=1.2)
text(s, 0.8, 1.8, 3.6, 0.35, "بطاقة الاقتراح في الواجهة", size=11, color=MUTED, font=SEMI)
text(s, 0.8, 2.15, 3.6, 0.5, [[("عميل ذكي ", {"bold": True}), ("←", {"color": MUTED}), (" وكيل ذكي", {"bold": True, "color": GREEN})]], size=20, font=SEMI)
pill(s, 0.8, 2.75, 1.45, "يحتاج تدقيقًا", REV_BG, REV, size=10.5)
text(s, 0.8, 3.15, 3.6, 2.2, [
    [("المعجم: ", {"bold": True}), ("معجم البيانات والذكاء الاصطناعي", {})],
    [("بالإنجليزية: ", {"bold": True}), ("Intelligent Agent (IA)", {})],
    [("التعريف: ", {"bold": True}), ("كيان ذاتي التحكم يدرك بيئته ويقوم بأفعال لتحقيق أهداف محددة.", {})],
    [("السبب: ", {"bold": True, "color": REV}), ("كلمة عامة لها مصطلح تخصصي في هذا السياق", {"color": REV})]], size=12, spacing=1.25, space_after=6)
for i, lab in enumerate(["وكيل ذكي", "الكلمة الأصلية"]):
    box(s, 0.8 + (1 - i) * 1.85, 5.75, 1.7, 0.45, fill=GREEN if i == 0 else SURF, line=None if i == 0 else LINE, radius=0.1)
    text(s, 0.8 + (1 - i) * 1.85, 5.75, 1.7, 0.45, lab, size=12, color="ffffff" if i == 0 else INK, font=SEMI, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

# ───────────────────────── 7. Precision rules
s = frame("قواعد الدقة: ما الذي يمنع الكاشف من الخطأ؟", "منطق القرار", 7, "كل قاعدة أُضيفت بعد خطأ حقيقي رُصد في مقالات أو تغريدات، ولم تُعتمد إلا إذا لم تسُؤ الاختبارات")
rules = [("بوابة السياق", "الكلمة اليومية لا تُقترح إلا إذا مال النص إلى المجال وقرب المعنى من الكلمات حولها", "«مقدم الطلب» لا تصبح «مذيع»"),
         ("الكلمة الشائعة جدًّا", "الكلمة المفردة الشائعة في المقالات العامة لا تُقترح", "معالجة، الضغط"),
         ("الصيغ العربية للتدقيق", "المرادف والإملاء الآخر يُعرضان للتدقيق لا للاستبدال", "سهم ممتاز = اختيار جيد"),
         ("الاختصار بين قوسين", "يُحذف إذا كان اختصارًا لاسم مكتوب قبله", "بورصة الدار البيضاء (CSE)"),
         ("أسماء الأعلام اللاتينية", "كلمة لاتينية مجاورة لكلمة لاتينية بحرف كبير", "Maroc Telecom"),
         ("الكاتب يستعمل المصطلح", "لا يُقترح «وكيل» لـ«العميل» في نص يكرر «الوكيل» للمعنى الآخر", "سيطرح الوكيل أسئلة على العميل")]
cw2, ch2 = (W - 1.2 - 0.3) / 2, 1.33
for i, (t, d, ex) in enumerate(rules):
    col, row = i % 2, i // 2
    x = W - 0.6 - (col + 1) * cw2 - col * 0.3
    y = 1.95 + row * (ch2 + 0.2)
    box(s, x, y, cw2, ch2, fill=SURF, line=LINE)
    box(s, x + cw2 - 0.08, y, 0.08, ch2, fill=GREEN, line=None, radius=0, shape=MSO_SHAPE.RECTANGLE)
    text(s, x + 2.35, y + 0.15, cw2 - 2.6, 0.4, t, size=15.5, font=BOLD, bold=True)
    text(s, x + 2.35, y + 0.55, cw2 - 2.6, 0.75, d, size=12, color=MUTED, spacing=1.2)
    box(s, x + 0.18, y + 0.3, 2.0, ch2 - 0.6, fill=RED_BG, line=None, radius=0.08)
    text(s, x + 0.25, y + 0.3, 1.86, ch2 - 0.6, [[("يمنع: ", {"bold": True, "color": RED, "size": 10}), (ex, {"size": 11})]],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, spacing=1.15)

# ───────────────────────── 8. Technologies
s = frame("التقنيات: ما يعمل فعلًا، وما جُرِّب، وما هو مخطط", "التقنيات", 8)
cols = [("مستخدم فعليًّا", GREEN, MINT, [
            ("التشغيل", ["الكاشف بـ JavaScript داخل المتصفح", "محرك Python مطابق + FastAPI", "فهارس JSON ومتجهات embeddinggemma محسوبة مسبقًا", "حاوية Podman على خادم الأكاديمية (معالج فقط)"]),
            ("البناء", ["Qwen3.5-4B لتوليد الصيغ", "Gemma 3 12B عبر Ollama (RTX 3080)", "Claude: المراجعة والبرمجة والاختبار", "ويكي بيانات، ويكيبيديا، 20 GB تغريدات"])]),
        ("تجريبي: جُرِّب ولم يُعتمد", RED, RED_BG, [
            ("حكم السياق", ["Clef-Flash: دقة 59.7%", "Gemma 3 12B حكمًا: دقة 61.5%", "Jev: نموذج مغلق، لا مفتاح، لم يُجرَّب"]),
            ("التضمين والتصنيف", ["bge-m3 · e5-large · Qwen3-Embedding · embeddinggemma: AUC من 0.55 إلى 0.67", "مصنّف على سمات الكاشف: AUC بين 0.46 و0.48 خارج نوع النص"])]),
        ("مخطط له", STD, STD_BG, [
            ("قريبًا", ["نموذج الشركة لضبط الإفراد والجمع والتذكير والتأنيث بعد إدراج المصطلح", "فحص 1,041 رابطًا يوميًّا بجمل حقيقية (جارٍ)"]),
            ("لاحقًا", ["إثراء «وكيل» و67 مصطلحًا بلا اسم إنجليزي", "حكم سياق خفيف يعمل على المعالج (بحث)"])])]
cw3 = (W - 1.2 - 0.5) / 3
for i, (title, col, fill, groups) in enumerate(cols):
    x = W - 0.6 - (i + 1) * cw3 - i * 0.25
    box(s, x, 1.6, cw3, 4.95, fill=SURF, line=LINE)
    box(s, x, 1.6, cw3, 0.55, fill=fill, line=None, radius=0.08)
    text(s, x + 0.2, 1.6, cw3 - 0.4, 0.55, title, size=16, font=BOLD, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    y = 2.35
    for g, items in groups:
        text(s, x + 0.2, y, cw3 - 0.4, 0.3, g, size=12, color=MUTED, font=SEMI)
        y += 0.33
        tb = bullets(s, x + 0.2, y, cw3 - 0.4, 0.42 * len(items) + 0.3, items, size=12.5, gap=4, mark_color=col)
        y += 0.47 * len(items) + (0.12 if i == 1 and g == "التضمين والتصنيف" else 0) + 0.18

# ───────────────────────── 9. Evaluation method
s = frame("كيف قِسنا: أربع مجموعات اختبار وقاعدة قبول صارمة", "منهجية التقييم", 9)
tiles = [("212", "جملة في 6 ملفات اختبار", "ضبط، اختبار مستقل، غموض، كلمات عربية"),
         ("31", "مقطعًا من مقالات منشورة", "3 دفعات؛ الأخيرة حُكم عليها قبل أي تعديل"),
         ("310", "تغريدات حقيقية", "صيغة مضافة واحدة في كل تغريدة"),
         ("368", "اقتراحًا محكومًا عليه", "مجمّعة من كل المجموعات لتحليل الأخطاء")]
tw = (W - 1.2 - 3 * 0.25) / 4
for i, (n_, a, b) in enumerate(tiles):
    x = W - 0.6 - (i + 1) * tw - i * 0.25
    box(s, x, 1.65, tw, 2.0, fill=SURF, line=LINE)
    text(s, x + 0.2, 1.8, tw - 0.4, 0.7, n_, size=34, font=BOLD, bold=True, color=GREEN)
    text(s, x + 0.2, 2.5, tw - 0.4, 0.4, a, size=14, font=SEMI)
    text(s, x + 0.2, 2.9, tw - 0.4, 0.7, b, size=11.5, color=MUTED, spacing=1.2)
box(s, 6.85, 3.95, 5.88, 2.55, fill=MINT, line=None)
text(s, 7.1, 4.1, 5.4, 0.4, "قاعدة القبول", size=16, font=BOLD, bold=True, color=GREEN)
bullets(s, 7.1, 4.6, 5.4, 1.9, ["لا يُعتمد أي تعديل إذا ساءت نتيجة أي ملف من الملفات الستة",
                                 "تطابق المحرك والصفحة: 212 من 212 جملة، و38 اختبارًا برمجيًّا ناجحًا",
                                 "كل قرار مسجّل في reports/pc_decisions.md"], size=13, gap=6)
box(s, 0.6, 3.95, 6.0, 2.55, fill=SURF, line=LINE)
text(s, 0.85, 4.1, 5.5, 0.4, "المقاييس", size=16, font=BOLD, bold=True)
bullets(s, 0.85, 4.6, 5.5, 1.9, [[("الدقة: ", {"bold": True}), ("من الاقتراحات المعروضة، كم منها صحيح؟", {})],
                                 [("الاستدعاء: ", {"bold": True}), ("من الكلمات المطلوب استبدالها، كم اكتُشف؟", {})],
                                 [("الدقة لكل طبقة: ", {"bold": True}), ("«مقترح» و«يحتاج تدقيقًا» كلٌّ على حدة", {})]], size=13, gap=6)

# ───────────────────────── 10. Results by tier
s = frame("النتيجة: الاستبدالات المؤكدة موثوقة، والكلمات اليومية هي الفجوة", "النتائج (1)", 10)
cd = CategoryChartData()
cd.categories = ["ملفات الاختبار", "مقالات جديدة", "تغريدات"]
cd.add_series("مقترح", (90.9, 100.0, 50.0))
cd.add_series("يحتاج تدقيقًا", (77.7, 74.0, 60.9))
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(4.55), Inches(1.6), Inches(8.18), Inches(4.9), cd)
ch = gf.chart
style_chart(ch, 12)
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(12)
pl = ch.plots[0]
pl.gap_width = 70
pl.overlap = -8
for ser, col in zip(pl.series, (REP, "c9922e")):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = rgb(col)
pl.has_data_labels = True
pl.data_labels.number_format = '0.0"%"'
pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(12)
pl.data_labels.font.bold = True
va = ch.value_axis
va.maximum_scale, va.minimum_scale, va.major_unit = 100, 0, 25
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = rgb(LINE)
va.format.line.fill.background()
va.tick_labels.number_format = '0"%"'
va.tick_labels.number_format_is_linked = False
ch.category_axis.reverse_order = True
ch.category_axis.tick_labels.font.size = Pt(13)
text(s, 0.6, 1.7, 3.7, 0.4, "كيف تُقرأ", size=16, font=BOLD, bold=True)
bullets(s, 0.6, 2.2, 3.7, 3.0, [
    [("مقترح ", {"bold": True, "color": REP}), ("= ما يطبّقه «تطبيق الكل»: 50 من 55 في ملفات الاختبار، و15 من 15 في دفعتين جديدتين.", {})],
    [("يحتاج تدقيقًا ", {"bold": True, "color": REV}), ("= كلمات عربية يقرر فيها المستخدم: 74% في المقالات الجديدة (37 من 50).", {})],
    [("التغريدات ", {"bold": True}), ("اختبار قاسٍ عمدًا: جمل قصيرة بلا سياق، و10 اقتراحات «مقترحة» فقط.", {})]], size=12.5, gap=8)
box(s, 0.6, 5.55, 3.7, 0.95, fill=REV_BG, line=None)
text(s, 0.75, 5.6, 3.4, 0.85, "الأحكام من Claude، ومراجعة مستقلة لعينة من 50 حكمًا جارية.", size=11.5, color=REV, anchor=MSO_ANCHOR.MIDDLE, spacing=1.2)

# ───────────────────────── 11. Gold sets
s = frame("ملفات الاختبار الستة: الاستدعاء والدقة اليوم", "النتائج (2)", 11)
sets = [("ضبط", 93.8, 90.0), ("اختبار مستقل 1", 90.5, 90.5), ("اختبار مستقل 2", 94.7, 100.0), ("الغموض", 78.6, 78.6),
        ("كلمات عربية: ضبط", 67.7, 75.0), ("كلمات عربية: مستقل", 66.7, 72.7)]
cd = CategoryChartData()
cd.categories = [a for a, _, _ in sets]
cd.add_series("الاستدعاء", [b for _, b, _ in sets])
cd.add_series("الدقة", [c for _, _, c in sets])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.55), Inches(8.4), Inches(4.95), cd)
ch = gf.chart
style_chart(ch, 11)
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
pl = ch.plots[0]
pl.gap_width = 60
pl.overlap = -5
for ser, col in zip(pl.series, (STD, GREEN2)):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = rgb(col)
pl.has_data_labels = True
pl.data_labels.number_format = '0.0'
pl.data_labels.number_format_is_linked = False
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
pl.data_labels.font.size = Pt(10)
va = ch.value_axis
va.maximum_scale, va.minimum_scale, va.major_unit = 100, 0, 25
va.major_gridlines.format.line.color.rgb = rgb(LINE)
va.format.line.fill.background()
va.tick_labels.number_format = '0"%"'
va.tick_labels.number_format_is_linked = False
ch.category_axis.reverse_order = True
ch.category_axis.tick_labels.font.size = Pt(11)
box(s, 9.3, 1.65, 3.43, 4.85, fill=SURF, line=LINE)
text(s, 9.5, 1.8, 3.05, 0.4, "ما وراء الأرقام", size=16, font=BOLD, bold=True)
bullets(s, 9.5, 2.3, 3.05, 4.1, [
    "الإنجليزية والتعريب: استدعاء ودقة حول 90% فأعلى",
    "الكلمات العربية اليومية: استدعاء نحو 67%، والسبب أن بوابة السياق متحفظة عمدًا",
    "أُضيف إلى الملفات حقل also بـ 19 إجابة صحيحة لم تكن مسجلة، دون تغيير الإجابات الأصلية (reports/gold_also.md)"],
    size=12, gap=8)

# ───────────────────────── 12. Experiments
s = frame("ما جرّبناه لفهم السياق ولم يبلغ المستوى المطلوب", "التجارب", 12, "الهدف دقة 90% في قائمة التدقيق؛ قسنا كل طريقة على الحالات نفسها قبل أي قرار")
cd = CategoryChartData()
cd.categories = ["Gemma 3 12B حكمًا", "Clef-Flash حكمًا"]
cd.add_series("الدقة على 600 حالة قرار", (61.5, 59.7))
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(6.9), Inches(2.25), Inches(5.83), Inches(1.9), cd)
ch = gf.chart
style_chart(ch, 12)
ch.has_legend = False
pl = ch.plots[0]
pl.gap_width = 55
pl.series[0].format.fill.solid()
pl.series[0].format.fill.fore_color.rgb = rgb(RED)
pl.has_data_labels = True
pl.data_labels.number_format = '0.0"%"'
pl.data_labels.number_format_is_linked = False
pl.data_labels.font.size = Pt(12)
pl.data_labels.font.bold = True
va = ch.value_axis
va.maximum_scale, va.minimum_scale = 100, 0
va.visible = False
va.has_major_gridlines = False
va.reverse_order = True
ch.category_axis.format.line.fill.background()
text(s, 6.9, 1.85, 5.83, 0.35, "نموذج لغوي يحكم: هل الكلمة بمعنى المصطلح هنا؟", size=14, font=BOLD, bold=True)
# target line note
text(s, 6.9, 4.15, 5.83, 0.3, "المطلوب: 90%", size=11, color=MUTED)
exps = [("مقارنة الجملة بتعريف المصطلح", "4 نماذج تضمين", "0.55 إلى 0.67", "AUC؛ و0.5 تعني الصدفة"),
        ("مصنّف متعلم على سمات الكاشف", "انحدار لوجستي وتعزيز تدرجي", "0.46 إلى 0.48", "AUC على نوع نص لم يتدرب عليه"),
        ("قبول العبارات دون فحص السياق", "اختبار التغريدات", "76.5%", "استدعاء، لكن الإنذارات الكاذبة 68%")]
for i, (t, how, num, note) in enumerate(exps):
    y = 1.9 + i * 1.5
    box(s, 0.6, y, 5.95, 1.3, fill=SURF, line=LINE)
    text(s, 2.75, y + 0.15, 3.6, 0.4, t, size=14.5, font=BOLD, bold=True)
    text(s, 2.75, y + 0.6, 3.6, 0.6, how, size=12, color=MUTED)
    text(s, 0.75, y + 0.12, 1.95, 0.5, num, size=16, font=BOLD, bold=True, color=RED, align=PP_ALIGN.CENTER)
    text(s, 0.75, y + 0.62, 1.95, 0.6, note, size=10.5, color=MUTED, align=PP_ALIGN.CENTER, spacing=1.1)
box(s, 6.9, 4.65, 5.83, 1.85, fill=MINT, line=None)
text(s, 7.15, 4.78, 5.35, 0.4, "الخلاصة", size=16, font=BOLD, bold=True, color=GREEN)
text(s, 7.15, 5.2, 5.35, 1.25, "الإشارات الثابتة (متجهات الكلمات، ميل المجال) لا تفصل المعنى في الكلمات اليومية، والنماذج المحلية الصغيرة لم تكفِ. لذلك صار التصميم صريحًا: ما لا نثق به يُعرض للتدقيق بسببه، ولا يُطبَّق آليًّا.",
     size=12.5, spacing=1.3)

# ───────────────────────── 13. Challenges and limits
s = frame("التحديات وحدود التقييم", "بصراحة", 13)
for i, (title, col, fill, items) in enumerate([
        ("التحديات التقنية", GREEN, MINT, [
            "غموض العربية دون تشكيل: «عميل» وكيل أو زبون، «بورصة» سوق أو صرف",
            "في المعاجم كلمات عامة مسجلة مصطلحات (انتهاء ← انقضاء)",
            "الأسماء والاختصارات تشبه المصطلحات (CSE، Telecom)",
            "إدراج المصطلح يكسر المطابقة: «المودلز الكبيرة» ← «النموذج الكبيرة»",
            "خادم الإطلاق بلا كرت شاشة: لا نموذج لغوي وقت التحليل"]),
        ("حدود التقييم", REV, REV_BG, [
            "الأحكام من Claude؛ مراجعة بشرية مستقلة لـ 50 حكمًا جارية",
            "بعض ملفات الاختبار كتبها فريق المشروع، وليست نصوصًا منشورة",
            "بعض القواعد صُمّمت بعد قراءة دفعات المقالات التي قيست عليها؛ الأرقام النزيهة: دفعة حُكم عليها قبل أي تعديل (مقترح 8 من 8، تدقيق 62%)",
            "عينات «مقترح» في المقالات صغيرة (15 اقتراحًا)",
            "التغريدات اختبار قاسٍ متعمد، لا يمثل الاستعمال المتوقع"])]):
    x = W - 0.6 - (i + 1) * 5.95 - i * 0.23
    box(s, x, 1.6, 5.95, 4.9, fill=SURF, line=LINE)
    box(s, x, 1.6, 5.95, 0.6, fill=fill, line=None, radius=0.08)
    text(s, x + 0.25, 1.6, 5.45, 0.6, title, size=17, font=BOLD, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, x + 0.25, 2.45, 5.45, 4.0, items, size=14.5, gap=14, mark_color=col)

# ───────────────────────── 14. Company model
s = frame("نموذج الشركة: يضبط صيغة الكلمة بعد إدراج المصطلح، لا أكثر", "الخطة القادمة (1)", 14)
stages = [("ما كتبه المستخدم", "درّبنا المودلز الكبيرة على الداتا الجديدة", SURF, LINE, INK),
          ("بعد إدراج مصطلحات سوار", "درّبنا النموذج الكبيرة على البيانات الجديدة", REV_BG, REV, INK),
          ("بعد نموذج الشركة", "درّبنا النماذج الكبيرة على البيانات الجديدة", REP_BG, REP, INK)]
for i, (lab, sent, fill, line, col) in enumerate(stages):
    y = 1.65 + i * 1.12
    box(s, 4.3, y, 8.43, 0.88, fill=fill, line=line, lw=1.0)
    text(s, 10.4, y, 2.15, 0.88, lab, size=12, color=MUTED, font=SEMI, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 4.5, y, 5.85, 0.88, sent, size=19, font=SEMI, anchor=MSO_ANCHOR.MIDDLE)
    if i < 2:
        arrow(s, 8.5, y + 0.9, 8.5, y + 1.1, color=GREEN, w=2)
text(s, 4.5, 4.98, 8.2, 0.4, "الكاشف نفسه ينبّه اليوم: «وردت بصيغة الجمع، فراجع صيغة المصطلح بعد الاستبدال»؛ هذا ما يحلّه النموذج.", size=11.5, color=MUTED)
box(s, 0.6, 1.65, 3.45, 2.3, fill=MINT, line=None)
text(s, 0.8, 1.75, 3.1, 0.4, "يفعل", size=16, font=BOLD, bold=True, color=GREEN)
bullets(s, 0.8, 2.25, 3.1, 1.7, ["يضبط الإفراد والجمع", "يضبط التذكير والتأنيث", "في الكلمة المستبدلة وما يطابقها فقط"], size=14, gap=8, mark="✓")
box(s, 0.6, 4.15, 3.45, 2.35, fill=RED_BG, line=None)
text(s, 0.8, 4.25, 3.1, 0.4, "لا يفعل", size=16, font=BOLD, bold=True, color=RED)
bullets(s, 0.8, 4.75, 3.1, 1.8, ["لا يختار المصطلح", "لا يعيد صياغة النص", "لا يعمل قبل قرار المستخدم"], size=14, gap=8, mark="✗", mark_color=RED)
box(s, 4.3, 5.5, 8.43, 1.0, fill=SURF, line=STD, dash=True, lw=1.2)
text(s, 4.5, 5.5, 8.05, 1.0, [[("موقعه في البنية: ", {"bold": True, "color": STD}), ("بعد قرار المستخدم وقبل النص النهائي. المصطلح يبقى من سوار دائمًا، والنموذج لا يرى إلا الجملة والمصطلح الذي اختاره المستخدم.", {})]],
     size=13, anchor=MSO_ANCHOR.MIDDLE, spacing=1.25)

# ───────────────────────── 15. Roadmap
s = frame("الخطة القادمة", "الخطة القادمة (2)", 15)
phases = [("الآن", "جارٍ", GREEN, ["فحص 1,041 رابطًا يوميًّا بجمل حقيقية من ويكيبيديا، وسحب الخاطئ بعد المراجعة", "مراجعة بشرية مستقلة لـ 50 حكمًا"]),
          ("قبل الإطلاق", "قريب", GREEN2, ["نشر النسخة الأخيرة على kass.arai.center", "دمج فرع enrichment-pass1 في main"]),
          ("التالي", "مخطط", STD, ["ربط نموذج الشركة لضبط الإفراد والجمع والتذكير والتأنيث", "قياسه على جمل حقيقية قبل اعتماده"]),
          ("لاحقًا", "بحث", "6b5a2e", ["إثراء «وكيل» و67 مصطلحًا بلا اسم إنجليزي", "حكم سياق خفيف يعمل على المعالج لرفع قائمة التدقيق نحو 90%"])]
pw2 = (W - 1.2 - 3 * 0.22) / 4
yline = 2.35
s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.9), Inches(yline), Inches(W - 0.9), Inches(yline)).line.color.rgb = rgb(MINT2)
for i, (t, tag, col, items) in enumerate(phases):
    x = W - 0.6 - (i + 1) * pw2 - i * 0.22
    box(s, x + pw2 / 2 - 0.16, yline - 0.16, 0.32, 0.32, fill=col, line=None, radius=0.16, shape=MSO_SHAPE.OVAL)
    text(s, x, 1.6, pw2, 0.45, t, size=19, font=BOLD, bold=True, color=col, align=PP_ALIGN.CENTER)
    box(s, x, 2.75, pw2, 2.75, fill=SURF, line=LINE)
    pill(s, x + pw2 - 1.1, 2.92, 0.9, tag, MINT if i < 2 else (STD_BG if i == 2 else "f3ecdc"), col, size=10.5)
    bullets(s, x + 0.2, 3.4, pw2 - 0.4, 2.1, items, size=13.5, gap=10, mark_color=col)
box(s, 0.6, 5.8, W - 1.2, 0.7, fill=GREEN, line=None, radius=0.1)
text(s, 0.85, 5.84, W - 1.7, 0.62, "الطبقة تعرف ما يجب أن يُكتب (المصطلح المعتمد)، والمستخدم يقرر، ونموذج الشركة يضبط الصيغة.",
     size=15, color="ffffff", font=SEMI, anchor=MSO_ANCHOR.MIDDLE)

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
