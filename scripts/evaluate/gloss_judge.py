"""Experiment: ArabGlossBERT (Al-Hajj & Jarrar, 2021; SinaLab/ArabGlossBERT, CC BY-SA 4.0) as a context-gloss judge for
Kass suggestions. It only scores pairs (sentence with the word marked, term definition); it never proposes anything.

Two tests:
  1. the 600 decision cases (reports/decision_gemma.json): same form, right term vs another term;
  2. the review-tier suggestions Kass makes on the gold sets: right (expect / also) vs wrong.
Run: .venv/Scripts/python scripts/evaluate/gloss_judge.py   (model files in data/models/arabglossbert)
Input format as in SinaTools (wsd/wsd.py): «context with [UNUSED0]word[UNUSED1] [SEP] word: gloss».
"""
import glob
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
from transformers import BertForSequenceClassification, BertTokenizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
MDIR = ROOT / "data" / "models" / "arabglossbert"
DIAC = re.compile("[ً-ْٰـ]")

tok = BertTokenizer.from_pretrained(str(MDIR / "bert-base-arabertv02"))
model = BertForSequenceClassification.from_pretrained(
    str(MDIR / "bert-base-arabertv02_22_May_2021_00h_allglosses_unused01"), num_labels=2).eval()
torch.set_num_threads(8)


def clean(s: str) -> str:
    return " ".join(DIAC.sub("", s or "").split())


def score(pairs: list[tuple[str, str, str]], batch: int = 16) -> np.ndarray:
    """pairs: (sentence, word, gloss) -> logit of the «same sense» class minus the other."""
    texts = []
    for sent, word, gloss in pairs:
        sent = clean(sent)
        i = sent.find(word)
        marked = sent[:i] + "[UNUSED0]" + word + "[UNUSED1]" + sent[i + len(word):] if i >= 0 else sent
        texts.append(f"{marked} [SEP] {clean(word)}: {clean(gloss)}")
    out = []
    for k in range(0, len(texts), batch):
        enc = tok(texts[k:k + batch], max_length=256, padding=True, truncation=True, return_tensors="pt")
        seg = torch.zeros_like(enc["input_ids"])
        for r, ids in enumerate(enc["input_ids"].tolist()):  # segment 1 after the first [SEP], as SinaTools does
            j = ids.index(tok.sep_token_id) if tok.sep_token_id in ids else len(ids)
            seg[r, j + 1:] = 1
        with torch.no_grad():
            lg = model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"], token_type_ids=seg).logits
        out += (lg[:, 1] - lg[:, 0]).tolist()
    return np.array(out)


def auc(y, s):
    y, s = np.array(y), np.array(s)
    pos, neg = s[y == 1], s[y == 0]
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def report(name, y, s):
    y = np.array(y)
    print(f"\n== {name}: {len(y)} cases ({int(y.sum())} right), AUC {auc(y, s):.3f}")
    print("threshold | kept | precision of kept | right kept (recall)")
    print(f"     none | {len(y)} | {y.mean():.3f} | 1.000")
    for t in (-2, -1, 0, 1, 2):
        k = s >= t
        if k.sum():
            print(f"{t:>9} | {int(k.sum())} | {y[k].mean():.3f} | {y[k].sum() / max(1, y.sum()):.3f}")


# definitions from the enriched files (full text), by (dictionary name, term without diacritics)
defs = {}
for p in glob.glob(str(ROOT / "data" / "dictionaries" / "enriched" / "*.enriched.json")):
    d = json.load(open(p, encoding="utf-8"))
    name = " ".join(d["dictionary_name"].split())
    for r in d["records"]:
        defs.setdefault((name, clean(r.get("term_without_diacritics") or r["term"])), r.get("definition") or "")


def gloss_of(term, dictionary, english):
    g = defs.get((" ".join(dictionary.split()), clean(term)), "")
    return f"{clean(term)}، {g}" if g else f"{clean(term)} ({english})"


t0 = time.time()
cases = json.load(open(ROOT / "reports" / "decision_gemma.json", encoding="utf-8"))["results"]
s1 = score([(c["sentence"], c["form"], gloss_of(c["term"], c["dictionary"], c["english"])) for c in cases])
report("600 decision cases (Gemma 3 12B: accuracy 0.66, precision 0.615)", [int(c["expected"]) for c in cases], s1)
print(f"time {time.time() - t0:.0f}s, {1000 * (time.time() - t0) / len(cases):.0f} ms per case")

# 2. review-tier suggestions on the gold sets
from kass_layer.detector.engine import Detector  # noqa: E402
det = Detector(ROOT / "demo_local")
rows = []
for f in sorted(glob.glob(str(ROOT / "scripts" / "demo" / "tests" / "gold-*.json"))):
    if "unify" in f:
        continue
    for c in json.load(open(f, encoding="utf-8")):
        ok = {**c.get("expect", {}), **c.get("also", {})}
        for it in det.analyse(c["text"], c["domain"])["items"]:
            if it["state"] != "review":
                continue
            sense = det.senses[it["best"][0]]
            want = ok.get(it["original"])
            right = bool(want) and any(clean(sense[0]).replace("ال", "", 1) == clean(w).replace("ال", "", 1) or clean(sense[0]) == clean(w)
                                       for w in want.split("|"))
            rows.append((c["text"], it["original"], gloss_of(sense[0], det.dictionaries[sense[1]], sense[2]), int(right),
                         Path(f).name, sense[0]))
s2 = score([(a, b, g) for a, b, g, *_ in rows])
report("review-tier suggestions on the gold sets", [r[3] for r in rows], s2)
json.dump([{"set": r[4], "text": r[0], "word": r[1], "term": r[5], "right": r[3], "score": round(float(x), 3)}
           for r, x in zip(rows, s2)], open(ROOT / "logs" / "gloss_judge_review.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
