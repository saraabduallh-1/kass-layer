"""Trials after the 300-item Wikipedia review (2026-11-19). Each trial is a patch applied at run time, so the engine
file is untouched; nothing here is adopted until the owner decides.

  E1  stricter sound match: reject when the consonant key fits several different English words, or when the Arabic
      long vowels do not follow the English vowels
  E2  a Latin word that is part of a longer English run (a reference, a sentence) or inside a formula is not a borrowing
  E3  an Arabic-letter acronym that is part of a longer run of letter names (كيه بي إم جي) is not that acronym
  E4  the name rule also for dictionary transliterations (بول بليشكا، بروس كاري)

Measured on: the gold sets (recall/precision), the 300 Wikipedia suggestions (ChatGPT labels: how many right/wrong each
trial removes) and the 103 article suggestions (owner labels).
Run: .venv/Scripts/python scripts/evaluate/phonetic_experiments.py
"""
import collections
import csv
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import kass_layer.detector.engine as E  # noqa: E402

det = E.Detector(ROOT / "demo_local")
ORIG_PHON = E.Detector.phonetic
ORIG_FIND = E.Detector.find_matches
LATIN = re.compile(r"^[A-Za-z][A-Za-z\-]*$")
ON = set()


def en_letters(w):
    return re.sub("[^a-z]", "", w.lower())


def vowel_ok(word, english):
    """The Arabic long vowels (ا و ي after the first letter) must appear, in order, among the English vowels."""
    ar = [{"ا": "a", "و": "u", "ي": "i"}[c] for c in word[1:] if c in "اوي"]
    en = []
    for c in en_letters(english)[1:]:
        k = {"a": "a", "e": "i", "i": "i", "y": "i", "o": "u", "u": "u"}.get(c)
        if k and (not en or en[-1] != k):
            en.append(k)
    j = 0
    for v in ar:
        while j < len(en) and not (en[j] == v or (v == "a" and en[j] in "au") or (v == "u" and en[j] in "ua")):
            j += 1
        if j == len(en):
            return False
        j += 1
    return True


def phonetic(self, word, allowed, words=1, loose=False, particle=False):
    r = ORIG_PHON(self, word, allowed, words, loose, particle)
    if r and not loose and ON & {"E1a", "E1b", "E1c"}:
        ens = {en_letters(e) for e in self.phon_en[r["key"]]}
        if "E1a" in ON and len(ens) > 1 and not any(a != b and (a.startswith(b) or b.startswith(a)) for a in ens for b in ens):
            return None
        if "E1c" in ON:  # several different English words in the chosen domain's own senses
            own = {en_letters(re.sub(r"\([^)]*\)", "", self.senses[x[0]][2] or "")) for x in r["rows"]} - {""}
            if len(own) > 1 and not any(a != b and (a in b or b in a) for a in own for b in own):
                return None
        if "E1b" in ON and not any(vowel_ok(word, e) for e in self.phon_en[r["key"]]):
            return None
    return r


def find_matches(self, tokens, text, allowed):
    hits = ORIG_FIND(self, tokens, text, allowed)
    out = []
    starts = {t["s"]: k for k, t in enumerate(tokens)}
    for h in hits:
        k = starts.get(h["s"])
        if k is None:
            out.append(h)
            continue
        prev = tokens[k - 1] if k > 0 else None
        nxt = tokens[k + h["n"]] if k + h["n"] < len(tokens) else None
        span = text[h["s"]:h["e"]]
        if ON & {"E2", "E2m"} and re.search("[A-Za-z]", span):
            near = lambda t: t is not None and LATIN.match(text[t["s"]:t["e"]]) and len(text[t["s"]:t["e"]]) > 1 \
                and not re.search(r"[^\s(]", text[min(t["e"], h["s"]):max(t["s"], h["e"])].replace(text[h["s"]:h["e"]], ""))
            window = text[max(0, h["s"] - 40):h["e"] + 40]
            if ("E2" in ON and (near(prev) or near(nxt))) or re.search(r"\\[a-z]+|[{}^=]", window):
                continue
        if "E3" in ON and h["how"] == "acronym" and ((prev and E.LETTERS.get(prev["n"])) or (nxt and E.LETTERS.get(nxt["n"]))):
            continue
        if "E4" in ON and h["how"] == "dict" and all(r[2] == "t" for r in h["rows"]) and self.name_context(tokens, k, h["n"], text):
            continue
        out.append(h)
    return out


E.Detector.phonetic = phonetic
E.Detector.find_matches = find_matches


def gold():
    res = {}
    for f in sorted(glob.glob(str(ROOT / "scripts/demo/tests/gold-*.json"))):
        if "unify" in f:
            continue
        tp = fn = fp = 0
        for c in json.load(open(f, encoding="utf-8")):
            ex = c.get("expect", {})
            ok = {**ex, **c.get("also", {})}
            got = {it["original"] for it in det.analyse(c["text"], c["domain"])["items"] if it["state"] != "std"}
            tp += sum(w in got for w in ex)
            fn += sum(w not in got for w in ex)
            fp += sum(w not in ok for w in got)
        res[Path(f).stem[5:]] = (tp, fn, fp)
    return res


key300 = {k["n"]: k for k in json.load(open(ROOT / "logs/review_sample_300_key.json", encoding="utf-8"))}
gpt300 = {int(r["row"]): r["الحكم"].strip() for r in csv.DictReader(open(ROOT / "logs/chatgpt_judgments_300.csv", encoding="utf-8-sig")) if r["row"]}
key200 = {k["n"]: k for k in json.load(open(ROOT / "logs/review_sample_200_key.json", encoding="utf-8"))}
human = {}
for f in glob.glob(str(ROOT / "logs/review_labels/labels/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    d = d.get("data", d)
    human[int(d["row"])] = d["label"]
arts = {}
for f in sorted(glob.glob(str(ROOT / "logs/real_articles/*.json"))):
    for i, a in enumerate(json.load(open(f, encoding="utf-8"))):
        arts[f"{Path(f).name}#{i}"] = a


def kept(text, domain, word, term):
    return any(it["original"] == word and E.normalize(det.senses[it["best"][0]][0]) == E.normalize(term)
               for it in det.analyse(text, domain)["items"])


def wiki():
    c = collections.Counter()
    for n, k in key300.items():
        c[gpt300[n]] += kept(k["context"], k["domain"], k["word"], k["term"])
    return c


def articles():
    c, cache = collections.Counter(), {}
    for n, l in human.items():
        k = key200[n]
        a = arts[k["ref"]]
        if k["ref"] not in cache:
            cache[k["ref"]] = {(it["original"], E.normalize(det.senses[it["best"][0]][0])) for it in det.analyse(a["text"], a["domain"])["items"]}
        c[l] += (k["word"], E.normalize(k["term"])) in cache[k["ref"]]
    return c


def fmt(g):
    tp, fn, fp = map(sum, zip(*g.values()))
    return f"gold recall {100 * tp / (tp + fn):.1f} precision {100 * tp / (tp + fp):.1f} (tp {tp}, missed {fn}, extra {fp})"


base_g, base_w, base_a = gold(), wiki(), articles()
print("BASE", fmt(base_g), "| wiki kept", dict(base_w), "| articles kept", dict(base_a))
for trial in [t.split("+") for t in (sys.argv[1:] or ["E1a", "E1b", "E2m", "E3", "E4"])]:
    ON.clear()
    ON.update(trial)
    g, w, a = gold(), wiki(), articles()
    lost = {s: (base_g[s][0] - g[s][0], g[s][2] - base_g[s][2]) for s in g if g[s] != base_g[s]}
    print("+".join(trial), fmt(g), "| changed sets (tp lost, extra added):", lost)
    print("    wiki removed:", {l: base_w[l] - w[l] for l in base_w}, "| articles removed:", {l: base_a[l] - a[l] for l in base_a})
