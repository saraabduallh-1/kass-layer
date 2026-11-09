"""Checks that term unification in Python (src/kass_layer/detector/unify.py) and in the page (kass-lab.html) agree, on the
unification gold sets and the real articles in logs/real_articles/ when present.

Run: .venv/Scripts/python scripts/demo/tests/parity_unify.py   (needs node)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
from kass_layer.detector.engine import Detector  # noqa: E402
from kass_layer.detector.unify import unify  # noqa: E402

cases = [{"domain": c["domain"], "text": c["text"]} for f in sorted(HERE.glob("gold-unify-*.json")) for c in json.loads(f.read_text(encoding="utf-8"))]
for f in sorted((ROOT / "logs" / "real_articles").glob("*.json")):
    cases += [{"domain": a["domain"], "text": a["text"]} for a in json.loads(f.read_text(encoding="utf-8"))]
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
    json.dump(cases, tmp, ensure_ascii=False)
js = json.loads(subprocess.run(["node", str(HERE / "dump_unify_js.js"), tmp.name], capture_output=True, text=True, encoding="utf-8", check=True).stdout)
Path(tmp.name).unlink()
det = Detector(ROOT / "demo_local")
same = 0
for c, j in zip(cases, js):
    p = unify(det, c["text"], c["domain"])["groups"]
    if json.loads(json.dumps(p, ensure_ascii=False)) == j:
        same += 1
    else:
        print("DIFF", c["text"][:60], "\n  py", [(g["keep"], [f["form"] for f in g["forms"]]) for g in p], "\n  js", [(g["keep"], [f["form"] for f in g["forms"]]) for g in j])
print(f"{same}/{len(cases)} texts identical")
