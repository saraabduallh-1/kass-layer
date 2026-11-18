"""Scores the blind human review of Kass suggestions on real articles (phone review page, db collection «labels»)
against the answer key, and compares it with an LLM judge (ChatGPT CSV: row,حكم).

Run: .venv/Scripts/python scripts/evaluate/score_human_review.py
Inputs (local, not in git): logs/review_labels/labels/*.json, logs/review_sample_200_key.json, logs/chatgpt_judgments_103.csv
"""
import collections
import csv
import glob
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNSURE = {"غير متأكدة", "غير متأكد"}


def wilson(k, n, z=1.96):
    if not n:
        return "-"
    p = k / n
    c = (p + z * z / 2 / n) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / 4 / n / n) / (1 + z * z / n)
    return f"{100 * p:.1f}% ({k}/{n}, 95% CI {100 * (c - h):.0f}–{100 * (c + h):.0f}%)"


def precision(labels, rows):
    dec = [labels[n] for n in rows if labels[n] not in UNSURE]
    return wilson(sum(x == "صحيح" for x in dec), len(dec))


key = {k["n"]: k for k in json.load(open(ROOT / "logs/review_sample_200_key.json", encoding="utf-8"))}
human = {}
for f in glob.glob(str(ROOT / "logs/review_labels/labels/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    d = d.get("data", d)
    human[int(d["row"])] = d["label"]
print("human:", dict(collections.Counter(human.values())))
print("all     ", precision(human, human))
for tier in ("replace", "review"):
    print(f"{tier:8}", precision(human, [n for n in human if key[n]["state"] == tier]))
for dom in sorted({key[n]["domain"] for n in human}):
    print(f"{dom:8}", precision(human, [n for n in human if key[n]["domain"] == dom]))

gpt_path = ROOT / "logs/chatgpt_judgments_103.csv"
if gpt_path.exists():
    gpt = {int(r["row"]): r["حكم"].strip() for r in csv.DictReader(open(gpt_path, encoding="utf-8-sig")) if r["row"]}
    print("\nChatGPT:", dict(collections.Counter(gpt.values())), "precision", precision(gpt, gpt))
    both = [n for n in human if n in gpt]
    same = lambda a, b: a == b or (a in UNSURE and b in UNSURE)
    print("agree (3 labels)", sum(same(human[n], gpt[n]) for n in both), "/", len(both))
    dec = [n for n in both if human[n] not in UNSURE and gpt[n] not in UNSURE]
    po = sum(human[n] == gpt[n] for n in dec) / len(dec)
    ph = sum(human[n] == "صحيح" for n in dec) / len(dec)
    pg = sum(gpt[n] == "صحيح" for n in dec) / len(dec)
    pe = ph * pg + (1 - ph) * (1 - pg)
    print(f"both decided {len(dec)}, agree {po:.3f}, Cohen kappa {(po - pe) / (1 - pe):.3f}")
