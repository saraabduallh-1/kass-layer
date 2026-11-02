"""Pass 3 audit of weak everyday -> term pairs: Gemma gives a first yes/no, Claude reviews only the "no" answers.

  .venv/Scripts/python scripts/enrich/audit_pairs.py run <dictionary> [--limit 300] [--workers 2]
      Judges pairs not judged yet, append-only in variants/raw/audit/<id>.jsonl. Picks the model from free GPU memory
      (gemma3:12b, else gemma3:4b); below 4 GB it exits without loading anything, so another job keeps the GPU.
  .venv/Scripts/python scripts/enrich/audit_pairs.py show <dictionary> [--limit 40]
      Prints the next rejected pairs not reviewed yet: <term> TAB <form> | relation | english | definition.
  .venv/Scripts/python scripts/enrich/audit_pairs.py done <dictionary> <decisions.txt>
      Marks the shown pairs reviewed. decisions.txt is the topic_pass.py --audit file (<term> TAB !form), applied
      separately; pairs absent from it were kept.
  .venv/Scripts/python scripts/enrich/audit_pairs.py status

A pair is an Arabic-script informal_synonym or colloquial variant. A pair is dropped only when it NEVER has the term's
meaning: «الحضور» is a fine form of المواظبة even though «بحضور المحامي» is not. Nothing here changes the dictionaries.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.enrichment import (  # noqa: E402
    OUT_DIR,
    append_jsonl,
    complete_dictionaries,
    current_generations,
    current_reviews,
    extract_json,
    load_dotenv,
    normalize,
    read_jsonl,
)
from kass_layer.dictionary.qwen_client import QwenClient, QwenError  # noqa: E402

AUDIT_DIR = OUT_DIR / "raw" / "audit"
WEAK_TYPES = {"informal_synonym", "colloquial"}
RELATIONS = {"exact", "broader", "narrower", "related", "wrong"}
ARABIC = re.compile(r"[؀-ۿ]")
PROMPT_VERSION = 2  # 1 asked "never the same meaning" and let nearly everything through
PROMPT = """أنت مدقق مصطلحات صارم. أمامك مصطلح قياسي من معجم متخصص وتعريفه، وكلمة يومية يُفترض أن الكتّاب يستعملونها بدلًا منه.
صنّف علاقة الكلمة بالمصطلح:
- exact: تعني المفهوم نفسه، ويصح استبدالها بالمصطلح في نص عن هذا المجال دون تغيير المعنى.
- broader: أعم من المصطلح.
- narrower: أخص من المصطلح.
- related: مفهوم مرتبط لكنه ليس المصطلح نفسه.
- wrong: معنى آخر أو صيغة غير مستعملة.
أجب بـ JSON فقط: {"relation": "exact", "reason": "سبب قصير"}"""


def _dictionary(prefix: str) -> dict:
    for dictionary in complete_dictionaries():
        if dictionary["dictionary_id"].startswith(prefix):
            return dictionary
    raise SystemExit(f"No completed dictionary {prefix}")


def _path(dictionary: dict) -> Path:
    return AUDIT_DIR / f"{dictionary['dictionary_id']}.jsonl"


def pairs(dictionary: dict) -> list[dict]:
    reviews = current_reviews(dictionary, current_generations(dictionary))
    out = []
    for record in dictionary["records"]:
        review = reviews.get(record["sense_id"]) or {}
        added = {normalize(f) for f in review.get("topic_pass_added") or []}  # reviewed by hand in the topic pass
        for variant in review.get("variants") or []:
            if (variant.get("type") in WEAK_TYPES and ARABIC.search(variant["form"])
                    and normalize(variant["form"]) not in added):
                out.append({"sense_id": record["sense_id"], "form": variant["form"],
                            "term": record.get("term_without_diacritics") or record["term"],
                            "english": record.get("english_term") or "",
                            "definition": " ".join((record.get("definition") or "").split())[:300]})
    return out


def _rows(dictionary: dict) -> list[dict]:
    path = _path(dictionary)
    return read_jsonl(path) if path.exists() else []


def pick_model() -> str | None:
    loaded = requests.get("http://localhost:11434/api/ps", timeout=10).json().get("models") or []
    for model in ("gemma3:12b", "gemma3:4b"):  # already in memory (its GPU use is not a reason to wait)
        if any(m.get("name") == model for m in loaded):
            return model
    free = int(subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, check=True).stdout.split()[0])
    return "gemma3:12b" if free >= 9500 else "gemma3:4b" if free >= 4000 else None


def judge(client: QwenClient, pair: dict) -> dict:
    user = (f"المصطلح: {pair['term']} ({pair['english'] or '-'})\nالتعريف: {pair['definition'] or '-'}\n"
            f"الكلمة اليومية: {pair['form']}")
    text, _ = client.complete([{"role": "system", "content": PROMPT}, {"role": "user", "content": user}], {})
    payload = extract_json(text)
    if not isinstance(payload, dict) or payload.get("relation") not in RELATIONS:
        raise ValueError(f"unparsed: {text[:100]}")
    return {**pair, "same_meaning": payload["relation"] == "exact", "relation": payload["relation"],
            "reason": str(payload.get("reason") or "")[:200], "model": client.model, "prompt": PROMPT_VERSION}


def cmd_run(args) -> None:
    model = pick_model()
    if model is None:
        raise SystemExit("under 4 GB of GPU memory free: nothing loaded, try later")
    load_dotenv()
    dictionary = _dictionary(args.dictionary)
    done = {(r["sense_id"], r["form"]) for r in _rows(dictionary) if r.get("prompt") == PROMPT_VERSION}
    work = [p for p in pairs(dictionary) if (p["sense_id"], p["form"]) not in done][: args.limit]
    client = QwenClient(model=model, thinking=False, temperature=0.0, max_tokens=300)

    def safe(pair):
        try:
            return judge(client, pair)
        except (QwenError, ValueError) as error:
            print(f"  failed {pair['form']}: {str(error)[:100]}", flush=True)
            return None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = [r for r in pool.map(safe, work) if r]
    append_jsonl(_path(dictionary), rows)
    print(f"{model}: judged {len(rows)}/{len(work)}, rejected {sum(not r['same_meaning'] for r in rows)}")


def _unreviewed(dictionary: dict) -> list[dict]:
    rows = _rows(dictionary)
    reviewed = {(r["sense_id"], r["form"]) for r in rows if r.get("reviewed")}
    return [r for r in rows if r.get("same_meaning") is False and (r["sense_id"], r["form"]) not in reviewed]


def cmd_show(args) -> None:
    dictionary = _dictionary(args.dictionary)
    rejected = _unreviewed(dictionary)
    selection = rejected[: args.limit]
    (AUDIT_DIR / f"selection-{dictionary['dictionary_id']}.json").write_text(
        json.dumps([[r["sense_id"], r["form"]] for r in selection], ensure_ascii=False), encoding="utf-8")
    print(f"# {len(rejected)} rejected pairs to review, showing {len(selection)}")
    for r in selection:
        print(f"{r['term']}\t{r['form']} | {r['english']} | {r['definition'][:120]}")


def cmd_done(args) -> None:
    dictionary = _dictionary(args.dictionary)
    selection = json.loads((AUDIT_DIR / f"selection-{dictionary['dictionary_id']}.json").read_text(encoding="utf-8"))
    append_jsonl(_path(dictionary), [{"sense_id": s, "form": f, "reviewed": True, "decisions": Path(args.decisions).name}
                                     for s, f in selection])
    print(f"{len(selection)} pairs marked reviewed, {len(_unreviewed(dictionary))} left to review")


def cmd_status(args) -> None:
    for dictionary in complete_dictionaries():
        total = len(pairs(dictionary))
        rows = _rows(dictionary)
        judged = sum(r.get("prompt") == PROMPT_VERSION for r in rows)
        print(f"{judged:>6}/{total:<6} judged, {len(_unreviewed(dictionary)):>5} to review  "
              f"{dictionary['dictionary_id'][:8]}  {dictionary['dictionary_name'].strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("dictionary")
    run.add_argument("--limit", type=int, default=300)
    run.add_argument("--workers", type=int, default=2)
    run.set_defaults(handler=cmd_run)
    show = commands.add_parser("show")
    show.add_argument("dictionary")
    show.add_argument("--limit", type=int, default=40)
    show.set_defaults(handler=cmd_show)
    done = commands.add_parser("done")
    done.add_argument("dictionary")
    done.add_argument("decisions")
    done.set_defaults(handler=cmd_done)
    commands.add_parser("status").set_defaults(handler=cmd_status)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
