"""Turn the enriched dictionaries into EmbeddingGemma vectors, and search them.

  .venv/bin/python scripts/embeddings/build_embeddings.py build [--dictionary ID] [--limit N] [--batch 32] [--cool 5]
  .venv/bin/python scripts/embeddings/build_embeddings.py search "المودل تدرب على بيانات العملاء" [-k 10]
  .venv/bin/python scripts/embeddings/build_embeddings.py status

What gets embedded (from data/dictionaries/enriched/*.enriched.json, never the original files):
  kind=term     the standard term plus its definition, one per sense   ("نموذج: تمثيل رياضي ...")
  kind=variant  every reviewed variant on its own, linked to its sense ("مودل", "model")
Both are encoded as *documents*; text from a user's sentence is encoded as a *query*. EmbeddingGemma
adds a different task prefix to each, which is why queries and documents use different encode calls.

Output (data/embeddings/embeddinggemma-300m/):
  vectors.npy   float16 matrix, one L2-normalised row per item (cosine similarity = dot product)
  items.jsonl   one line per row: id, kind, text, sense_id, dictionary_id, term, variant status, sha256
A text whose sha256 (model + kind + text) is unchanged is never re-encoded, so adding new variants later
only encodes the new ones.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ENRICHED_DIR = ROOT / "data" / "dictionaries" / "enriched"
MODEL_ID = "google/embeddinggemma-300m"
OUT_DIR = ROOT / "data" / "embeddings" / "embeddinggemma-300m"
VECTORS = OUT_DIR / "vectors.npy"
ITEMS = OUT_DIR / "items.jsonl"
DEFINITION_CHARS = 300  # enough context to tell senses apart; keeps every text well under the model's limit


# ----------------------------------------------------------------------------- step 1: collect the texts
def collect_items(dictionary_prefix: str | None = None) -> list[dict]:
    """One item per standard-term sense and one per variant, read from the enriched files."""
    items = []
    for path in sorted(ENRICHED_DIR.glob("*.enriched.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if dictionary_prefix and not data["dictionary_id"].startswith(dictionary_prefix):
            continue
        for record in data["records"]:
            term = record.get("term_without_diacritics") or record["term"]
            definition = " ".join((record.get("definition") or "").split())[:DEFINITION_CHARS]
            base = {"sense_id": record["sense_id"], "dictionary_id": data["dictionary_id"], "term": term}
            items.append({**base, "kind": "term", "text": f"{term}: {definition}" if definition else term})
            for variant in (record.get("enrichment") or {}).get("variants") or []:
                items.append({**base, "kind": "variant", "text": variant["form"],
                              "variant_type": variant.get("type"), "status": variant.get("status")})
    for item in items:
        # step 2: the fingerprint that decides whether a text needs (re-)encoding
        item["sha256"] = hashlib.sha256(f"{MODEL_ID}|{item['kind']}|{item['text']}".encode()).hexdigest()
        item["id"] = f"{item['sense_id']}|{item['kind']}|{item['text']}"
    return items


CACHE_DIR = OUT_DIR / "cache"
CHECKPOINT = 2048  # texts per saved part


def save_checkpoint(items: list[dict], vectors: np.ndarray) -> None:
    """Save one part (fingerprints + vectors) so an interrupted build never loses finished work."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    name = CACHE_DIR / f"part-{time.time_ns()}.npz"
    np.savez(name, sha256=np.array([item["sha256"] for item in items]), vectors=vectors.astype(np.float16))


def load_cache() -> dict[str, np.ndarray]:
    cached = {}
    for path in sorted(CACHE_DIR.glob("part-*.npz")) if CACHE_DIR.exists() else []:
        data = np.load(path)
        cached.update(zip(data["sha256"].tolist(), data["vectors"]))
    return cached


def load_existing() -> tuple[list[dict], np.ndarray | None]:
    if not (ITEMS.exists() and VECTORS.exists()):
        return [], None
    items = [json.loads(line) for line in ITEMS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return items, np.load(VECTORS)


def load_model():
    from sentence_transformers import SentenceTransformer
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    # float32 on purpose: EmbeddingGemma's activations do not support float16 (results would be wrong)
    return SentenceTransformer(MODEL_ID, device=device), device


# ----------------------------------------------------------------------------- step 3+4: encode and save
def cmd_build(args) -> None:
    items = collect_items(args.dictionary)
    if args.limit:
        items = items[: args.limit]
    cached = load_cache()
    old_items, old_vectors = load_existing()
    if old_vectors is not None:
        cached.update({item["sha256"]: old_vectors[i] for i, item in enumerate(old_items)})
    todo = list({item["sha256"]: item for item in items if item["sha256"] not in cached}.values())
    print(f"[1] collected {len(items)} texts: "
          f"{sum(i['kind'] == 'term' for i in items)} terms, {sum(i['kind'] == 'variant' for i in items)} variants")
    unique = len({item["sha256"] for item in items})
    print(f"[2] {unique} unique texts ({len(items) - unique} repeated across terms); "
          f"{unique - len(todo)} already encoded, {len(todo)} to encode")

    if todo:
        model, device = load_model()
        print(f"[3] model {MODEL_ID} loaded on {device}; batches of {args.batch}, "
              f"saving every {CHECKPOINT} texts, {args.cool}s cool-down between parts")
        start = time.time()
        # longest texts first: batches of similar length waste less padding and finish sooner
        todo.sort(key=lambda item: len(item["text"]), reverse=True)
        for offset in range(0, len(todo), CHECKPOINT):
            part = todo[offset: offset + CHECKPOINT]
            vectors = model.encode_document([item["text"] for item in part], batch_size=args.batch,
                                            normalize_embeddings=True, convert_to_numpy=True)
            save_checkpoint(part, vectors)  # an interrupted run resumes from here
            cached.update({item["sha256"]: vector for item, vector in zip(part, vectors)})
            done = offset + len(part)
            elapsed = time.time() - start
            eta = elapsed / done * (len(todo) - done)
            print(f"    {done}/{len(todo)} encoded ({done / elapsed:.0f} texts/s, ~{eta / 60:.0f} min left)", flush=True)
            if args.cool and done < len(todo):
                time.sleep(args.cool)  # let the GPU cool down a little
        elapsed = time.time() - start
        print(f"    encoded {len(todo)} texts in {elapsed / 60:.1f} min")

    matrix = np.stack([cached[item["sha256"]] for item in items]).astype(np.float16)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(VECTORS, matrix)
    with ITEMS.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"[4] saved {matrix.shape[0]} vectors x {matrix.shape[1]} dims -> {VECTORS.relative_to(ROOT)} "
          f"({VECTORS.stat().st_size / 1e6:.0f} MB) and {ITEMS.relative_to(ROOT)}")


# ----------------------------------------------------------------------------- step 5: try it
def cmd_search(args) -> None:
    items, vectors = load_existing()
    if vectors is None:
        raise SystemExit("No vectors yet: run `build` first.")
    model, _ = load_model()
    query = model.encode_query(args.text, normalize_embeddings=True, convert_to_numpy=True)
    scores = vectors.astype(np.float32) @ query  # cosine similarity, because every row is normalised
    best_by_sense: dict[str, tuple[float, dict]] = {}
    for index in np.argsort(-scores)[: args.k * 10]:
        item = items[index]
        if item["sense_id"] not in best_by_sense:
            best_by_sense[item["sense_id"]] = (float(scores[index]), item)
    print(f"query: {args.text}")
    for score, item in list(best_by_sense.values())[: args.k]:
        via = f"  (matched variant «{item['text']}»)" if item["kind"] == "variant" else ""
        print(f"  {score:.3f}  {item['term']}{via}")


def cmd_status(args) -> None:
    items, vectors = load_existing()
    current = collect_items()
    done = {item["sha256"] for item in items}
    missing = sum(item["sha256"] not in done for item in current)
    print(f"stored: {len(items)} vectors; current texts: {len(current)}; not yet encoded: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--dictionary", help="dictionary id prefix (default: all)")
    build.add_argument("--limit", type=int, help="first N texts only, for a trial run")
    build.add_argument("--batch", type=int, default=32)
    build.add_argument("--cool", type=float, default=5, help="seconds of pause between saved parts")
    build.set_defaults(handler=cmd_build)
    search = commands.add_parser("search")
    search.add_argument("text")
    search.add_argument("-k", type=int, default=10)
    search.set_defaults(handler=cmd_search)
    commands.add_parser("status").set_defaults(handler=cmd_status)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
