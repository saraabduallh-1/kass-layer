"""Decision-step test ("Jev" fallback): local Gemma as a yes/no judge for replacing a variant with a standard term.

Cases come from the enriched dictionaries, nothing is invented:
  positive  the example sentence written for a variant, asked about the term that variant belongs to  -> yes
  negative  the same sentence and form, asked about a different term that also lists that form
            (different English term)                                                             -> no
Gemma answers {"replace": bool, "confidence": 0..1}. The report gives accuracy, precision and recall, and for
each confidence threshold the share of cases that could be replaced automatically and how precise that would be
(auto = replace and confidence >= threshold; everything else goes to "ask the user" or "skip").

  .venv/Scripts/python scripts/evaluate/decision_gemma.py [--per-class 300] [--workers 4] [--seed 7]
Writes reports/decision_gemma.json and reports/decision_gemma.md.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.enrichment import extract_json, load_dotenv, normalize  # noqa: E402
from kass_layer.dictionary.qwen_client import QwenClient, QwenError  # noqa: E402

ENRICHED = ROOT / "data" / "dictionaries" / "enriched"
REPORTS = ROOT / "reports"
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]

PROMPT = """أنت جزء من طبقة آلية تستبدل الكلمات غير القياسية في النصوص العربية بالمصطلح القياسي من معجم متخصص.
أمامك جملة، وكلمة منها، ومصطلح قياسي مع تعريفه.
السؤال: هل تعني الكلمة في هذه الجملة بالضبط هذا المصطلح، بحيث يصح استبدالها به دون تغيير المعنى؟
أجب بـ "replace": false إذا كانت الكلمة تعني في هذا السياق شيئًا آخر أو مفهومًا مختلفًا أو أعم أو أخص.
confidence: رقم من 0 إلى 1 يعبر عن ثقتك في جوابك.
أجب بـ JSON فقط: {"replace": true, "confidence": 0.9}"""


def _sense_rows() -> list[dict]:
    rows = []
    for path in sorted(ENRICHED.glob("*.enriched.json")):
        dictionary = json.loads(path.read_text(encoding="utf-8"))
        for record in dictionary["records"]:
            rows.append({"sense_id": record["sense_id"], "dictionary": dictionary["dictionary_name"].strip(),
                         "term": record.get("term_without_diacritics") or record["term"],
                         "english": (record.get("english_term") or "").strip(),
                         "definition": " ".join((record.get("definition") or "").split())[:300],
                         "variants": (record.get("enrichment") or {}).get("variants") or []})
    return rows


def build_cases(per_class: int, seed: int) -> list[dict]:
    senses = _sense_rows()
    by_form = defaultdict(list)
    for sense in senses:
        for variant in sense["variants"]:
            by_form[normalize(variant["form"])].append(sense)
    positives, negatives = [], []
    for sense in senses:
        for variant in sense["variants"]:
            example = (variant.get("example") or "").strip()
            if not example or variant["form"] not in example:
                continue
            base = {"sentence": example, "form": variant["form"], "source_sense": sense["sense_id"]}
            positives.append({**base, "sense": sense, "expected": True})
            for other in by_form[normalize(variant["form"])]:
                if (normalize(other["term"]) != normalize(sense["term"]) and other["english"] and sense["english"]
                        and other["english"].lower() != sense["english"].lower()):
                    negatives.append({**base, "sense": other, "expected": False})
    rng = random.Random(seed)
    rng.shuffle(positives)
    rng.shuffle(negatives)
    seen, unique_negatives = set(), []
    for case in negatives:  # one negative per sentence keeps the set varied
        if case["sentence"] not in seen:
            seen.add(case["sentence"])
            unique_negatives.append(case)
    return positives[:per_class] + unique_negatives[:per_class]


def ask(client: QwenClient, case: dict) -> dict:
    sense = case["sense"]
    user = (f"الجملة: {case['sentence']}\nالكلمة: {case['form']}\nالمصطلح القياسي: {sense['term']}"
            f" ({sense['english'] or '-'})\nالتعريف: {sense['definition'] or '-'}\nالمعجم: {sense['dictionary']}")
    try:
        text, _ = client.complete([{"role": "system", "content": PROMPT}, {"role": "user", "content": user}], {})
        payload = extract_json(text)
    except (QwenError, ValueError) as error:
        return {"error": str(error)[:200]}
    if not isinstance(payload, dict) or not isinstance(payload.get("replace"), bool):
        return {"error": f"unparsed: {str(text)[:200]}"}
    try:
        confidence = min(max(float(payload.get("confidence", 0.5)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.5
    return {"replace": payload["replace"], "confidence": confidence}


def metrics(results: list[dict]) -> dict:
    answered = [r for r in results if "replace" in r]
    tp = sum(r["replace"] and r["expected"] for r in answered)
    fp = sum(r["replace"] and not r["expected"] for r in answered)
    fn = sum(not r["replace"] and r["expected"] for r in answered)
    tn = sum(not r["replace"] and not r["expected"] for r in answered)
    out = {"cases": len(results), "answered": len(answered), "errors": len(results) - len(answered),
           "tp": tp, "fp": fp, "fn": fn, "tn": tn,
           "accuracy": round((tp + tn) / len(answered), 3) if answered else None,
           "precision": round(tp / (tp + fp), 3) if tp + fp else None,
           "recall": round(tp / (tp + fn), 3) if tp + fn else None, "thresholds": []}
    for t in THRESHOLDS:
        auto = [r for r in answered if r["replace"] and r["confidence"] >= t]
        correct = sum(r["expected"] for r in auto)
        out["thresholds"].append({"threshold": t, "auto": len(auto),
                                  "auto_share": round(len(auto) / len(answered), 3) if answered else None,
                                  "auto_precision": round(correct / len(auto), 3) if auto else None,
                                  "wrong_auto_replacements": len(auto) - correct})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-class", type=int, default=300)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    load_dotenv()
    client = QwenClient(thinking=False, temperature=0.0, max_tokens=200)
    cases = build_cases(args.per_class, args.seed)
    print(f"model {client.model}; {sum(c['expected'] for c in cases)} positive, "
          f"{sum(not c['expected'] for c in cases)} negative cases", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        answers = list(pool.map(lambda c: ask(client, c), cases))
    results = [{"sentence": c["sentence"], "form": c["form"], "term": c["sense"]["term"],
                "english": c["sense"]["english"], "dictionary": c["sense"]["dictionary"],
                "expected": c["expected"], **a} for c, a in zip(cases, answers)]
    summary = metrics(results)
    REPORTS.mkdir(exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "model": client.model,
               "judge": "gemma yes/no (Jev fallback)", "summary": summary, "results": results}
    (REPORTS / "decision_gemma.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"# Decision test — {client.model} as yes/no judge (Jev fallback)", "",
             f"{summary['cases']} cases ({sum(c['expected'] for c in cases)} should replace, "
             f"{sum(not c['expected'] for c in cases)} should not: same form, different term). "
             f"Errors: {summary['errors']}.",
             "Some negatives pair a form with a near-synonymous term from another dictionary, so a few "
             "'wrong replacements' may be acceptable: check the sample below.", "",
             f"Accuracy {summary['accuracy']} · precision {summary['precision']} · recall {summary['recall']} "
             f"(tp {summary['tp']}, fp {summary['fp']}, fn {summary['fn']}, tn {summary['tn']})", "",
             "| confidence ≥ | auto-replaced | share | precision | wrong replacements |", "|---|---|---|---|---|"]
    lines += [f"| {t['threshold']} | {t['auto']} | {t['auto_share']} | {t['auto_precision']} | "
              f"{t['wrong_auto_replacements']} |" for t in summary["thresholds"]]
    wrong = [r for r in results if r.get("replace") is not None and r["replace"] != r["expected"]][:15]
    lines += ["", "## Sample of wrong answers", ""]
    lines += [f"- {'replaced' if r['replace'] else 'kept'} «{r['form']}» → {r['term']} ({r['english']}), "
              f"conf {r['confidence']}: {r['sentence']}" for r in wrong]
    (REPORTS / "decision_gemma.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]), flush=True)


if __name__ == "__main__":
    main()
