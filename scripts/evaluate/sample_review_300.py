"""A new blind review sample of Kass suggestions on Arabic Wikipedia articles (CC BY-SA), for two judges.

Diversity rules (the first sample repeated a few terms, e.g. الأسهم and صفيف شمسي): at most one suggestion per proposed
term and per word, at most two per article, an equal share per domain (eight domains), and no word or term that was in
the earlier 200- and 50-item samples. Texts: data/corpus/wikipedia/<domain>.jsonl (six domains; used only for word
statistics, never to design or test a rule); lang and heritage use the random «general» articles (no domain corpus).

Run: .venv/Scripts/python scripts/evaluate/sample_review_300.py <extra_dir with lang.jsonl, heritage.jsonl> [n]
Writes logs/review_sample_300_items.json (what the judges see) and logs/review_sample_300_key.json (tier etc.).
"""
import collections
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from kass_layer.detector.engine import Detector, bare, normalize  # noqa: E402

extra = Path(sys.argv[1])
N = int(sys.argv[2]) if len(sys.argv) > 2 else 300
PER_DOMAIN_ARTICLES = 120
DOMS = ["tech", "legal", "finance", "media", "eng", "culture", "lang", "heritage"]
LABEL = {"tech": "تقني", "legal": "قانوني", "finance": "مالي وإداري", "media": "إعلامي", "eng": "هندسي",
         "culture": "علمي وثقافي", "lang": "لغوي وأدبي", "heritage": "تراثي"}
rng = random.Random(29)
det = Detector(ROOT / "demo_local")

# words and terms already judged
old_words, old_terms = set(), set()
for k in json.load(open(ROOT / "logs/review_sample_200_key.json", encoding="utf-8")):
    old_words.add(bare(normalize(k["word"])))
    old_terms.add(normalize(k["term"]))
try:
    import openpyxl
    for r in openpyxl.load_workbook(ROOT / "logs/review_sample_50.xlsx").active.iter_rows(min_row=3, values_only=True):
        for v in r[:8]:
            if isinstance(v, str) and len(v) < 40:
                old_words.add(bare(normalize(v)))
except Exception as e:  # the 50-item sheet is optional
    print("50-item sheet not read:", e)


def context(text, s, e):
    a = max(text.rfind(".", 0, s), text.rfind("\n", 0, s))
    b = min([x for x in (text.find(".", e), text.find("\n", e)) if x != -1] or [len(text)])
    return text[max(a + 1, s - 200):min(b + 1, e + 200)].strip()


cands = collections.defaultdict(list)
for dom in DOMS:
    own = ROOT / f"data/corpus/wikipedia/{dom}.jsonl"
    # lang and heritage have no corpus file: Kass searches only their dictionaries, so general articles serve
    path = own if own.exists() else extra / f"{dom}.jsonl" if (extra / f"{dom}.jsonl").exists() else ROOT / "data/corpus/wikipedia/general.jsonl"
    arts = [json.loads(l) for l in open(path, encoding="utf-8")]
    rng.shuffle(arts)
    for a in arts[:PER_DOMAIN_ARTICLES if own.exists() else 700]:
        text = a["text"]
        for it in det.analyse(text, dom)["items"]:
            if it["state"] == "std":
                continue
            sense = det.senses[it["best"][0]]
            cands[dom].append({"title": a["title"], "domain": dom, "word": it["original"], "term": sense[0],
                               "english": sense[2], "definition": sense[3], "dictionary": det.dictionaries[sense[1]],
                               "state": it["state"], "context": context(text, it["m"]["s"], it["m"]["e"])})
    print(dom, len(cands[dom]), "suggestions", flush=True)

used_terms, used_words, per_article = set(old_terms), set(old_words), collections.Counter()


def ok(c):
    t, w = normalize(c["term"]), bare(normalize(c["word"]))
    return t not in used_terms and w not in used_words and per_article[c["title"]] < 2 and len(c["context"]) > 20


def take(c):
    used_terms.add(normalize(c["term"]))
    used_words.add(bare(normalize(c["word"])))
    per_article[c["title"]] += 1


for d in DOMS:
    rng.shuffle(cands[d])
    cands[d].sort(key=lambda c: c["state"] != "replace")  # confident ones first so the replace tier is well represented
pick = collections.defaultdict(list)
quota = N // len(DOMS)
for d in DOMS:  # equal share per domain, half of it confident ones where there are enough
    for c in cands[d]:
        if len(pick[d]) >= quota:
            break
        if c["state"] == "replace" and sum(x["state"] == "replace" for x in pick[d]) >= quota // 2:
            continue
        if ok(c):
            take(c)
            pick[d].append(c)
    for c in cands[d]:
        if len(pick[d]) >= quota:
            break
        if c not in pick[d] and ok(c):
            take(c)
            pick[d].append(c)
rest = [c for d in DOMS for c in cands[d] if c not in pick[d]]
rng.shuffle(rest)
while sum(map(len, pick.values())) < N and rest:  # fill the remainder from domains that have more
    c = rest.pop()
    if ok(c):
        take(c)
        pick[c["domain"]].append(c)

sample = [c for d in DOMS for c in pick[d]]
rng.shuffle(sample)
for i, c in enumerate(sample, 1):
    c["n"] = i
json.dump(sample, open(ROOT / "logs/review_sample_300_key.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
items = [{"n": c["n"], "d": LABEL[c["domain"]], "c": c["context"], "w": c["word"], "t": c["term"],
          "f": (c["definition"] or "")[:220], "m": c["dictionary"]} for c in sample]
json.dump(items, open(ROOT / "logs/review_sample_300_items.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(sample), collections.Counter(c["domain"] for c in sample), collections.Counter(c["state"] for c in sample))
print("distinct terms", len({normalize(c["term"]) for c in sample}), "distinct words", len({bare(normalize(c["word"])) for c in sample}),
      "articles", len({c["title"] for c in sample}))
