from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "reports" / "retrieval_evaluation.json"


def main() -> None:
    report = {
        "dataset_name": "seed_validation_terms",
        "counts": {"queries": 3, "relevant": 3},
        "metrics": {
            "recall_at_1": 0.0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "mrr": 0.0,
            "false_candidate_rate": 0.0,
            "latency_ms": 0,
        },
        "limitations": [
            "No official Academy source data was available from the public network in this environment.",
            "No EmbeddingGemma execution was performed because the model weights were not locally available."
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Evaluation report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
