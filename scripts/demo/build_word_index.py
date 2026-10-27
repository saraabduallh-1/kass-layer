"""Word statistics + word meaning vectors for the detector's context step.

  .venv/bin/python scripts/demo/build_word_index.py <out_dir> [--max-words 40000] [--no-vectors]

Inputs: the Wikipedia corpus (data/corpus/wikipedia/<domain>.jsonl, from scripts/corpus/fetch_wikipedia.py) and
the full definitions of every dictionary (specialist writing of each domain); "general" articles are the baseline.
Writes <out_dir>/words.json:
  {"words": [...], "domains": ["legal", ...], "dom": base64 int8 [n x 6],   how typical a word is of each domain
   "gen": [...], "gen_total": N}                                            (log-odds against general writing, x16),
                                                                           and its count in the general articles
and <out_dir>/words.txt: base64 int8 [n x 128] EmbeddingGemma vectors of each word (same space as senses.txt).
Words use the detector's context form (normalized, leading ال and و/ب/ل removed). Vectors are cached in
data/embeddings/words-cache.npz, so a rebuild only encodes new words. No model is needed when analysing.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from kass_layer.detector.engine import DOMAINS, STOP, ctx_words, normalize  # noqa: E402

CORPUS = ROOT / "data" / "corpus" / "wikipedia"
CACHE = ROOT / "data" / "embeddings" / "words-cache.npz"
DIMS = 128


def words_of(text: str) -> list[str]:
    # ctx_words returns a set; keep repeats for counting by applying it per word
    return [w for t in normalize(text).split() for w in ctx_words(t) if w not in STOP]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--max-words", type=int, default=40000)
    ap.add_argument("--no-vectors", action="store_true")
    args = ap.parse_args()
    out = Path(args.out_dir)
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    names = [normalize(n) for n in index["dictionaries"]]
    dom_of_dict = {i: [d["id"] for d in DOMAINS if any(normalize(k) in n for k in d["keys"])] for i, n in enumerate(names)}

    counts = {d["id"]: Counter() for d in DOMAINS} | {"general": Counter()}
    for name, c in counts.items():
        path = CORPUS / f"{name}.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                c.update(words_of(json.loads(line)["text"]))
    by_name = {normalize(n): i for i, n in enumerate(index["dictionaries"])}
    for path in sorted((ROOT / "data" / "dictionaries" / "enriched").glob("*.enriched.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        doms = dom_of_dict.get(by_name.get(normalize(d["dictionary_name"])), [])
        for rec in d["records"]:
            ws = words_of(f"{rec.get('term') or ''} {rec.get('definition') or ''}")
            for dom in doms:
                counts[dom].update(ws)
    for name, c in counts.items():
        print(f"  {name}: {sum(c.values()):,} words, {len(c):,} distinct")

    total = Counter()
    for c in counts.values():
        total.update(c)
    words = [w for w, n in total.most_common() if n >= 4][: args.max_words]
    doms = [d["id"] for d in DOMAINS]
    g, gN, V = counts["general"], sum(counts["general"].values()) or 1, len(total)
    dom = np.zeros((len(words), len(doms)), dtype=np.int8)
    for j, name in enumerate(doms):
        c, N = counts[name], sum(counts[name].values()) or 1
        for i, w in enumerate(words):
            lo = math.log((c[w] + 0.5) / (N + 0.5 * V)) - math.log((g[w] + 0.5) / (gN + 0.5 * V))
            dom[i, j] = int(max(-127, min(127, round(lo * 16))))
    gen = [g[w] for w in words]  # raw counts in general articles: frequent there = an ordinary word, not a term
    (out / "words.json").write_text(json.dumps({"words": words, "domains": doms, "dom": base64.b64encode(dom.tobytes()).decode(),
                                                "gen": gen, "gen_total": gN},
                                               ensure_ascii=False), encoding="utf-8")
    print(f"words.json: {len(words):,} words, {(out / 'words.json').stat().st_size / 1e6:.1f} MB")
    if args.no_vectors:
        return

    cache = dict(np.load(CACHE, allow_pickle=False)) if CACHE.exists() else {}
    cache = {k: v for k, v in zip(cache.get("words", []), cache.get("vecs", []))}
    todo = [w for w in words if w not in cache]
    if todo:
        from sentence_transformers import SentenceTransformer
        import torch
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        model = SentenceTransformer("google/embeddinggemma-300m", device=device)  # float32: float16 breaks this model
        print(f"encoding {len(todo):,} words on {device}")
        t0 = time.time()
        for i in range(0, len(todo), 2048):
            part = todo[i:i + 2048]
            vecs = model.encode_document(part, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)
            cache.update(zip(part, vecs[:, :DIMS].astype(np.float32)))
            np.savez(CACHE, words=np.array(list(cache)), vecs=np.stack(list(cache.values())))
            print(f"  {min(i + 2048, len(todo)):,}/{len(todo):,} ({time.time() - t0:.0f}s)", flush=True)
            time.sleep(3)  # let the laptop cool down
    vec = np.zeros((len(words), DIMS), dtype=np.int8)
    for i, w in enumerate(words):
        v = cache[w][:DIMS]
        vec[i] = np.clip(np.round(v / (np.linalg.norm(v) or 1) * 127), -127, 127)
    (out / "words.txt").write_text(base64.b64encode(vec.tobytes()).decode())
    print(f"words.txt: {(out / 'words.txt').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
