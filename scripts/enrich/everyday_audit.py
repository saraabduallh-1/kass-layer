"""Usage check of the everyday pairs: does an ordinary Arabic word (عوائد) really carry its term's meaning (ريع)
in real sentences of the term's own field?

For each pair the detector treats as an everyday word (an Arabic form whose words are all common), up to six
sentences that contain the form are taken from the Arabic Wikipedia corpus of the term's domain
(data/corpus/wikipedia/<domain>.jsonl). Gemma says for each sentence whether the word means the term there.
Pairs where it rarely does are then reviewed by Claude and withdrawn with topic_pass.py --audit.

  .venv/Scripts/python scripts/enrich/everyday_audit.py count             # pairs and their corpus frequency
  .venv/Scripts/python scripts/enrich/everyday_audit.py run [--min-freq 3] [--limit N] [--model gemma3:12b]
  .venv/Scripts/python scripts/enrich/everyday_audit.py show [--max-ratio 0.34]

Output (append-only, resumable): data/dictionaries/enriched/variants/raw/everyday_usage.jsonl
"""
import argparse
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from kass_layer.detector.engine import ARABIC_WORD, STOP, Detector, bare, normalize  # noqa: E402

OUT = ROOT / "data" / "dictionaries" / "enriched" / "variants" / "raw" / "everyday_usage.jsonl"
FREQ = ROOT / "logs" / "everyday_freq.json"
CORPUS = ROOT / "data" / "corpus" / "wikipedia"
PROMPT_VERSION = 2


def everyday_pairs(d):
    """(form, sense) pairs the detector handles as everyday words (same test as find_matches)."""
    out = []
    for f, rows in d.forms.items():
        ws = f.split(" ")
        if not all(ARABIC_WORD.search(w) for w in ws):
            continue
        if any(r[1] & 4 for r in rows) or any(re.search("[tfac]", r[2]) for r in rows):
            continue
        if not all(w in STOP or d.vocab.get(bare(w), 0) >= d.EVERYDAY_VOCAB for w in ws) or all(w in STOP for w in ws):
            continue
        out.extend((f, r[0]) for r in rows)
    return out


def sentences(domain):
    out = []
    for line in open(CORPUS / f"{domain}.jsonl", encoding="utf-8"):
        for s in re.split(r"(?<=[.!؟?\n])\s+", json.loads(line)["text"]):
            s = " ".join(s.split())
            if 6 <= len(s.split()) <= 60:
                out.append((normalize(s), s))
    return out


def form_re(form):
    ws = form.split(" ")
    w = ws[0]
    # «الغير» needs its article (غير alone is the negation); «محاسبه» may take one (المحاسبه، والمحاسبه)
    first = (r"(?:[وفبك]?ال|لل)" + re.escape(w[2:])) if w.startswith("ال") and len(w) > 4 else (r"(?:[وفبلك]?(?:ال)?|لل)?" + re.escape(w))
    return re.compile(r"(?:^| )" + " ".join([first] + [re.escape(w) for w in ws[1:]]) + r"(?: |$)")


def domain_of(d, sense):
    return next((dm["id"] for dm in d.domains if d.senses[sense][1] in dm["dicts"]), None)


def count(d):
    corp = {}
    res = []
    for f, s in everyday_pairs(d):
        dom = domain_of(d, s)
        if dom is None:
            continue
        if dom not in corp:
            corp[dom] = sentences(dom)
        rx = form_re(f)
        hits = [orig for norm, orig in corp[dom] if rx.search(norm)]
        res.append({"form": f, "sense": s, "domain": dom, "freq": len(hits), "examples": hits[:6]})
    FREQ.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def ask(model, term, definition, form, examples):
    lines = "\n".join(f"{i}. {s}" for i, s in enumerate(examples, 1))
    prompt = (f"المصطلح: {term}\nتعريفه: {definition or '—'}\n\n"
              f"في كل جملة مما يلي، هل جاءت «{form}» بمعنى هذا المصطلح تحديدًا، لا بمعناها العام؟ "
              "إذا دلت على مفهوم قريب منه أو أعم أو أخص (مثل الروبوتات مقابل علم الروبوتات) فالجواب لا.\n"
              f"{lines}\n\n"
              'أجب بصيغة JSON فقط: {"1": "نعم" أو "لا", "2": ...}')
    r = requests.post("http://localhost:11434/api/generate", timeout=300, json={
        "model": model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0}})
    ans = json.loads(r.json()["response"])
    return [str(ans.get(str(i), "")).strip().startswith("نعم") for i in range(1, len(examples) + 1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["count", "run", "show"])
    ap.add_argument("--min-freq", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="gemma3:12b")
    ap.add_argument("--max-ratio", type=float, default=0.34)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    d = Detector(ROOT / "demo_local")
    if a.cmd == "count":
        res = count(d)
        for th in (1, 3, 10, 30):
            print(f"pairs with {th}+ sentences in their field: {sum(r['freq'] >= th for r in res)}")
        return
    done = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[(r["form"], r["term"], r["dictionary"])] = r
    if a.cmd == "show":
        rows = [r for r in done.values() if r["ratio"] <= a.max_ratio]
        rows.sort(key=lambda r: (r["dictionary"], -r["freq"]))
        for r in rows:
            print(f"{r['dictionary'][:30]}\t{r['term']}\t!{r['form']}\t{r['yes']}/{r['n']}\tfreq {r['freq']}\t| {r['examples'][0][:90]}")
        print(len(rows), "of", len(done))
        return
    res = json.loads(FREQ.read_text(encoding="utf-8"))
    todo = sorted((r for r in res if r["freq"] >= a.min_freq), key=lambda r: -r["freq"])
    n = 0
    with OUT.open("a", encoding="utf-8") as out:
        for r in todo:
            term, dic, _, definition = d.senses[r["sense"]][:4]
            key = (r["form"], term, d.dictionaries[dic])
            if key in done:
                continue
            try:
                votes = ask(a.model, term, definition, r["form"], r["examples"])
            except Exception as e:  # a bad answer: skip, it is retried on the next run
                print("skip", r["form"], e, flush=True)
                continue
            row = {"form": r["form"], "term": term, "dictionary": d.dictionaries[dic], "domain": r["domain"],
                   "freq": r["freq"], "n": len(votes), "yes": sum(votes), "ratio": sum(votes) / max(1, len(votes)),
                   "votes": votes, "examples": r["examples"], "model": a.model, "prompt_version": PROMPT_VERSION}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            done[key] = row
            n += 1
            if n % 25 == 0:
                print(n, "done", flush=True)
            if a.limit and n >= a.limit:
                break
    print(n, "new pairs judged")


if __name__ == "__main__":
    main()
