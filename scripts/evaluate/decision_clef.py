"""Decision-step test with Clef-Flash (open, Jev-compatible decision model), on the same cases as decision_gemma.py.

  .venv/Scripts/python scripts/evaluate/decision_clef.py [--per-class 300] [--seed 7] [--bits 4] [--limit N]
Runs the model locally, loaded in 4-bit to fit a 10 GB GPU. Asks one true/false question per case and reports accuracy,
precision and recall at 0.5, and what each probability threshold would keep, so the confidence itself can be judged.
Writes reports/decision_clef.json and reports/decision_clef.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "data" / "models" / "clef-flash"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "evaluate"))
sys.path.insert(0, str(MODEL))

import torch  # noqa: E402
from decision_gemma import REPORTS, build_cases  # noqa: E402
from joint_schema_model import collate_records, encode_record, load_release_model  # noqa: E402
from transformers import BitsAndBytesConfig  # noqa: E402

THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
QUESTION = ("هل تعني الكلمة المذكورة في هذه الجملة بالضبط هذا المصطلح، بحيث يصح استبدالها به دون تغيير المعنى؟ "
            "أجب بالنفي إذا كانت تعني في هذا السياق شيئًا آخر أو مفهومًا مختلفًا أو أعم أو أخص.")


def load(bits: int):
    kwargs = {}
    if bits == 4:
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                           bnb_4bit_compute_dtype=torch.bfloat16)
    return load_release_model(MODEL, device="cuda", **kwargs)


def ask(model, processor, state: dict, question: str = QUESTION) -> float:
    record = {"state": state, "questions": {"same": {"type": "noul", "instructions": question}}}
    encoded = encode_record(processor.tokenizer, record, processor=processor)
    batch = collate_records([encoded], processor.tokenizer.pad_token_id, torch.device("cuda"))
    with torch.inference_mode():
        logits = model(batch)[0]
    question_row = encoded.questions[0]
    probs = logits[0].float().softmax(-1).tolist()
    return dict(zip(question_row.option_ids, probs))["true"]


def state_of(case: dict) -> dict:
    sense = case["sense"]
    return {"الجملة": case["sentence"], "الكلمة": case["form"], "المصطلح": sense["term"],
            "المقابل الإنجليزي": sense["english"] or "-", "التعريف": sense["definition"] or "-",
            "المعجم": sense["dictionary"]}


def summary(results: list[dict]) -> dict:
    out = {"cases": len(results), "thresholds": []}
    for t in THRESHOLDS:
        kept = [r for r in results if r["p"] >= t]
        right = sum(r["expected"] for r in kept)
        positives = sum(r["expected"] for r in results)
        out["thresholds"].append({"threshold": t, "kept": len(kept), "precision": round(right / len(kept), 3) if kept else None,
                                  "recall": round(right / positives, 3) if positives else None,
                                  "wrong_kept": len(kept) - right})
    correct = sum((r["p"] >= 0.5) == r["expected"] for r in results)
    out["accuracy"] = round(correct / len(results), 3)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-class", type=int, default=300)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bits", type=int, choices=[4, 16], default=4)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    model, processor = load(args.bits)
    print(f"loaded; GPU memory {torch.cuda.memory_allocated() / 1e9:.1f} GB", flush=True)
    cases = build_cases(args.per_class, args.seed)
    if args.limit:
        cases = cases[: args.limit // 2] + cases[-(args.limit // 2):]
    results, start = [], time.time()
    for n, case in enumerate(cases, 1):
        results.append({"sentence": case["sentence"], "form": case["form"], "term": case["sense"]["term"],
                        "english": case["sense"]["english"], "expected": case["expected"],
                        "p": round(ask(model, processor, state_of(case)), 4)})
        if n % 50 == 0:
            print(f"  {n}/{len(cases)} ({(time.time() - start) / n:.2f} s each)", flush=True)
    result = summary(results)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "model": "Cloudflare/clef-flash", "bits": args.bits,
               "seconds_per_case": round((time.time() - start) / len(cases), 3), "summary": result, "results": results}
    (REPORTS / "decision_clef.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# Decision test — Clef-Flash ({args.bits}-bit), same cases as decision_gemma", "",
             f"{result['cases']} cases, accuracy at 0.5: {result['accuracy']}, {payload['seconds_per_case']} s per case.", "",
             "| p >= | kept | precision | recall | wrong kept |", "|---|---|---|---|---|"]
    lines += [f"| {t['threshold']} | {t['kept']} | {t['precision']} | {t['recall']} | {t['wrong_kept']} |" for t in result["thresholds"]]
    (REPORTS / "decision_clef.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
