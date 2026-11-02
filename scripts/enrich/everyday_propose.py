"""Pass 3 proposals: everyday Arabic words writers use instead of a specialist term (عميل -> وكيل, غلاء الأسعار -> تضخم).

  .venv/Scripts/python scripts/enrich/everyday_propose.py run <dictionary> [--limit N] [--workers 2]
      One Gemma call per sense, resumable, written to variants/raw/everyday/<id>.jsonl. Deterministic filters: Arabic
      script, 1-4 words, not the term, an existing form, or the standard term of another sense of the dictionary.
      Below 4 GB of free GPU memory it exits without loading anything (see audit_pairs.pick_model).
  .venv/Scripts/python scripts/enrich/everyday_propose.py show <dictionary> [--limit 150] [--offset 0]
      Prints senses with proposals: <term> | english | definition || current forms || proposals.

Nothing here changes the dictionaries: Claude reviews the proposals and applies the good ones with topic_pass.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "enrich"))

from audit_pairs import pick_model  # noqa: E402
from kass_layer.dictionary.enrichment import (  # noqa: E402
    OUT_DIR,
    append_jsonl,
    article_free_key,
    complete_dictionaries,
    current_generations,
    current_reviews,
    extract_json,
    load_dotenv,
    normalize,
    read_jsonl,
)
from kass_layer.dictionary.qwen_client import QwenClient, QwenError  # noqa: E402

OUT = OUT_DIR / "raw" / "everyday"
ARABIC_ONLY = re.compile(r"^[؀-ۿ\s]+$")
PROMPT = """أنت خبير في العربية المعاصرة كما تُكتب في التقارير والمقالات والأخبار.
أمامك مصطلح متخصص وتعريفه. اذكر الكلمات أو العبارات العربية اليومية التي يكتبها غير المتخصصين فعلًا بدلًا منه وبالمعنى نفسه تمامًا.
أمثلة: وكيل (agent) ← عميل. تضخم (inflation) ← غلاء الأسعار. تنبؤ (prediction) ← التوقع.
قواعد: الاستعمال الحقيقي فقط، لا تخترع ولا تشرح المصطلح. لا مفهوم أعم أو أخص أو مرتبط. لا تعريب بحروف عربية، ولا تكرر المصطلح أو الصيغ الموجودة.
القائمة الفارغة هي الجواب الصحيح لأغلب المصطلحات.
أجب بـ JSON فقط: {"forms": ["..."]}"""


def _dictionary(prefix: str) -> dict:
    for dictionary in complete_dictionaries():
        if dictionary["dictionary_id"].startswith(prefix):
            return dictionary
    raise SystemExit(f"No completed dictionary {prefix}")


def _path(dictionary: dict) -> Path:
    return OUT / f"{dictionary['dictionary_id']}.jsonl"


def _senses(dictionary: dict) -> list[dict]:
    reviews = current_reviews(dictionary, current_generations(dictionary))
    return [{"sense_id": r["sense_id"], "term": r.get("term_without_diacritics") or r["term"],
             "english": r.get("english_term") or "", "definition": " ".join((r.get("definition") or "").split())[:300],
             "existing": [v["form"] for v in (reviews.get(r["sense_id"]) or {}).get("variants") or []]}
            for r in dictionary["records"]]


def propose(client: QwenClient, sense: dict, terms: set[str]) -> dict:
    user = (f"المصطلح: {sense['term']} ({sense['english'] or '-'})\nالتعريف: {sense['definition'] or '-'}\n"
            f"الصيغ الموجودة: {' ، '.join(sense['existing']) or '-'}")
    text, _ = client.complete([{"role": "system", "content": PROMPT}, {"role": "user", "content": user}], {})
    payload = extract_json(text)
    forms = payload.get("forms") if isinstance(payload, dict) else None
    taken = {normalize(f) for f in sense["existing"]} | {article_free_key(f) for f in sense["existing"]}
    kept = []
    for form in forms if isinstance(forms, list) else []:
        form = " ".join(str(form).split())
        key = normalize(form)
        if (ARABIC_ONLY.match(form) and 1 <= len(form.split()) <= 4 and key not in taken
                and article_free_key(form) not in taken and key not in terms and article_free_key(form) not in terms
                and form not in kept):
            kept.append(form)
    return {"sense_id": sense["sense_id"], "term": sense["term"], "proposals": kept, "model": client.model}


def cmd_run(args) -> None:
    model = pick_model()
    if model is None:
        raise SystemExit("under 4 GB of GPU memory free: nothing loaded, try later")
    load_dotenv()
    dictionary = _dictionary(args.dictionary)
    senses = _senses(dictionary)
    terms = {normalize(s["term"]) for s in senses} | {article_free_key(s["term"]) for s in senses}
    path = _path(dictionary)
    done = {r["sense_id"] for r in read_jsonl(path)} if path.exists() else set()
    work = [s for s in senses if s["sense_id"] not in done][: args.limit]
    client = QwenClient(model=model, thinking=False, temperature=0.2, max_tokens=300)

    def safe(sense):
        try:
            return propose(client, sense, terms)
        except (QwenError, ValueError) as error:
            print(f"  failed {sense['term']}: {str(error)[:100]}", flush=True)
            return None

    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for start in range(0, len(work), 100):  # saved in chunks, so an interruption loses little
            rows = [r for r in pool.map(safe, work[start:start + 100]) if r]
            append_jsonl(path, rows)
            print(f"  {start + len(rows)}/{len(work)}", flush=True)
    print(f"{model}: {len(work)} senses done")


def cmd_show(args) -> None:
    dictionary = _dictionary(args.dictionary)
    senses = {s["sense_id"]: s for s in _senses(dictionary)}
    rows = [r for r in read_jsonl(_path(dictionary)) if r["proposals"]]
    print(f"# {len(rows)} senses with proposals, from {args.offset}")
    for r in rows[args.offset: args.offset + args.limit]:
        s = senses[r["sense_id"]]
        print(f"{r['term']} | {s['english']} | {s['definition'][:90]} || {' ; '.join(s['existing'][:5])} "
              f"|| {' ; '.join(r['proposals'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("dictionary")
    run.add_argument("--limit", type=int)
    run.add_argument("--workers", type=int, default=2)
    run.set_defaults(handler=cmd_run)
    show = commands.add_parser("show")
    show.add_argument("dictionary")
    show.add_argument("--limit", type=int, default=150)
    show.add_argument("--offset", type=int, default=0)
    show.set_defaults(handler=cmd_show)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
