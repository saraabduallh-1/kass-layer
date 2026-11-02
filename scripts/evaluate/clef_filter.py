"""Gold-set scores of the detector with and without the two context rules, and with and without Clef-Flash as a filter.

  .venv/Scripts/python scripts/evaluate/clef_filter.py
Every suggestion is asked to Clef-Flash once (cached in reports/clef_filter_cache.json). The threshold is chosen on the
tuning sets only (best precision whose recall loss is at most one correct suggestion per 20), then reported on all sets.
Scoring follows scripts/demo/tests/run_tests.py. Writes reports/clef_filter.md.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "evaluate"))

from decision_clef import ask, load  # noqa: E402
from kass_layer.detector.engine import Detector, normalize  # noqa: E402

TESTS = ROOT / "scripts" / "demo" / "tests"
ARTICLES = ROOT / "reports" / "articles"
TUNING = ["gold-tuning.json", "gold-ambiguity.json", "gold-arabic-tuning.json"]
HELDOUT = ["gold-heldout-1.json", "gold-heldout-2.json", "gold-arabic-heldout.json"]
ALL = [TESTS / f for f in TUNING + HELDOUT] + [ARTICLES / "gold-written.json", ARTICLES / "gold-wiki.json"]
THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
CACHE = ROOT / "reports" / "clef_filter_cache.json"
key = lambda t: " ".join(w[2:] if w.startswith("ال") and len(w) > 3 else w for w in normalize(t).split())


def sentence_at(text: str, start: int, end: int) -> str:
    left = max(text.rfind(c, 0, start) for c in ".؟!\n") + 1
    rights = [i for i in (text.find(c, end) for c in ".؟!\n") if i >= 0]
    return text[left:min(rights) + 1 if rights else len(text)].strip()


def collect(det: Detector) -> dict[str, list[dict]]:
    """Per gold file: per case, the detector's suggestions as plain rows."""
    out = {}
    for path in ALL:
        cases = []
        for g in json.loads(path.read_text(encoding="utf-8")):
            rows = []
            for it in det.analyse(g["text"], g["domain"])["items"]:
                if it["state"] == "std":
                    continue
                sense = det.senses[it["choices"][0][0]]
                rows.append({"original": it["original"], "term": sense[0], "english": sense[2] or "-", "definition": sense[3] or "-",
                             "dictionary": str(sense[1]), "sentence": sentence_at(g["text"], it["m"]["s"], it["m"]["e"])})
            cases.append({"expect": g.get("expect") or {}, "domain": g["domain"], "rows": rows})
        out[path.name] = cases
    return out


def score(cases: list[dict], cache: dict, threshold: float) -> dict:
    tp = fn = fp = wrong = 0
    for case in cases:
        found = [r for r in case["rows"] if threshold == 0 or cache[cache_key(r)] >= threshold]
        used = set()
        for surface, term in case["expect"].items():
            row = next((r for r in found if r["original"] == surface), None)
            if row is None:
                fn += 1
                continue
            used.add(id(row))
            if any(key(row["term"]) == key(t) for t in term.split("|")):
                tp += 1
            else:
                wrong += 1
        fp += sum(id(r) not in used for r in found)
    return {"tp": tp, "fn": fn, "wrong": wrong, "fp": fp, "recall": 100 * tp / max(1, tp + fn + wrong),
            "precision": 100 * tp / max(1, tp + wrong + fp)}


def cache_key(row: dict) -> str:
    return "\t".join((row["sentence"], row["original"], row["term"]))


def total(results: dict, names: list[str], cache: dict, threshold: float) -> dict:
    parts = [score(results[n], cache, threshold) for n in names]
    tp, fn, wrong, fp = (sum(p[k] for p in parts) for k in ("tp", "fn", "wrong", "fp"))
    return {"tp": tp, "recall": 100 * tp / max(1, tp + fn + wrong), "precision": 100 * tp / max(1, tp + wrong + fp)}


def main() -> None:
    det = Detector(ROOT / "demo_local")
    with_rules = collect(det)
    det.EVERYDAY_COMMON, det.EVERYDAY_STRONG = 1e9, -9.0
    without_rules = collect(det)
    configs = {"with the two rules": with_rules, "without the rules": without_rules}

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    todo = {cache_key(r): r for results in configs.values() for cases in results.values() for c in cases for r in c["rows"]}
    todo = {k: r for k, r in todo.items() if k not in cache}
    print(f"{len(todo)} suggestions to ask", flush=True)
    if todo:
        model, processor = load(4)
        for n, (k, r) in enumerate(todo.items(), 1):
            state = {"الجملة": r["sentence"], "الكلمة": r["original"], "المصطلح": r["term"], "المقابل الإنجليزي": r["english"],
                     "التعريف": re.sub(r"\s+", " ", r["definition"])[:300]}
            cache[k] = round(ask(model, processor, state), 4)
            if n % 50 == 0:
                print(f"  {n}/{len(todo)}", flush=True)
                CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    lines = ["# Detector with and without the context rules, with and without Clef-Flash", ""]
    tuning = TUNING
    for name, results in configs.items():
        base = total(results, tuning, cache, 0)
        candidates = [t for t in THRESHOLDS if total(results, tuning, cache, t)["tp"] >= base["tp"] * 0.95]
        best = max(candidates, key=lambda t: total(results, tuning, cache, t)["precision"])
        lines += [f"## {name}: threshold chosen on the tuning sets = {best}", "",
                  "| gold set | no filter R/P | Clef filter R/P | extra no filter | extra filter |", "|---|---|---|---|---|"]
        for path in ALL:
            a, b = score(results[path.name], cache, 0), score(results[path.name], cache, best)
            lines.append(f"| {path.stem} | {a['recall']:.1f} / {a['precision']:.1f} | {b['recall']:.1f} / {b['precision']:.1f} | {a['fp']} | {b['fp']} |")
        lines.append("")
    (ROOT / "reports" / "clef_filter.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
