"""Pack EmbeddingGemma term vectors into a small binary for the demo: 128 dims (Matryoshka cut), int8.

  .venv/bin/python scripts/demo/build_vectors_index.py <out_dir>
Reads data/embeddings/embeddinggemma-300m/ (kind=term rows) and writes <out_dir>/senses.vec: one 128-byte row per
sense, in index.json order (matched by sense_id). Used only to rank candidate terms by closeness to the standard
terms already found in the text — no model runs when analysing. Senses without a vector get zeros.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EMB = ROOT / "data" / "embeddings" / "embeddinggemma-300m"
DIMS = 128


def main(out_dir: str) -> None:
    items = [json.loads(line) for line in (EMB / "items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    vectors = np.load(EMB / "vectors.npy").astype(np.float32)
    by_sense = {item["sense_id"]: vectors[i] for i, item in enumerate(items) if item["kind"] == "term"}
    order = []
    for path in sorted((ROOT / "data" / "dictionaries" / "enriched").glob("*.enriched.json")):
        order += [record["sense_id"] for record in json.loads(path.read_text(encoding="utf-8"))["records"]]
    out = np.zeros((len(order), DIMS), dtype=np.int8)
    found = 0
    for row, sense_id in enumerate(order):
        v = by_sense.get(sense_id)
        if v is None:
            continue
        v = v[:DIMS]
        v = v / (np.linalg.norm(v) or 1)
        out[row] = np.clip(np.round(v * 127), -127, 127).astype(np.int8)
        found += 1
    path = Path(out_dir) / "senses.vec"
    path.write_bytes(out.tobytes())
    print(f"{found}/{len(order)} senses with vectors, {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
