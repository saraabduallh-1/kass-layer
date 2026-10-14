from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.retrieval.embeddings import build_manifest

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "reports" / "embedding_manifest.json"


def main() -> None:
    path = build_manifest(OUT_PATH, generated_embeddings=0, failures=[
        "Model execution was not run in this environment because no public EmbeddingGemma weights were available locally."
    ])
    print(f"Embedding manifest written to {path}")


if __name__ == "__main__":
    main()
