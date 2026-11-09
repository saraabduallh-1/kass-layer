"""Term consistency within one text: the same concept written in different forms (المودل، الموديل، نموذج; داشبورد، Dashboard).

Two layers, as terminology QA tools do (glossary first, spelling variants second, never meaning-closeness alone):
1. Dictionary groups: every form the detector links to the same SIWAR term. The term is the form to keep.
2. Spelling groups: borrowed words outside the dictionaries that are spellings of one word (الداتا، داتا، ديتا;
   داشبورد، dashboard). The most frequent form is kept; these are always marked for review.
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


def same_word(a: str, b: str) -> bool:
    """Two forms of one word or phrase, only inflected differently (الاستثمار / الاستثمارات, سيارة ذاتية / السيارات الذاتية)."""
    x, y = [_lexeme(w) for w in normalize(a).split()], [_lexeme(w) for w in normalize(b).split()]
    if len(x) == len(y):
        return all(_same_lex(p, q) for p, q in zip(x, y))
    if len(x) > len(y):
        x, y = y, x
    # a shortened mention is the same name (للفيدرالي / الاحتياطي الفيدرالي); السوفتوير / السوفت وير is two spellings
    return any(x == y[i:i + len(x)] or all(_same_lex(p, q) and len(p) == len(q) for p, q in zip(x, y[i:i + len(x)]))
               for i in range(len(y) - len(x) + 1))


def _same_lex(p: str, q: str) -> bool:
    if p == q or (min(len(p), len(q)) >= 4 and (p.startswith(q) or q.startswith(p))):
        return True
    # a one-letter particle: لصاحب / صاحب, بتقديم / تقديم
    return any(u[0] in "وفبلك" and len(u) >= (3 if u[0] == "و" else 4) and u[1:] == v for u, v in ((p, q), (q, p)))


def _distinct(forms: list[str]) -> int:
    """How many different words the forms are, inflection aside."""
    heads: list[str] = []
    for f in forms:
        if not any(same_word(f, h) for h in heads):
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


def unify(det: Detector, text: str, domain_id: str = "tech", analysis: dict | None = None) -> dict:
    res = analysis or det.analyse(text, domain_id)
    groups = []

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
        if it["state"] == "std" and it["m"]["n"] == 1 and not same_word(it["original"], sense[0]):
            continue  # a one-word "standard" match that is another word (عملية / العملة, الدور / الدوري)
        g["uses"].append({"text": it["original"], "start": it["m"]["s"], "end": it["m"]["e"], "state": it["state"]})
    for g in by_term.values():
        n = len(term_key(g["term"]).split())
        taken = [(u["start"], u["end"]) for gg in by_term.values() for u in gg["uses"]]
        for i in range(len(tokens) - n + 1):  # the term itself, written anywhere (خادم، العقد), even where nothing was proposed
            s0, e0 = tokens[i]["s"], tokens[i + n - 1]["e"]
            window = text[s0:e0]
            if any(s0 < e and e0 > s for s, e in taken) or not same_word(window, re.sub(r"\([^)]*\)", " ", g["term"])):
                continue
            g["uses"].append({"text": window, "start": s0, "end": e0, "state": "std"})
            taken.append((s0, e0))
        forms: dict[str, dict] = {}
        for u in g["uses"]:
            f = forms.setdefault(form_key(u["text"]), {"form": u["text"], "count": 0, "standard": u["state"] == "std"})
            f["count"] += 1
        if _distinct([f["form"] for f in forms.values()]) < 2:
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
        if _distinct([f["form"] for f in forms.values()]) < 2:
            continue
        # spellings of one word stay close in sound; a shared skeleton between unlike words (كاميرا / كوميري) does not
        keys = list(forms)
        if not all(sim(_spelling_key(a), _spelling_key(b)) >= 0.75 for a in keys for b in keys if a < b):
            continue
        ranked = sorted(forms.values(), key=lambda f: (-f["count"], is_latin(normalize(f["form"]))))
        groups.append({"kind": "spelling", "keep": _strip(ranked[0]["form"]) if not is_latin(normalize(ranked[0]["form"]))
                       else ranked[0]["form"], "dictionary": None, "review": True, "forms": ranked, "uses": uses})

    groups.sort(key=lambda g: min(u["start"] for u in g["uses"]))
    return {"groups": groups}
