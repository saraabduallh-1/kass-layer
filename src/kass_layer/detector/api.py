"""HTTP API for the term detector.

Run:  .venv/bin/uvicorn kass_layer.detector.api:app --app-dir src --port 8000
Data: KASS_DATA_DIR (default demo_local/) holding index.json, context.json, senses.txt.
Docs: http://localhost:8000/docs   (KASS_SERVE_PAGE=1 also serves the demo page at /)
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .. import agreement
from .engine import DOMAINS, TYPE, Detector, replacement
from .unify import unify, with_choices

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


class AgreeReplacement(BaseModel):
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    original: str = Field(..., max_length=200, description="what the user had written there")
    term: str = Field(..., max_length=200, description="the SIWAR term as inserted in text")


class AgreeRequest(BaseModel):
    text: str = Field(..., max_length=MAX_CHARS, description="the text after the user's choices",
                      examples=["درّبنا النموذج الكبيرة على البيانات الجديدة"])
    replacements: list[AgreeReplacement] = Field(..., max_length=200,
                                                 examples=[[{"start": 7, "end": 14, "original": "المودلز", "term": "النموذج"}]])


@app.get("/agree/status")
def agree_status():
    """Whether the agreement model is configured (KASS_AGREE_URL); the page shows its button only then."""
    return {"available": agreement.configured(), "model": os.environ.get("KASS_AGREE_MODEL") or None}


@app.post("/agree")
def agree(req: AgreeRequest):
    """Fixes number and gender of the inserted terms and the words that agree with them; nothing else may change."""
    if not agreement.configured():
        raise HTTPException(503, "agreement model not configured (KASS_AGREE_URL)")
    reps = [agreement.Replacement(**r.model_dump()) for r in req.replacements]
    if any(r.end > len(req.text) or r.start >= r.end for r in reps):
        raise HTTPException(422, "replacement outside the text")
    t0 = time.perf_counter()
    out = agreement.agree(req.text, reps)
    return {**out, "ms": round((time.perf_counter() - t0) * 1000, 1)}


@app.post("/unify")
def unify_terms(req: AnalyseRequest):
    """Term consistency inside one text: forms of one concept written differently (المودل، الموديل، نموذج), each group with the
    form to keep (the SIWAR term, or for spellings outside the dictionaries the most frequent one).
    The writer decides: group["options"] are the forms they may keep (the suggested one first), and every use carries
    use["replacements"][option], the text to write at use["start"]:use["end"] (its own و/ب/ال kept). Change all uses or
    only the ones the writer picks; nothing changes unless the writer asks."""
    if req.domain not in {d["id"] for d in DOMAINS}:
        raise HTTPException(422, f"unknown domain {req.domain!r}")
    t0 = time.perf_counter()
    analysis = detector.analyse(req.text, req.domain)
    groups = with_choices(detector, unify(detector, req.text, req.domain, analysis)["groups"], analysis)
    return {"domain": req.domain, "groups": groups, "ms": round((time.perf_counter() - t0) * 1000, 1)}


# KASS_SERVE_PAGE=1 also serves the demo page and its data files from KASS_DATA_DIR at "/" (one container, no GitHub Pages)
if os.environ.get("KASS_SERVE_PAGE") == "1":
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=DATA_DIR, html=True), name="page")
