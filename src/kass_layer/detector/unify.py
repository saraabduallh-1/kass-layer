"""Term consistency within one text: the same concept written in different forms (المودل، الموديل، نموذج; داشبورد، Dashboard).

Two layers, as terminology QA tools do (glossary first, spelling variants second, never meaning-closeness alone):
1. Dictionary groups: every form the detector links to the same SIWAR term. The term is the form to keep.
2. Spelling groups: borrowed words outside the dictionaries that are spellings of one word (الداتا، داتا، ديتا;
   داشبورد، dashboard). The most frequent form is kept; these are always marked for review.
معجم الرياض (general Arabic, demo_local/riyadh.json) adds three things: a dictionary group also takes the synonyms the
Riyadh dictionary translates the same way (الحاسب الآلي: حاسوب، كمبيوتر), and in tech عميل / وكيل (DOMAIN_SYN); a feminine form with its own meaning is another
word (حاسب / حاسبة); and a place name it spells with «يا» groups its «ية» spelling (سوريا / سورية).
Word vectors are not used to merge words: they put related words and opposites close (البائع / المشتري), so a merge
on closeness alone would join different concepts.
"""
import re

from .engine import ARABIC_WORD, Detector, ar_skel, bare, ctx_words, en_skels, is_latin, normalize, sim, tokenize, vowels

_ARTICLE = re.compile("^(?:[وفبك]?ال|و?لل)(?=.{3,})")  # والمودل، بالنموذج، للنموذج
_AND = re.compile("^و(?=.{4,})")  # ولوحة (not لوحة → وحة)
_PLURAL = re.compile("(ات|ين|ون|ز|س)$")
COMMON_RATE = 2e-5  # a word this frequent in general Arabic articles is ordinary Arabic (كاليفورنيا، فيديو), not a spelling to unify


def term_key(term: str) -> str:
    """One key per term, whatever its article: «الشبكة العصبية» and «شبكة عصبية» are one term."""
    return " ".join(bare(w) for w in normalize(re.sub(r"\([^)]*\)", " ", term)).split())


def form_key(form: str) -> str:
    """One key per written form, without و/ب/ل/ال, so «والمودل» and «المودل» are one form, not two."""
    return " ".join(_strip(w) for w in normalize(form).split())


def _strip(w: str) -> str:
    x = _ARTICLE.sub("", w)
    return x if x != w else _AND.sub("", w)


def _lexeme(word: str) -> str:
    """The word without particle, article, pronoun and plural/feminine ending: للنظام → نظام, تدريبها → تدريب, LLMs → llm."""
    w = _strip(normalize(word))
    if is_latin(w):
        return re.sub("(es|s)$", "", w) if len(w) > 3 else w
    w = re.sub("(هما|ها|هم|هن|كم|نا|ه|ك)$", "", w) if len(w) >= 5 else w
    return re.sub("(ات|ان|ين|ون|يه|ي|و|ا)$", "", w) if len(w) > 4 else w


def _singular_f(w: str) -> str:
    """The ة form a word is written from: حاسبه → حاسبه, حاسبات → حاسبه, حاسب → حاسب."""
    return w[:-2] + "ه" if w.endswith("ات") and len(w) > 4 else w


def _own_word(a: str, b: str, own) -> bool:
    """«حاسبة» is its own word (calculator), not «حاسب» + ة: معجم الرياض translates the two differently."""
    if not own:
        return False
    p, q = _singular_f(bare(_strip(a))), _singular_f(bare(_strip(b)))
    return (p in own and q == p[:-1]) or (q in own and p == q[:-1])


def same_word(a: str, b: str, own=frozenset()) -> bool:
    """Two forms of one word or phrase, only inflected differently (الاستثمار / الاستثمارات, سيارة ذاتية / السيارات الذاتية).
    own: the Riyadh feminine forms with their own meaning (حاسبة), which are not forms of the masculine (حاسب)."""
    na, nb = normalize(a).split(), normalize(b).split()
    x, y = [_lexeme(w) for w in na], [_lexeme(w) for w in nb]
    if len(x) == len(y):
        return all(_same_lex(p, q) and not _own_word(u, v, own) for p, q, u, v in zip(x, y, na, nb))
    if len(x) > len(y):
        x, y = y, x
    # a shortened mention is the same name (للفيدرالي / الاحتياطي الفيدرالي); السوفتوير / السوفت وير is two spellings
    return any(x == y[i:i + len(x)] or all(_same_lex(p, q) and len(p) == len(q) for p, q in zip(x, y[i:i + len(x)]))
               for i in range(len(y) - len(x) + 1))


_FUALAA = re.compile("^(.)(.)(.)ا[ءئؤ]$")  # the broken plural فُعَلاء of فَعِيل: عملاء / عميل، وكلاء / وكيل، وزراء / وزير


def _same_lex(p: str, q: str) -> bool:
    if p == q or (min(len(p), len(q)) >= 4 and (p.startswith(q) or q.startswith(p))):
        return True
    for u, v in ((p, q), (q, p)):
        m = _FUALAA.match(u)
        if m and v == m.group(1) + m.group(2) + "ي" + m.group(3):
            return True
    # a one-letter particle: لصاحب / صاحب, بتقديم / تقديم
    return any(u[0] in "وفبلك" and len(u) >= (3 if u[0] == "و" else 4) and u[1:] == v for u, v in ((p, q), (q, p)))


def _distinct(forms: list[str], own=frozenset()) -> int:
    """How many different words the forms are, inflection aside."""
    heads: list[str] = []
    for f in forms:
        if not any(same_word(f, h, own) for h in heads):
            heads.append(f)
    return len(heads)


def _glossed(text: str, s: int, e: int) -> bool:
    """A form that glosses or quotes, not a second name: «الذكاء الاصطناعي (AI)», «(بالإنجليزية: Cloud computing)», and an
    English word inside an English phrase (software as a service, Azure AI)."""
    before, after = text[max(0, s - 60):s], text[e:e + 60]
    if "(" in before and ")" not in before[before.rfind("("):] and ")" in after and "(" not in after[:after.find(")")]:
        return True
    if re.search("[A-Za-z]", text[s:e]):
        return bool(re.search(r"[A-Za-z]+[\s\-]*$", before) or re.search(r"^[\s\-]*[A-Za-z]+", after))
    return False


def _spelling_key(word: str) -> str:
    """The sound skeleton of a borrowed word: داشبورد and dashboard both give «dsbrd»."""
    if is_latin(word):
        return en_skels(word)[0]
    w = _strip(word)
    return ar_skel(_PLURAL.sub("", w) if len(w) > 5 else w)


def _riyadh_keys(word: str) -> set[str]:
    """The keys a written word may have in معجم الرياض: والحاسوب → حاسوب, حاسوبا → حاسوب, الوكلاء → وكيل."""
    w = normalize(word)
    if " " in w:
        return set()
    keys = {bare(_strip(w)), _lexeme(w), bare(w)}  # bare(w): a word that starts with و itself (وكيلا, not «و» + كيلا)
    if w.endswith("ا") and len(w) > 4:
        keys.add(bare(w[:-1]))
    m = _FUALAA.match(_lexeme(w))
    return keys | {m.group(1) + m.group(2) + "ي" + m.group(3)} if m else keys


# Synonyms one domain uses that the dictionaries do not link: in tech «عميل ذكي» is written for an intelligent agent
# (وكيل ذكي). Elsewhere عميل is a client and وكيل an agent, two concepts; and next to a server it is a client in tech too.
DOMAIN_SYN = {"tech": {"عميل": ["وكيل"], "وكيل": ["عميل"]}}
_CLIENT_SERVER = re.compile("خادم|خوادم|سيرفر|server")


def _place(w: str, places) -> str | None:
    """The Riyadh place name a written word is: سوريا، وسوريا، بسورية، لسوريه → سوريا; not السورية (the adjective)."""
    if w.startswith("ال"):
        return None
    for x in (w, w[1:]) if w[:1] in "وبل" and len(w) > 4 else (w,):
        if x in places:
            return x
        if x.endswith("يه") and x[:-2] + "يا" in places:
            return x[:-2] + "يا"
    return None


def unify(det: Detector, text: str, domain_id: str = "tech", analysis: dict | None = None) -> dict:
    res = analysis or det.analyse(text, domain_id)
    groups = []
    riyadh = getattr(det, "riyadh", None) or {"syn": {}, "own": frozenset(), "place": frozenset(), "name": ""}
    own, syn = riyadh["own"], riyadh["syn"]
    dsyn = {} if _CLIENT_SERVER.search(normalize(text)) else DOMAIN_SYN.get(domain_id, {})

    def near_of(word: str) -> set[str]:
        out = {s for k in _riyadh_keys(word) for s in syn.get(k, [])}
        return out | {s for w in normalize(word).split() for k in _riyadh_keys(w) for s in dsyn.get(k, [])}

    # 1. forms the dictionaries link to one term
    tokens = tokenize(text)
    std_keys = {term_key(det.senses[it["best"][0]][0]) for it in res["items"] if it["state"] == "std"}
    by_term: dict[str, dict] = {}
    for it in res["items"]:
        # a form with several terms takes the one the writer also uses (الإنفرتر → عاكس التيار, when «عاكس التيار» is there)
        best = next((r for r in it["choices"] if term_key(det.senses[r[0]][0]) in std_keys), it["best"])
        sense = det.senses[best[0]]
        g = by_term.setdefault(term_key(sense[0]), {"term": sense[0], "dictionary": det.dictionaries[sense[1]], "uses": []})
        if _glossed(text, it["m"]["s"], it["m"]["e"]):
            continue
        if it["state"] == "std" and it["m"]["n"] == 1 and not same_word(it["original"], sense[0], own):
            continue  # a one-word "standard" match that is another word (عملية / العملة, الدور / الدوري)
        if any(_own_word(w, v, own) for w in normalize(it["original"]).split() for v in term_key(sense[0]).split()):
            continue  # a feminine with its own meaning is another word (الحاسبة is not «الحاسب الآلي»)
        g["uses"].append({"text": it["original"], "start": it["m"]["s"], "end": it["m"]["e"], "state": it["state"]})
    for g in by_term.values():
        n = len(term_key(g["term"]).split())
        taken = [(u["start"], u["end"]) for gg in by_term.values() for u in gg["uses"]]
        for i in range(len(tokens) - n + 1):  # the term itself, written anywhere (خادم، العقد), even where nothing was proposed
            s0, e0 = tokens[i]["s"], tokens[i + n - 1]["e"]
            window = text[s0:e0]
            if any(s0 < e and e0 > s for s, e in taken) or not same_word(window, re.sub(r"\([^)]*\)", " ", g["term"]), own):
                continue
            g["uses"].append({"text": window, "start": s0, "end": e0, "state": "std"})
            taken.append((s0, e0))
        # the Riyadh synonyms of the forms used (الحاسب → حاسوب، كمبيوتر), written anywhere; marked for review
        if (syn or dsyn) and g["uses"]:
            near = {s for u in g["uses"] for s in near_of(u["text"])}
            added = True
            while added:
                added = False
                for t in tokens:
                    if any(t["s"] < e and t["e"] > s for s, e in taken) or not _riyadh_keys(t["n"]) & near:
                        continue
                    g["uses"].append({"text": text[t["s"]:t["e"]], "start": t["s"], "end": t["e"], "state": "review"})
                    taken.append((t["s"], t["e"]))
                    near |= near_of(t["n"])
                    added = True
            g["uses"].sort(key=lambda u: u["start"])
        forms: dict[str, dict] = {}
        for u in g["uses"]:
            f = forms.setdefault(form_key(u["text"]), {"form": u["text"], "count": 0, "standard": u["state"] == "std"})
            f["count"] += 1
        if _distinct([f["form"] for f in forms.values()], own) < 2:
            continue  # one word throughout, however inflected: consistent (a lone borrowed form is already a suggestion)
        review = any(u["state"] == "review" for u in g["uses"])
        groups.append({"kind": "dictionary", "keep": g["term"], "dictionary": g["dictionary"], "review": review,
                       "forms": sorted(forms.values(), key=lambda f: -f["count"]), "uses": g["uses"]})

    # 2. spellings of one borrowed word that the dictionaries do not list
    covered = [(it["m"]["s"], it["m"]["e"]) for it in res["items"]]
    by_skel: dict[str, list] = {}
    for t in tokens:
        if any(t["s"] < e and t["e"] > s for s, e in covered):
            continue
        w = t["n"]
        latin = is_latin(w) and len(w) >= 4
        x = bare(_strip(w))
        # not an ordinary Arabic word: rare in general Arabic articles and not in the dictionaries' Arabic (الدرايف، اللابتوب)
        common = det.known_arabic(x) or any(c in det.words and det.word_gen[det.words[c]] / det.gen_total >= COMMON_RATE
                                            for c in ctx_words(w))
        # and spelled like a borrowing, with long vowels (ديتا، سوفتوير), not like an Arabic verb or noun (ناقش، نقاشات)
        borrowed = ARABIC_WORD.search(w) and len(x) >= 4 and not common and vowels(x) >= 2 \
            and (det.looks_borrowed(w) or det.foreign_looking(x, lead=False))
        if not (latin or borrowed):
            continue
        k = _spelling_key(w)
        if len(k) >= 3 and not _glossed(text, t["s"], t["e"]):
            by_skel.setdefault(k, []).append({"text": text[t["s"]:t["e"]], "start": t["s"], "end": t["e"], "state": "review"})
    for k, uses in by_skel.items():
        forms: dict[str, dict] = {}
        for u in uses:
            f = forms.setdefault(form_key(u["text"]), {"form": u["text"], "count": 0, "standard": False})
            f["count"] += 1
        if _distinct([f["form"] for f in forms.values()], own) < 2:
            continue
        # spellings of one word stay close in sound; a shared skeleton between unlike words (كاميرا / كوميري) does not
        keys = list(forms)
        if not all(sim(_spelling_key(a), _spelling_key(b)) >= 0.75 for a in keys for b in keys if a < b):
            continue
        ranked = sorted(forms.values(), key=lambda f: (-f["count"], is_latin(normalize(f["form"]))))
        groups.append({"kind": "spelling", "keep": _strip(ranked[0]["form"]) if not is_latin(normalize(ranked[0]["form"]))
                       else ranked[0]["form"], "dictionary": None, "review": True, "forms": ranked, "uses": uses})

    # 3. a place name معجم الرياض spells with «يا», also written with «ية» (سوريا / سورية); not the adjective after a
    # feminine noun (شركة سورية) and not with the article (السورية)
    if riyadh["place"]:
        taken = [(u["start"], u["end"]) for g in groups for u in g["uses"]] + covered
        places = riyadh["place"]
        by_place: dict[str, list] = {}
        for i, t in enumerate(tokens):
            name = _place(normalize(t["n"]), places)
            if not name or any(t["s"] < e and t["e"] > s for s, e in taken):
                continue
            if not normalize(t["n"]).endswith("يا") and i and normalize(tokens[i - 1]["n"]).endswith("ه"):
                continue
            by_place.setdefault(name, []).append({"text": text[t["s"]:t["e"]], "start": t["s"], "end": t["e"], "state": "review"})
        for name, uses in by_place.items():
            forms: dict[str, dict] = {}
            for u in uses:
                f = forms.setdefault(form_key(u["text"]), {"form": u["text"], "count": 0, "standard": False})
                f["count"] += 1
            if len({normalize(f["form"]).endswith("يا") for f in forms.values()}) < 2:
                continue  # both spellings, «يا» and «ية», are written
            groups.append({"kind": "spelling", "keep": name, "dictionary": riyadh["name"], "review": True,
                           "forms": sorted(forms.values(), key=lambda f: -f["count"]), "uses": uses})

    groups.sort(key=lambda g: min(u["start"] for u in g["uses"]))
    return {"groups": groups}


# ---- the writer's choice (same rules as unifyOptions / formFor / unifyPlan in the page): for each group the forms the
# writer may keep, and for each use the text it takes under each of them. A client shows the options, lets the writer
# pick one and the uses to change (all, or some), and writes use["replacements"][kept] at use["start"]:use["end"].

def options(group: dict) -> list[str]:
    """The suggested form first, then every other form of the group without its article (المودل → مودل)."""
    out, seen = [group["keep"]], {term_key(group["keep"])}
    for f in group["forms"]:
        c = f["form"] if is_latin(normalize(f["form"])) else _strip(f["form"])
        if term_key(c) not in seen:
            seen.add(term_key(c))
            out.append(c)
    return out


def form_for(use: str, keep: str) -> str:
    """The text one use takes when the writer keeps «keep»: its own و/ب/ال stay (بالمودل → بالنموذج)."""
    lead, had_al = "", False
    if not is_latin(normalize(use)):
        m = _ARTICLE.match(use)
        if m:
            lead, had_al = m.group(0), True
        elif a := _AND.match(use):
            lead = a.group(0)
    no_al = re.sub("^(و?)لل$", r"\1ل", re.sub("ال$", "", lead))
    if is_latin(normalize(keep)) or " " in keep:
        return (no_al if had_al else lead) + keep
    return lead + (keep[2:] if keep.startswith("ال") and len(keep) > 4 else keep)


def with_choices(det: Detector, groups: list[dict], analysis: dict) -> list[dict]:
    """Adds group["options"] and use["replacements"] = {option: text}. A use the detector already suggests the term
    for takes the suggestion's own text for that term (pronoun endings carried over), as the page does."""
    from .engine import replacement
    items = {it["m"]["s"]: it for it in analysis["items"] if it["state"] != "std"}
    for g in groups:
        g["options"] = options(g)
        for u in g["uses"]:
            it = items.get(u["start"])
            u["replacements"] = {
                o: replacement(o, it) if it is not None and o == g["keep"] and any(det.senses[r[0]][0] == o for r in it["choices"])
                else form_for(u["text"], o)
                for o in g["options"]}
    return groups
