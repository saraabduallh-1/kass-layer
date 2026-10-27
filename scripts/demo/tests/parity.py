"""Checks that the Python engine (src/kass_layer/detector) and the page (kass-lab.html) agree on every gold sentence.

Run: .venv/bin/python scripts/demo/tests/parity.py [data_dir]   (needs node)
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
from kass_layer.detector.engine import Detector  # noqa: E402

data_dir = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "demo_local")
js = json.loads(subprocess.run(["node", str(HERE / "dump_js.js"), data_dir], capture_output=True, text=True, check=True).stdout)
det = Detector(data_dir)
diffs = 0
for case in js:
    r = det.analyse(case["text"], case["domain"])
    py = {"items": [{"original": x["original"], "state": x["state"], "choices": [det.senses[c[0]][0] for c in x["choices"][:6]],
                     "reasons": x["reasons"], "notes": x["notes"]} for x in r["items"]], "unknown": r["unknown"]}
    if py["items"] != case["items"] or py["unknown"] != case["unknown"]:
        diffs += 1
        print(f"DIFF [{case['domain']}] {case['text']}\n  js: {json.dumps({k: case[k] for k in ('items', 'unknown')}, ensure_ascii=False)}\n  py: {json.dumps(py, ensure_ascii=False)}")
print(f"{len(js) - diffs}/{len(js)} sentences identical")
sys.exit(1 if diffs else 0)
