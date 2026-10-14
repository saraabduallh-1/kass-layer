from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EmbeddingGemmaConfig:
    model_id: str = "google/embeddinggemma-300m"
    version: str = "2025-10"
    dimensions: int = 768
    retrieval_format: str = "query|passage"
    notes: str = "Use the Google EmbeddingGemma release intended for retrieval; execution is gated by model availability in the target environment."
    status: str = "not_executed"


@dataclass
class EmbeddingManifest:
    model: EmbeddingGemmaConfig
    generated_embeddings: int = 0
    processing_stats: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model.model_id,
            "version": self.model.version,
            "dimensions": self.model.dimensions,
            "retrieval_format": self.model.retrieval_format,
            "status": self.model.status,
            "generated_embeddings": self.generated_embeddings,
            "processing_stats": self.processing_stats,
            "failures": self.failures,
        }


def build_manifest(path: str | Path, generated_embeddings: int = 0, failures: list[str] | None = None) -> Path:
    manifest = EmbeddingManifest(
        model=EmbeddingGemmaConfig(),
        generated_embeddings=generated_embeddings,
        processing_stats={"entries_seen": generated_embeddings, "batch_count": 0, "cache_hits": 0},
        failures=failures or [],
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(__import__("json").dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return target
