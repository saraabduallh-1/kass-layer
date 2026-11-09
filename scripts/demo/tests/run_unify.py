"""Scores term unification (src/kass_layer/detector/unify.py) on gold-unify-*.json: pairs of forms that should be merged.

Run: .venv/Scripts/python scripts/demo/tests/run_unify.py [gold file ...] [-v]
"""
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "src"))
from kass_layer.detector.engine import Detector  # noqa: E402
from kass_layer.detector.unify import form_key, unify  # noqa: E402

verbose = "-v" in sys.argv
files = [a for a in sys.argv[1:] if a != "-v"] or sorted(str(p) for p in HERE.glob("gold-unify-*.json"))
det = Detector(HERE.parents[2] / "demo_local")


def pairs(groups):
    return {frozenset(p) for g in groups for p in itertools.combinations(sorted({form_key(f) for f in g}), 2)}


for f in files:
    gold = json.loads(Path(f).read_text(encoding="utf-8"))
    tp = fp = fn = 0
    for case in gold:
        got = [[x["form"] for x in g["forms"]] for g in unify(det, case["text"], case["domain"])["groups"]]
        want, have = pairs(case["groups"]), pairs(got)
        tp, fp, fn = tp + len(want & have), fp + len(have - want), fn + len(want - have)
        if verbose and want != have:
            print("  ", case["text"], "\n     want", case["groups"], "\n     got ", got)
    p = tp / (tp + fp) if tp + fp else 1
    r = tp / (tp + fn) if tp + fn else 1
    print(f"{Path(f).name}: cases {len(gold)} | pairs right {tp} wrong {fp} missed {fn} | precision {p:.1%} | recall {r:.1%}")
