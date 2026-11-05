"""Filter mined usage candidates before Claude reviews them: do people write the form, and does it mean the term?

  .venv/Scripts/python scripts/enrich/usage_filter.py count [--workers 6] [--gb 20]
      Scans the Arabic tweets (data/corpus/tweets/lm_twitter.txt) in parallel byte ranges and counts every candidate of
      variants/raw/usage/*.jsonl as a whole-word phrase, keeping up to 3 example tweets. Writes variants/raw/usage/tweets.json.
  .venv/Scripts/python scripts/enrich/usage_filter.py judge [--limit N]
      Clef-Flash (4-bit, local GPU) rates each candidate: in its example tweets when it has some, else from the term alone.
      Cached in variants/raw/usage/clef.json.
  .venv/Scripts/python scripts/enrich/usage_filter.py show <dictionary> [--min-count 3] [--min-p 0.5] [--limit 200] [--offset 0]
      Prints the senses whose candidates pass both filters: term | english || current forms || form(count, p) ...

Forms are compared after tweet-style normalisation (no hamza forms, ة → ه, ى → ي), since the tweets are written that way.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "enrich"))

from kass_layer.dictionary.enrichment import OUT_DIR, complete_dictionaries, read_jsonl  # noqa: E402

USAGE = OUT_DIR / "raw" / "usage"
TWEETS = ROOT / "data" / "corpus" / "tweets" / "lm_twitter.txt"
COUNTS, CLEF = USAGE / "tweets.json", USAGE / "clef.json"
DIAC = re.compile("[ً-ْـ]")
WORD = re.compile(r"[ء-ي]+")
MAX_N = 5


def flat(text: str) -> str:
    text = DIAC.sub("", text)
    text = re.sub("[أإآٱ]", "ا", text).replace("ة", "ه").replace("ى", "ي")
    return " ".join(WORD.findall(text))


def candidates() -> dict[str, list[dict]]:
    """dictionary id -> mined rows (with candidates)."""
    return {p.stem: [r for r in read_jsonl(p) if r["candidates"]] for p in USAGE.glob("*.jsonl")}


def _scan(job: tuple[int, int, list[str]]) -> dict[str, list]:
    start, end, keys = job
    wanted = set(keys)
    found: dict[str, list] = {}
    with TWEETS.open("rb") as handle:
        handle.seek(start)
        if start:
            handle.readline()
        while handle.tell() < end:
            raw = handle.readline()
            if not raw:
                break
            words = flat(raw.decode("utf-8", "ignore")).split()
            for i in range(len(words)):
                for n in range(1, MAX_N + 1):
                    if i + n > len(words):
                        break
                    key = " ".join(words[i:i + n])
                    if key in wanted:
                        entry = found.setdefault(key, [0, []])
                        entry[0] += 1
                        if len(entry[1]) < 3:
                            entry[1].append(raw.decode("utf-8", "ignore").strip()[:200])
    return found


def cmd_count(args) -> None:
    keys = sorted({flat(c["form"]) for rows in candidates().values() for r in rows for c in r["candidates"]} - {""})
    size = min(TWEETS.stat().st_size, int(args.gb * 1e9))
    chunks = args.workers * 4
    jobs = [(size * i // chunks, size * (i + 1) // chunks, keys) for i in range(chunks)]
    print(f"{len(keys)} forms, {size / 1e9:.1f} GB in {chunks} parts", flush=True)
    total: dict[str, list] = {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for n, part in enumerate(pool.map(_scan, jobs), 1):
            for key, (count, examples) in part.items():
                entry = total.setdefault(key, [0, []])
                entry[0] += count
                entry[1] = (entry[1] + examples)[:3]
            print(f"  part {n}/{chunks}, {len(total)} forms seen", flush=True)
    COUNTS.write_text(json.dumps({"gb": size / 1e9, "counts": total}, ensure_ascii=False), encoding="utf-8")


def cmd_judge(args) -> None:
    sys.path.insert(0, str(ROOT / "scripts" / "evaluate"))
    from decision_clef import ask, load
    counts = json.loads(COUNTS.read_text(encoding="utf-8"))["counts"]
    cache = json.loads(CLEF.read_text(encoding="utf-8")) if CLEF.exists() else {}
    senses = {r["sense_id"]: r for d in complete_dictionaries() for r in d["records"]}
    todo = []
    for rows in candidates().values():
        for r in rows:
            for c in r["candidates"]:
                k = f"{r['sense_id']}\t{c['form']}"
                if k not in cache:
                    todo.append((k, r, c))
    todo = todo[: args.limit]
    print(f"{len(todo)} candidates to judge", flush=True)
    model, processor = load(4)
    question = ("هل يستعمل الكاتب هذه الكلمة اسمًا لهذا المصطلح نفسه، بحيث يصح استبدالها بالمصطلح؟ "
                "أجب بالنفي إذا كانت تعني شيئًا آخر أو مفهومًا أعم أو أخص أو مرتبطًا فقط.")
    for n, (k, r, c) in enumerate(todo, 1):
        sense = senses.get(r["sense_id"], {})
        base = {"المصطلح": r["term"], "المقابل الإنجليزي": r["english"],
                "التعريف": " ".join((sense.get("definition") or "-").split())[:300], "الكلمة": c["form"]}
        examples = (counts.get(flat(c["form"])) or [0, []])[1]
        ps = [ask(model, processor, {**base, "الجملة": e}, question) for e in examples] or [ask(model, processor, base, question)]
        cache[k] = round(max(ps), 4)
        if n % 200 == 0:
            CLEF.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            print(f"  {n}/{len(todo)}", flush=True)
    CLEF.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def cmd_show(args) -> None:
    counts = json.loads(COUNTS.read_text(encoding="utf-8"))["counts"]
    cache = json.loads(CLEF.read_text(encoding="utf-8")) if CLEF.exists() else {}
    dictionary = next(d for d in complete_dictionaries() if d["dictionary_id"].startswith(args.dictionary))
    rows, shown = candidates().get(dictionary["dictionary_id"], []), []
    for r in rows:
        kept = []
        for c in r["candidates"]:
            count = (counts.get(flat(c["form"])) or [0])[0]
            p = cache.get(f"{r['sense_id']}\t{c['form']}")
            human = bool(set(c["sources"]) & {"wikidata", "redirect"}) or c["count"] >= 2  # a curated name, or glossed twice
            judged = args.min_p < 0 or (p is not None and p >= args.min_p)  # --min-p -1: without Clef (GPU busy)
            if count >= args.min_count and human and judged and not (len(c["form"].split()) == 1 and count > 20000):
                kept.append(f"{c['form']}({count}" + (f",{p:.2f})" if p is not None else ")"))
        if kept:
            shown.append(f"{r['term']} | {r['english']} || {' ; '.join(kept)}")
    print(f"# {len(shown)} senses with candidates passing (count >= {args.min_count}, p >= {args.min_p}), from {args.offset}")
    print("\n".join(shown[args.offset: args.offset + args.limit]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    count = commands.add_parser("count")
    count.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 2))
    count.add_argument("--gb", type=float, default=20)
    count.set_defaults(handler=cmd_count)
    judge = commands.add_parser("judge")
    judge.add_argument("--limit", type=int)
    judge.set_defaults(handler=cmd_judge)
    show = commands.add_parser("show")
    show.add_argument("dictionary")
    show.add_argument("--min-count", type=int, default=3)
    show.add_argument("--min-p", type=float, default=0.5)
    show.add_argument("--limit", type=int, default=200)
    show.add_argument("--offset", type=int, default=0)
    show.set_defaults(handler=cmd_show)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
