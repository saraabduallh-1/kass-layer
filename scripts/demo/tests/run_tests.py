"""Gold-set scores for the Python engine (same rules as run_tests.js).

Run: .venv/bin/python scripts/demo/tests/run_tests.py [gold files...] [-v]
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "src"))
from kass_layer.detector.engine import Detector, normalize  # noqa: E402

key = lambda t: " ".join(w[2:] if w.startswith("ال") and len(w) > 3 else w for w in normalize(t).split())
det = Detector(HERE.parents[2] / "demo_local")
files = [a for a in sys.argv[1:] if a != "-v"] or sorted(p.name for p in HERE.glob("gold*.json"))
for f in files:
    tp = fn = fp = wrong = 0
    notes = []
    gold = json.loads((HERE / f).read_text(encoding="utf-8"))
    for g in gold:
        found = [x for x in det.analyse(g["text"], g["domain"])["items"] if x["state"] != "std"]
        used = set()
        for surface, term in (g.get("expect") or {}).items():
            it = next((x for x in found if x["original"] == surface), None)
            if not it:
                fn += 1; notes.append(f"  MISS  [{g['domain']}] {surface} → {term}"); continue
            used.add(id(it))
            got = det.senses[it["choices"][0][0]][0]
            if any(key(got) == key(t) for t in term.split("|")):
                tp += 1
            else:
                wrong += 1; notes.append(f"  WRONG [{g['domain']}] {surface} → {got} (want {term})")
        for it in found:
            if id(it) not in used:
                fp += 1; notes.append(f"  EXTRA [{g['domain']}] {it['original']} → {det.senses[it['best'][0]][0]} ({it['state']})")
    P, R = tp / max(1, tp + wrong + fp), tp / max(1, tp + fn + wrong)
    print(f"{f:26} cases {len(gold)} | correct {tp} | missed {fn} | wrong {wrong} | extra {fp} | recall {100 * R:.1f}% | precision {100 * P:.1f}%")
    if "-v" in sys.argv:
        print("\n".join(notes))
