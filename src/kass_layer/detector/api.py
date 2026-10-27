"""HTTP API for the term detector.

Run:  .venv/bin/uvicorn kass_layer.detector.api:app --app-dir src --port 8000
Data: KASS_DATA_DIR (default demo_local/) holding index.json, context.json, senses.txt.
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engine import DOMAINS, TYPE, Detector, replacement

DATA_DIR = Path(os.environ.get("KASS_DATA_DIR", Path(__file__).resolve().parents[3] / "demo_local"))
MAX_CHARS = 5000

app = FastAPI(title="Kass Layer term detector", version="1.0",
              description="Finds non-standard words in Arabic text and proposes the standard SIWAR term.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
detector = Detector(DATA_DIR)


class AnalyseRequest(BaseModel):
    text: str = Field(..., max_length=MAX_CHARS, examples=["درّبنا المودل على الداتا وبعدين سوينا داشبورد للإدارة"])
    domain: str = Field("tech", description="one of: " + ", ".join(d["id"] for d in DOMAINS))


def _choice(r, item):
    sense = detector.senses[r[0]]
    return {"term": sense[0], "replacement": replacement(sense[0], item), "dictionary": detector.dictionaries[sense[1]],
            "english": sense[2] or None, "definition": sense[3] or None, "form_type": TYPE.get(r[2], ""), "accepted": bool(r[1] & 1)}


@app.get("/health")
def health():
    return {"ok": True, "senses": len(detector.senses), "dictionaries": len(detector.dictionaries),
            "context": detector.ctx is not None, "vectors": detector.vec is not None}


@app.get("/domains")
def domains():
    return [{"id": d["id"], "label": d["label"], "dictionaries": [detector.dictionaries[i] for i in sorted(d["dicts"])]} for d in detector.domains]


@app.post("/analyse")
def analyse(req: AnalyseRequest):
    if req.domain not in {d["id"] for d in DOMAINS}:
        raise HTTPException(422, f"unknown domain {req.domain!r}")
    t0 = time.perf_counter()
    res = detector.analyse(req.text, req.domain)
    items, out, pos = [], [], 0
    for x in res["items"]:
        m = x["m"]
        best = _choice(x["best"], x)
        items.append({"original": x["original"], "start": m["s"], "end": m["e"], "state": x["state"],
                      "suggestion": None if x["state"] == "std" else best,
                      "choices": [] if x["state"] == "std" else [_choice(r, x) for r in x["choices"][:6]],
                      "match": m["how"], "reasons": x["reasons"], "notes": x["notes"]})
        # suggested text: only confident replacements; "review" items stay as written for a person to decide
        out.append(req.text[pos:m["s"]] + (best["replacement"] if x["state"] == "replace" else x["original"]))
        pos = m["e"]
    out.append(req.text[pos:])
    ranked, total = res["ranked"], res["total"]
    return {
        "domain": req.domain,
        "nearest_dictionaries": [{"name": detector.dictionaries[d], "share": round(s / total, 3)} for d, s in ranked[:3]],
        "words": len(res["tokens"]),
        "counts": {s: sum(1 for i in items if i["state"] == s) for s in ("replace", "review", "std")},
        "items": items,
        "unknown": res["unknown"],
        "suggested_text": "".join(out),
        "ms": round((time.perf_counter() - t0) * 1000, 1),
    }
