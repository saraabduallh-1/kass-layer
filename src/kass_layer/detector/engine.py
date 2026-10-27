"""Term detector: finds non-standard words in Arabic text and proposes the standard SIWAR term.

A line-by-line port of the engine in scripts/demo/kass-lab.html (keep the two in step;
scripts/demo/tests/parity.py checks they agree). No model runs at query time: it uses the
dictionary index (index.json), per-sense keywords (context.json) and precomputed 128-d
EmbeddingGemma vectors (senses.txt, base64 int8). Build them with scripts/demo/build_*.py.
"""

from __future__ import annotations

import base64
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
import regex

TYPE = {"f": "صيغة إنجليزية", "t": "كتابة صوتية", "a": "اختصار", "i": "مرادف غير رسمي", "c": "عامية", "s": "اختلاف إملائي", "": ""}
PREFIXES = ["وبال", "وال", "بال", "فال", "كال", "ولل", "لل", "ال", "و", "ف", "ب", "ل", "ك"]
DIAC = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ​-‏‪-‮⁦-⁩﻿]")
PUNCT = re.compile("[\"'«»“”‘’()\\[\\]{}.,،؛:!?؟]")
TOKEN = regex.compile(r"[\p{L}\p{N}][\p{L}\p{N}\p{M}_\-']*")
ARABIC_WORD = re.compile("^[؀-ۿ]+$")

DOMAINS = [
    {"id": "legal", "label": "قانوني", "keys": ["القانونية", "العقود"]},
    {"id": "tech", "label": "تقني", "keys": ["البيانات والذكاء", "الحكومة الرقمية"]},
    {"id": "finance", "label": "مالي وإداري", "keys": ["المالية", "العقود", "الإحصائية", "الإدارية", "الموارد البشرية", "قياس أداء", "غير الربحي", "الإنمائية"]},
    {"id": "media", "label": "إعلامي", "keys": ["الإعلام"]},
    {"id": "eng", "label": "هندسي", "keys": ["الطيران", "السيارات", "الطاقة", "الخطوط الحديدية", "الطرق"]},
    {"id": "culture", "label": "علمي وثقافي", "keys": ["علم السلوك", "الحياة الفطرية", "المصطلحات الرياضية", "الموسيقية", "الرياضات الإلكترونية"]},
]


def normalize(t: str | None) -> str:
    t = DIAC.sub("", t or "")
    t = re.sub("[أإآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه").lower()
    return " ".join(PUNCT.sub(" ", t).split())


STOP = {normalize(w) for w in ["آخر", "أن", "أنا", "أنت", "أو", "إذا", "إلى", "إن", "إيه", "ابي", "احنا", "اخر", "اذا", "التي", "الحين", "الذي", "الذين", "اللي", "الى", "الي", "اليوم", "امس", "ان", "انا", "انت", "انتم", "او", "اول", "ايش", "اين", "ايه", "بس", "بعد", "بعض", "بكرة", "بكره", "بل", "بين", "تبي", "تحت", "تكون", "تلك", "ثم", "جدا", "جديد", "حتى", "خاص", "دحين", "ذلك", "زي", "سوى", "سوي", "سوينا", "صار", "صارت", "صغير", "عام", "عشان", "علشان", "على", "علي", "عليه", "عليها", "عن", "عند", "عنده", "عنه", "عنها", "غير", "فوق", "في", "فيه", "فيها", "قبل", "قد", "قليل", "كان", "كانت", "كبير", "كثير", "كذا", "كل", "كيف", "لا", "لدى", "لقد", "لكن", "لم", "لماذا", "لن", "لو", "ليس", "ليست", "ليش", "لين", "ما", "ماذا", "متى", "مثل", "مرة", "مره", "مع", "معه", "معها", "معي", "من", "منا", "منك", "منه", "منها", "منهم", "مني", "نبي", "نحن", "نفس", "هاذا", "هالشي", "هذا", "هذه", "هذي", "هم", "هن", "هنا", "هناك", "هو", "هي", "واجد", "وش", "وين", "يا", "يبي", "بدل", "بدال", "عوض", "تسوي", "نسوي", "يسوي", "اسوي", "سويت", "سوت", "يسوون", "تسوون", "سوو", "يسوي", "يكون"]}


def tokenize(text: str) -> list[dict]:
    return [{"s": m.start(), "e": m.end(), "n": normalize(m.group())} for m in TOKEN.finditer(text)]


# ---- phonetic matching: Arabic-letter spellings of English words already listed in the dictionaries
AR2LAT = {"ب": "b", "پ": "b", "ت": "t", "ث": "t", "ج": "k", "ح": "h", "خ": "k", "د": "d", "ذ": "z", "ر": "r", "ز": "s", "س": "s",
          "ش": "s", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "غ": "k", "ف": "f", "ڤ": "f", "ق": "k", "ك": "k", "گ": "k", "ل": "l", "م": "m",
          "ن": "n", "ه": "h"}  # ز → s: Arabic writes English s/z sounds with either letter (نيوز = news)


def collapse(t: str) -> str:
    return re.sub(r"h$", "", re.sub(r"(.)\1+", r"\1", t))


def ar_skel(w: str) -> str:
    return collapse("".join(AR2LAT.get(c, "") for c in w))


def en_skels(w: str) -> list[str]:
    base = re.sub(r"[^a-z]", "", w.lower())
    for pat, rep in [(r"[ts]ion", "shn"), ("sch", "sk"), ("ph", "f"), ("sh", "s"), ("ck", "k"), ("qu", "k"), ("gh", ""),
                     ("x", "ks"), (r"c(?=[eiy])", "s"), ("q", "k"), ("p", "b"), ("v", "f"), ("[jg]", "k"), ("c", "k")]:
        base = re.sub(pat, rep, base)
    out = [base]
    if "kh" in base:  # "ch" became "kh"
        out = [x for b in out for x in (b.replace("kh", "s"), b.replace("kh", "ts"), b.replace("kh", "k"))]
    if "th" in base:
        out = [x for b in out for x in (b.replace("th", "t"), b.replace("th", "z"), b.replace("th", "s"))]
    return list(dict.fromkeys(collapse(re.sub(r"[aeiouwy]", "", b.replace("z", "s"))) for b in out))


def lev(a: str, b: str) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            t = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = t
    return d[len(b)]


def sim(a: str, b: str) -> float:
    return 1 - lev(a, b) / max(len(a), len(b), 1)


NATIVE = re.compile("[عحصضظذثءؤئة]")


def bare(w: str) -> str:
    return w[2:] if w.startswith("ال") and len(w) > 4 else w


def verb_shape(w: str) -> bool:
    return bool(re.search("^[يتن].{2,}(ون|وا|ين)$", w) or re.search("^.{3,}(وا|تم|تن)$", w)
                or re.search("^ا.{2,}يت$", w) or re.search("^.{2,3}نا$", w))


def vowels(w: str) -> int:
    return len(re.findall("[اوي]", w))


def stems(w: str) -> list[str]:
    return [x for x in (w, re.sub("(ت|ن|نا|وا|ه|ها)$", "", w, count=1), re.sub("^[وفبلك]", "", w, count=1)) if len(x) >= 3]


def arabic_pattern(x: str) -> bool:  # فاعل، فعايل، مفاعل
    return bool(re.search("^.ا..$", x) or re.search("^..اي.$", x) or re.search("^م.ا..$", x))


# English prefixes Arabic writers often split off (أوت سورسنق, بري بروسيسنج, سب كونتراكتور)
PARTICLES = {normalize(w) for w in ["اوت", "بري", "سب", "اوفر", "ري", "اب", "داون", "ان", "انتر", "ميكرو", "ميني", "ملتي", "سوبر"]}
SUFFIXES = [("ات", "plural"), ("ين", "plural"), ("ون", "plural"), ("ها", "pron"), ("هم", "pron"), ("نا", "pron"), ("كم", "pron"),
            ("هن", "pron"), ("ه", "pron"), ("ز", "plural-en"), ("س", "plural-en")]  # ز/س: English plural s (مودلز، سيرفرز)
LETTERS: dict[str, str] = {}
for _n, _l in [("ايه", "a"), ("اي", "ia"), ("بي", "bp"), ("سي", "c"), ("دي", "d"), ("اف", "f"), ("جي", "g"), ("اتش", "h"), ("اتش", "h"), ("جيه", "j"),
               ("كي", "k"), ("ال", "l"), ("ام", "m"), ("ان", "n"), ("او", "o"), ("كيو", "q"), ("ار", "r"), ("اس", "s"), ("تي", "t"), ("يو", "u"),
               ("في", "v"), ("دبليو", "w"), ("اكس", "x"), ("واي", "y"), ("زد", "z"), ("زي", "z")]:
    LETTERS[normalize(_n)] = LETTERS.get(normalize(_n), "") + _l


def is_latin(t: str) -> bool:
    return bool(re.search(r"^[a-z0-9][a-z0-9.\-]*$", t))


def gap(text: str, a: dict, b: dict) -> bool:  # anything but spaces between two tokens
    return bool(re.search(r"\S", text[a["e"]:b["s"]]))


def ctx_words(text: str) -> set[str]:
    out = set()
    for w in re.findall("[ء-ي]{3,}", normalize(text)):
        w = w[2:] if w.startswith("ال") and len(w) > 4 else w
        out.add(w[1:] if w[0] in "وبل" and len(w) > 4 and w[1] != "ا" else w)
    return out


def _js_key_order(keys):
    """Object.entries order: array-index keys first (ascending), then insertion order."""
    idx = [k for k in keys if k.isdigit() and (k == "0" or k[0] != "0") and int(k) < 2**32 - 1]
    s = set(idx)
    return sorted(idx, key=int) + [k for k in keys if k not in s]


class Detector:
    EMB_W = 2  # weight of meaning-closeness to the sentence's other terms

    def __init__(self, data_dir: str | Path):
        data_dir = Path(data_dir)
        d = json.loads((data_dir / "index.json").read_text(encoding="utf-8"))
        self.dictionaries: list[str] = d["dictionaries"]
        self.senses: list[list] = d["senses"]
        self.forms: dict[str, list] = d["forms"]
        self.vocab: dict[str, int] = d["vocab"]
        ctx = data_dir / "context.json"
        self.ctx = json.loads(ctx.read_text(encoding="utf-8"))["kw"] if ctx.exists() else None
        self.vec = None
        vec = data_dir / "senses.txt"
        if vec.exists():
            v = np.frombuffer(base64.b64decode("".join(vec.read_text().split())), dtype=np.int8)
            if v.size == len(self.senses) * 128:
                self.vec = v.reshape(-1, 128)
        self.words, self.word_dom, self.word_vec = {}, None, None
        wj = data_dir / "words.json"
        if wj.exists():
            w = json.loads(wj.read_text(encoding="utf-8"))
            self.words = {x: i for i, x in enumerate(w["words"])}
            self.word_doms = w["domains"]
            self.word_dom = np.frombuffer(base64.b64decode(w["dom"]), dtype=np.int8).reshape(-1, len(w["domains"]))
            self.word_gen, self.gen_total = w.get("gen"), w.get("gen_total") or 1
            wv = data_dir / "words.txt"
            if wv.exists():
                v = np.frombuffer(base64.b64decode("".join(wv.read_text().split())), dtype=np.int8)
                if v.size == len(self.words) * 128:
                    self.word_vec = v.reshape(-1, 128)
        names = [normalize(n) for n in self.dictionaries]
        self.domains = [dict(dom, dicts={i for i, n in enumerate(names) if any(normalize(k) in n for k in dom["keys"])}) for dom in DOMAINS]
        self._build_phon()

    # ---- helpers that need the data
    def native(self, w: str) -> bool:
        return bool(NATIVE.search(w) or w.endswith("ه") or w in STOP or verb_shape(w)
                    or max(self.vocab.get(bare(w), 0), self.vocab.get(w, 0)) >= 3)

    def foreign_looking(self, w: str, lead: bool = True) -> bool:
        if self.native(w):
            return False
        if lead:
            return vowels(w) >= 2 or (vowels(w) >= 1 and len(ar_skel(w)) >= 5)
        return vowels(w) >= 1 or len(ar_skel(w)) >= 3

    def unseen(self, x: str) -> bool:
        return not (self.vocab.get(x) or self.vocab.get(bare(x)) or self.forms.get(x) or self.forms.get(bare(x)))

    def known_arabic(self, w: str) -> bool:  # a common word of the dictionaries' Arabic, not a listed transliteration (سولار)
        b = bare(w)
        return self.vocab.get(b, 0) >= 3 and not any(r[2] == "t" for r in self.forms.get(b, []))

    def bare_foreign(self, w: str) -> bool:  # no long vowel (بدجت، بزنس): foreign only if no Arabic stem shows up (كتبت → كتب)
        return not self.native(w) and vowels(w) <= 1 and len(ar_skel(w)) >= 4 and all(self.unseen(x) for x in stems(w))

    def looks_borrowed(self, w: str) -> bool:
        if re.search("^[a-z]{3,}$", w) and w not in STOP:
            return True
        return bool(re.search("^[ء-ي]{4,}$", w)) \
            and all(not self.native(x) and self.unseen(x) and not arabic_pattern(bare(x)) for x in stems(w)) \
            and self.foreign_looking(bare(re.sub("^[وفبلك](?=ال)", "", w, count=1))) and vowels(w) >= 2

    def _build_phon(self):
        self.phon: dict[str, list] = {}
        self.phon_wc: dict[str, set] = {}
        self.phon_en: dict[str, dict] = {}

        def add(sk, rows, wc, en):
            if sk not in self.phon:
                self.phon[sk], self.phon_wc[sk], self.phon_en[sk] = [], set(), {}
            self.phon[sk].extend(rows)
            self.phon_wc[sk].add(wc)
            self.phon_en[sk][en] = None

        wc = lambda en: len([x for x in re.split(r"[\s\-]+", en) if x])
        for key in _js_key_order(list(self.forms)):
            if re.search(r"^[a-z][a-z0-9 .\-]*$", key):
                for sk in en_skels(key):
                    if len(sk) >= 3:
                        add(sk, self.forms[key], wc(key), key)
        for i, sense in enumerate(self.senses):
            en = re.sub(r"\([^)]*\)", " ", sense[2] or "").lower().strip()
            if not en or len(en.split()) > 3:
                continue
            for sk in en_skels(en):
                if len(sk) >= 3:
                    add(sk, [[i, 1, "f"]], wc(en), en)
        self.phon_by_len: dict[int, list[str]] = {}
        self.phon_order = {k: i for i, k in enumerate(self.phon)}
        for k in self.phon:
            self.phon_by_len.setdefault(len(k), []).append(k)

    def _keep(self, rows, allowed):
        r = [x for x in rows if allowed is None or self.senses[x[0]][1] in allowed]
        return r or None

    def phonetic(self, word, allowed, words=1, loose=False, particle=False):
        sk = ar_skel(word)
        if len(sk) < 4:
            return None
        fits = lambda k: loose or words == 1 or words in self.phon_wc[k] or (particle and (words - 1) in self.phon_wc[k])
        if sk in self.phon and fits(sk):
            exact = self._keep(self.phon[sk], allowed)
            if exact:
                return {"rows": exact, "how": "exact", "key": sk}
        if len(sk) < 6:
            return None
        # only scores >= 0.85 are ever used, so skip keys that cannot reach it (same winner as a full scan):
        # lev >= max length - shared letters, and a score of 0.85 allows at most 15% edits
        cands = sorted((k for L in (len(sk) - 1, len(sk), len(sk) + 1) for k in self.phon_by_len.get(L, ())), key=self.phon_order.__getitem__)
        have = Counter(sk)
        best, best_score, best_key = None, 0.0, None
        for k in cands:
            longest = max(len(k), len(sk))
            limit = int(longest * 0.15 + 1e-9)
            if longest - sum((have & Counter(k)).values()) > limit or not fits(k):
                continue
            score = sim(sk, k)
            if score >= 0.85 and score > best_score:
                r = self._keep(self.phon[k], allowed)
                if r:
                    best, best_score, best_key = r, score, k
        return {"rows": best, "how": "near", "key": best_key} if best_score >= 0.85 else None

    def acronym_at(self, tokens, i, text, allowed):
        # 2-5 letter names in a row; the first may carry ال / و / ب / ل
        for n in range(min(5, len(tokens) - i), 1, -1):
            span = tokens[i:i + n]
            if any(gap(text, span[j - 1], span[j]) for j in range(1, n)):
                continue
            for prefix in ["", "ال", "وال", "بال", "لل", "و", "ب", "ل"]:
                first = span[0]["n"][len(prefix):] if span[0]["n"].startswith(prefix) else None
                if first is None or (prefix and not first):
                    continue
                names = [first] + [t["n"] for t in span[1:]]
                if not all(LETTERS.get(w) for w in names):
                    continue
                combos = [""]
                for w in names:
                    combos = [c + l for c in combos for l in LETTERS[w]]
                for c in combos[:32]:
                    rows = self.forms.get(c)
                    if rows and allowed is not None:
                        rows = [r for r in rows if self.senses[r[0]][1] in allowed]
                    if rows:
                        return {"n": n, "s": span[0]["s"], "e": span[-1]["e"], "prefix": prefix, "suffix": "", "sufKind": "", "head": c, "rows": rows, "how": "acronym"}
        return None

    @staticmethod
    def variants_of(first, rest):
        out = [("", first, "", "")]
        for p in PREFIXES:
            if not first.startswith(p):
                continue
            head = first[len(p):]
            mn = 2 if rest else 2 if is_latin(head) else 4 if len(p) == 1 else 3
            if len(head) >= mn:
                out.append((p, head, "", ""))
        if not rest:
            for p, head, _, _ in list(out):
                for suf, kind in SUFFIXES:
                    if not is_latin(head) and head.endswith(suf) and len(head) - len(suf) >= (3 if kind == "plural-en" else 5 if len(suf) == 1 else 4):
                        out.append((p, head[:-len(suf)], suf, kind))
        return out

    def find_matches(self, tokens, text, allowed):
        found, i = [], 0
        filt = lambda rows: [r for r in rows if self.senses[r[0]][1] in allowed] if rows and allowed is not None else rows
        while i < len(tokens):
            hit, everyday = None, None
            for n in range(min(6, len(tokens) - i), 0, -1):
                if hit or (everyday and everyday["n"] > 1):
                    break
                span = tokens[i:i + n]
                if any(gap(text, span[j - 1], span[j]) for j in range(1, n)):
                    continue
                rest, first = " ".join(t["n"] for t in span[1:]), span[0]["n"]
                for prefix, head, suffix, suf_kind in self.variants_of(first, rest):
                    key = head + " " + rest if rest else head
                    if len(key) < 2 or (n == 1 and (re.search("^[a-z]$", key) or key in STOP or first in STOP)):
                        continue
                    no_al = " ".join(bare(w) for w in key.split(" ")) if n > 1 else key
                    rows = filt(self.forms.get(key))
                    if not rows and no_al != key:
                        rows = filt(self.forms.get(no_al))
                    if rows and suf_kind == "plural-en":
                        rows = [r for r in rows if r[2] == "t"]
                    words = [head] + [t["n"] for t in span[1:]]
                    # colloquial forms (c: دوام) are always worth replacing, so they stay ordinary matches
                    if rows and not any(r[1] & 4 for r in rows) and all(not re.search("[tfac]", r[2]) for r in rows) \
                            and all(ARABIC_WORD.search(w) and (w in STOP or self.vocab.get(bare(w), 0) >= self.EVERYDAY_VOCAB) for w in words) \
                            and not all(w in STOP for w in words):
                        # everyday Arabic word or phrase (عميل، على الهواء): a term only when the context says so, decided in analyse()
                        if everyday is None:
                            everyday = {"n": n, "s": span[0]["s"], "e": span[-1]["e"], "prefix": prefix, "suffix": suffix, "sufKind": suf_kind,
                                        "head": "".join(words), "rows": rows, "how": "everyday"}
                        rows = None
                    if rows:
                        hit = {"n": n, "s": span[0]["s"], "e": span[-1]["e"], "prefix": prefix, "suffix": suffix, "sufKind": suf_kind,
                               "head": "".join([head] + [t["n"] for t in span[1:]]), "rows": rows, "how": "dict"}
                        break
            if not hit:
                hit = self.acronym_at(tokens, i, text, allowed)
            # nothing in the dictionaries (or only a one-word hit followed by more foreign words, as in «سولار بانلز»):
            # try a phonetic match of an Arabic-letter spelling of 1-3 words written together or apart
            dict_hit = hit
            min_n = 2 if hit and hit["n"] == 1 and i + 1 < len(tokens) and self.foreign_looking(tokens[i + 1]["n"], False) else 1
            if min_n == 2:
                hit = None
            for n in range(min(3, len(tokens) - i), min_n - 1, -1):
                if hit:
                    break
                span = tokens[i:i + n]
                if any(gap(text, span[j - 1], span[j]) for j in range(1, n)):
                    continue
                if any(not ARABIC_WORD.search(t["n"]) for t in span):
                    continue
                if any(not self.foreign_looking(t["n"], False) for t in span[1:]):
                    continue
                best_ph = None  # an exact sound match beats a near one, a stripped reading beats the raw word
                if span[0]["n"].endswith("ه") and n == 1:
                    continue
                for prefix, head, suffix, suf_kind in self.variants_of(span[0]["n"], "x" if n > 1 else ""):
                    if suffix == "ه":
                        continue
                    word = "".join([head] + [t["n"] for t in span[1:]])
                    # in a phrase the first word may itself be a known transliteration (سولار); judge its letters, and the phrase as a whole
                    strict_only = n == 1 and not self.foreign_looking(head) and self.bare_foreign(head)
                    head_ok = (self.foreign_looking(head) or strict_only) if n == 1 else \
                        not NATIVE.search(head) and head not in STOP and not verb_shape(head) and vowels(head) + len(ar_skel(head)) >= 3 \
                        and (bare(head) in PARTICLES or not self.known_arabic(head))  # «الطيار أنهى» is not «late turn»
                    if not head_ok or (n > 1 and not self.foreign_looking(word)):
                        continue
                    ph = self.phonetic(word, allowed, n, False, n > 1 and bare(head) in PARTICLES)
                    if not ph or (strict_only and ph["how"] != "exact"):
                        continue
                    if n > 1 and bare(head) not in PARTICLES:  # «سولار بانلز» starts like «solar panels»; «التزم بالكونتراكت» does not
                        lead = ar_skel(head)
                        near = lambda x, y: 1 - lev(x, y) / max(len(x), len(y), 1) >= 0.6
                        agrees = any(lead[:1] == sk[:1] and any(L > 0 and near(lead, sk[:L]) for L in (len(lead) - 1, len(lead), len(lead) + 1))
                                     for en in self.phon_en[ph["key"]] for sk in en_skels(re.split(r"[\s\-]+", en)[0]))
                        if not agrees:
                            continue
                    score = (10 if ph["how"] == "exact" else 0) + len(prefix) + len(suffix)
                    if not best_ph or score > best_ph[0]:
                        best_ph = (score, {"n": n, "s": span[0]["s"], "e": span[-1]["e"], "prefix": prefix, "suffix": suffix, "sufKind": suf_kind,
                                           "head": word, "rows": ph["rows"], "how": ph["how"]})
                if best_ph:
                    hit = best_ph[1]
            if not hit:
                hit = dict_hit or everyday
            if hit and hit["how"] == "dict":
                w = hit["head"]
                if ARABIC_WORD.search(w) and self.foreign_looking(w):
                    ph = self.phonetic(w, allowed, hit["n"], True)  # only adds candidates to rank; the match came from the dictionary
                    if ph:
                        seen = {r[0] for r in hit["rows"]}
                        hit["rows"] = hit["rows"] + [r for r in ph["rows"] if r[0] not in seen]
            if hit:
                found.append(hit)
                i += hit["n"]
            else:
                i += 1
        return found

    # ---- context
    def centroid(self, rows):  # average meaning of the given senses (float32, as in the page)
        if self.vec is None or not rows:
            return None
        c = self.vec[rows].astype(np.float32).sum(axis=0)
        n = math.sqrt(float((c.astype(np.float64) ** 2).sum())) or 1
        return (c.astype(np.float64) / n).astype(np.float32)

    def sim_to(self, i, c):
        return float(np.dot(self.vec[i].astype(np.float64), c.astype(np.float64))) / 127

    def context_score(self, sense_idx, words, own):
        if not self.ctx or not self.ctx[sense_idx]:
            return 0
        sc = sum(math.log(40102 / max(1, self.vocab.get(w, 0) or 1)) for w in self.ctx[sense_idx].split(" ") if w and w in words and w not in own)
        return min(1.5, sc / 6)

    EVERYDAY_TYPICAL = 0.6  # context words must lean towards the chosen domain at least this much (mean log-odds)
    EVERYDAY_VOCAB = 10     # a word seen this often in the dictionaries' Arabic is ordinary Arabic, not a borrowed form
    EVERYDAY_W = 6          # weight of meaning-closeness when choosing the sense of an everyday word
    GENERAL_RATE = 6e-5     # a one-word term this frequent in general articles is an ordinary word (يجب، مجموعة), not a term

    def general_word(self, term: str) -> bool:
        words = normalize(re.sub(r"\([^)]*\)", " ", term)).split()
        if len(words) != 1 or not self.word_gen:
            return False
        w = next(iter(ctx_words(words[0])), None)
        return w in self.words and self.word_gen[self.words[w]] / self.gen_total >= self.GENERAL_RATE

    def everyday_evidence(self, text: str, m: dict, domain_id: str, senses: list[int]) -> tuple[float, dict]:
        """How strongly the text around an everyday word leans to the domain, and how close its meaning is to each sense."""
        if self.word_dom is None:
            return (-9.0, {})
        own = ctx_words(text[m["s"]:m["e"]])
        ids = [self.words[w] for w in ctx_words(text) if w not in own and w in self.words]
        if not ids:
            return (-9.0, {})
        j = self.word_doms.index(domain_id)
        typical = float(self.word_dom[ids, j].astype(np.float64).mean()) / 16
        close = {}
        if self.word_vec is not None and self.vec is not None:
            c = self.word_vec[ids].astype(np.float64).sum(axis=0)
            c /= (np.linalg.norm(c) or 1)
            close = {i: float(self.vec[i].astype(np.float64) @ c) / 127 for i in senses}
        return (typical, close)

    def analyse(self, text: str, domain_id: str = "tech") -> dict:
        dom = next(d for d in self.domains if d["id"] == domain_id)
        allowed = dom["dicts"]
        tokens = tokenize(text)
        matches = self.find_matches(tokens, text, allowed)
        score: dict[int, float] = {}
        for m in matches:
            if m["how"] == "everyday":
                continue
            std_only = all(r[1] & 4 for r in m["rows"])
            w = (0.6 if m["n"] > 1 else 0.25) if std_only else 1
            dicts = list(dict.fromkeys(self.senses[r[0]][1] for r in m["rows"]))
            for d in dicts:
                score[d] = score.get(d, 0) + w / len(dicts)
        ranked = sorted(score.items(), key=lambda x: -x[1])
        total = sum(s for _, s in ranked) or 1
        domain = ranked[0][0] if ranked else None
        top3 = {d for d, _ in ranked[:3]}
        text_words = ctx_words(text)
        # the meaning of each match: its sense when unambiguous, else the average of its senses
        match_rows = [[] if m["how"] == "everyday" else list(dict.fromkeys(r[0] for r in m["rows"]))[:12] for m in matches]
        all_key = lambda t: " ".join(bare(w) for w in normalize(re.sub(r"\([^)]*\)", " ", t)).split(" "))
        items = []
        for mi, m in enumerate(matches):
            anchors = [x for j, rows in enumerate(match_rows)
                       if not (j == mi or (matches[j]["s"] < m["e"] and matches[j]["e"] > m["s"])) and len(rows) <= 3 for x in rows]
            ctx_vec = self.centroid(anchors)
            in_domain = [r for r in m["rows"] if self.senses[r[0]][1] == domain]
            word_sims = None
            if m["how"] == "everyday":
                rows = [r for r in m["rows"] if not self.general_word(self.senses[r[0]][0])]
                typical, word_sims = self.everyday_evidence(text, m, domain_id, [r[0] for r in rows])
                if not rows or typical < self.EVERYDAY_TYPICAL:
                    continue
                m = dict(m, rows=rows)
            if m["how"] == "everyday" and any(same_term(text[m["s"]:m["e"]], self.senses[r[0]][0]) for r in m["rows"]):
                continue  # already the term, in another form
            is_std = any(r[1] & 4 for r in m["rows"])  # a standard term somewhere in the chosen domain: leave it
            if is_std and m["n"] == 1 and not in_domain:
                continue
            by_term: dict[str, list] = {}
            for r in m["rows"]:
                k = all_key(self.senses[r[0]][0])
                if k not in by_term or (r[1] & 1 and not by_term[k][1] & 1):
                    by_term[k] = r
            p = m.get("head") or ""
            everyday = m["how"] == "everyday"  # an Arabic word: no sound match, and its sense comes from the words around it
            surf = "" if everyday else ar_skel(p) if ARABIC_WORD.search(p) else (en_skels(p)[0] if re.search(r"^[a-z0-9.\- ]+$", p) else "")
            own = ctx_words(text[m["s"]:m["e"]])

            def rank(r):
                sense = self.senses[r[0]]
                en = re.sub(r"\([^)]*\)", " ", sense[2] or "")
                sound = 0
                if surf and en:
                    for sk in en_skels(en):
                        sound = max(sound, sim(surf, sk))
                acr = 1 if m["how"] == "acronym" and re.search(r"\(" + m["head"] + r"s?\)|^" + m["head"] + "$", sense[2] or "", re.I) else 0
                ctx = 0 if everyday else self.context_score(r[0], text_words, own)
                return acr + ctx + sound * 2 + (0.3 if r[1] & 1 else 0) + (0.3 if sense[1] == domain else 0.1 if sense[1] in top3 else 0) - len(sense[0]) / 200

            vals = list(by_term.values())
            # meaning closeness: to the other terms found; for an everyday word, to all the words around it
            sims = word_sims or ({r[0]: self.sim_to(r[0], ctx_vec) for r in vals} if ctx_vec is not None else None)
            mean_sim = sum(sims.values()) / len(sims) if sims else 0
            w_sim = self.EVERYDAY_W if everyday else self.EMB_W
            scores = {id(r): rank(r) + ((sims[r[0]] - mean_sim) * w_sim if sims else 0) for r in vals}
            choices = sorted(vals, key=lambda r: -scores[id(r)])
            best, reasons = choices[0], []
            if len(choices) > 1 and scores[id(choices[0])] - scores[id(choices[1])] < 0.5:
                reasons.append("يحتمل أكثر من مصطلح")
            if best[1] & 2:
                reasons.append("له معنى آخر شائع في الاستعمال اليومي")
            if m["how"] == "near":
                reasons.append("كتابة قريبة من صيغة معروفة، تحقّق منها")
            if m["how"] == "everyday":
                reasons.append("كلمة عامة لها مصطلح تخصصي في هذا السياق")
            notes = []
            if m["how"] == "acronym":
                notes.append(f"اختصار مكتوب بأسماء الحروف ({m['head'].upper()})")
            elif m["how"] not in ("dict", "everyday"):
                notes.append("اكتُشفت بالمطابقة الصوتية مع الصيغة الإنجليزية")
            if m["sufKind"] in ("plural", "plural-en"):
                notes.append("وردت بصيغة الجمع، فراجع صيغة المصطلح بعد الاستبدال")
            items.append({"m": m, "original": text[m["s"]:m["e"]], "state": "std" if is_std else "review" if reasons else "replace",
                          "best": best, "choices": choices, "reasons": reasons, "notes": notes})
        # words that look borrowed but match nothing in the chosen domain: shown as a note, never replaced
        covered = lambda t: any(t["s"] < m["e"] and t["e"] > m["s"] for m in matches)
        seen, unknown = set(), []
        for t in tokens:
            word = text[t["s"]:t["e"]]
            if covered(t) or word in seen or not self.looks_borrowed(t["n"]):
                continue
            seen.add(word)
            elsewhere = {self.senses[r[0]][1] for m in self.find_matches([dict(t, s=0, e=len(word))], word, None) for r in m["rows"]}
            unknown.append({"word": word, "domains": [d["label"] for d in self.domains if d["id"] != domain_id and elsewhere & d["dicts"]]})
        return {"tokens": tokens, "items": items, "ranked": ranked, "total": total, "domain": domain, "unknown": unknown}


def light_stem(w: str) -> str:
    w = bare(w)
    return re.sub("(ات|ين|ون|يه|ه|ي)$", "", w) if len(w) > 4 else w


def same_term(original: str, term: str) -> bool:
    """The text already uses the term, only in another form (الشبكات العصبية / شبكة عصبية, وسائل الإعلام / وسائل إعلامية)."""
    a = [light_stem(w) for w in normalize(original).split()]
    b = [light_stem(w) for w in normalize(re.sub(r"\([^)]*\)", " ", term)).split()]
    return len(a) == len(b) and all(x.startswith(y) or y.startswith(x) for x, y in zip(a, b) if min(len(x), len(y)) >= 3) \
        and all(min(len(x), len(y)) >= 3 for x, y in zip(a, b))


def adapt_article(term: str, prefix: str, original: str) -> str:
    words = term.split(" ")
    lead = re.sub("ال$|لل$", lambda m: "ل" if m.group() == "لل" else "", prefix)
    if len(words) > 1:
        return lead + term
    had_al = prefix.endswith("ال") or prefix in ("لل", "ولل") or (not prefix and normalize(original).startswith("ال"))
    if had_al and not words[0].startswith("ال"):
        words[0] = "ال" + words[0]
    if not had_al and words[0].startswith("ال") and len(words[0]) > 3:
        words[0] = words[0][2:]
    out = " ".join(words)
    if prefix in ("لل", "ولل"):
        return ("و" if prefix == "ولل" else "") + "لل" + out[2:]
    return lead + out


def with_suffix(word: str, m: dict) -> str:
    if m["sufKind"] != "pron" or " " in word:
        return word
    return (word[:-1] + "ت" if word.endswith("ة") else word) + m["suffix"]


def replacement(term: str, item: dict) -> str:
    """The term as it should appear in the sentence (article, و/ب/ل and pronoun endings carried over)."""
    return with_suffix(adapt_article(term, item["m"]["prefix"], item["original"]), item["m"])
