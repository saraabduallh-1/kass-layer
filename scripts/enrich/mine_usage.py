"""Pass 3 mining: Arabic words real writers use for a term, found through its English name, with the evidence kept.

  .venv/Scripts/python scripts/enrich/mine_usage.py run <dictionary> [--limit N] [--term ...]
      For each sense with an English term, resumable, written to variants/raw/usage/<id>.jsonl:
        wikidata  Arabic label and aliases of the entity the English Wikipedia page belongs to (edited by people)
        redirect  Arabic Wikipedia title for that page and every title redirecting to it
        paren     Arabic Wikipedia text where a writer glosses a word with the English term: «العميل (Agent)»
      Polite: one request at a time with a pause, a descriptive User-Agent, and maxlag.
  .venv/Scripts/python scripts/enrich/mine_usage.py show <dictionary> [--limit 150] [--offset 0]
      Prints senses with new candidates: term | english | definition || current forms || form[sources] ...

Nothing here changes the dictionaries: Claude reviews the candidates and applies the good ones with topic_pass.py.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.enrichment import (  # noqa: E402
    OUT_DIR,
    append_jsonl,
    article_free_key,
    complete_dictionaries,
    current_generations,
    current_reviews,
    normalize,
    read_jsonl,
)

OUT = OUT_DIR / "raw" / "usage"
PAUSE = 0.4
EN_API, AR_API = "https://en.wikipedia.org/w/api.php", "https://ar.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "KassLayerResearch/0.1 (Arabic terminology research; https://github.com/saraabduallh-1/kass-layer)"}
ARABIC_ONLY = re.compile(r"^[ء-يً-ْ\s\-]+$")
LEAD_STOP = {normalize(w) for w in ["في", "من", "إلى", "على", "عن", "مع", "أو", "و", "أن", "إن", "هو", "هي", "هذا", "هذه", "ذلك", "التي",
                                    "الذي", "باسم", "يسمى", "تسمى", "يعرف", "تعرف", "مثل", "بين", "كما", "ثم", "قد", "لا", "ما", "عند", "بالإنجليزية", "بالانجليزية", "الإنجليزية", "الانجليزية", "باللغة", "اللغة"]}
session = requests.Session()
session.headers.update(HEADERS)


def api(url: str, **params) -> dict:
    params.update(format="json", formatversion=2, maxlag=5)
    for attempt in range(4):
        time.sleep(PAUSE)
        try:
            response = session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("error", {}).get("code") != "maxlag":
                    return data
            time.sleep(5 * (attempt + 1))
        except (requests.RequestException, ValueError):
            time.sleep(5 * (attempt + 1))
    return {}


def clean_english(english: str) -> str:
    return " ".join(re.sub(r"\([^)]*\)", " ", english or "").split())


def from_pages(english: str) -> dict[str, set[str]]:
    """Wikidata label and aliases, Arabic title and redirects of the English page with this exact name."""
    found: dict[str, set[str]] = defaultdict(set)
    query = api(EN_API, action="query", titles=english, redirects=1, prop="langlinks|pageprops", lllang="ar", ppprop="wikibase_item|disambiguation")
    pages = (query.get("query") or {}).get("pages") or []
    if not pages or pages[0].get("missing") or "disambiguation" in (pages[0].get("pageprops") or {}):
        return found
    page = pages[0]
    item = (page.get("pageprops") or {}).get("wikibase_item")
    if item:
        entity = (api(WD_API, action="wbgetentities", ids=item, props="labels|aliases", languages="ar").get("entities") or {}).get(item) or {}
        label = (entity.get("labels") or {}).get("ar") or {}
        if label.get("value"):
            found[label["value"]].add("wikidata")
        for alias in (entity.get("aliases") or {}).get("ar") or []:
            found[alias["value"]].add("wikidata")
    links = page.get("langlinks") or []
    if links:
        title = links[0].get("title")
        found[title].add("redirect")
        redirects = api(AR_API, action="query", titles=title, prop="redirects", rdlimit=50, rdnamespace=0)
        for ar_page in (redirects.get("query") or {}).get("pages") or []:
            for redirect in ar_page.get("redirects") or []:
                found[redirect["title"]].add("redirect")
    return found


def from_glosses(english: str, words: int) -> dict[str, int]:
    """Words written right before a parenthesis holding the English term, in Arabic Wikipedia."""
    hits = (api(AR_API, action="query", list="search", srsearch=f'"{english}"', srnamespace=0, srlimit=20).get("query") or {}).get("search") or []
    pattern = re.compile(r"((?:[ء-يً-ْ]+\s+){1,%d})\(\s*(?:(?:ب|)ال[إا]نجليزية\s*:?\s*)?%s\s*[\),:;]" % (words + 1, re.escape(english)), re.I)
    counts: dict[str, int] = defaultdict(int)
    for hit in hits:
        text = html.unescape(re.sub(r"<[^>]+>", "", hit.get("snippet") or ""))
        for match in pattern.finditer(text):
            tokens = match.group(1).split()
            for size in range(1, min(words + 1, len(tokens)) + 1):  # every ending of the phrase: the review picks the right span
                form = " ".join(tokens[-size:])
                if normalize(tokens[-size]) not in LEAD_STOP:
                    counts[form] += 1
    return counts


def _dictionary(prefix: str) -> dict:
    for dictionary in complete_dictionaries():
        if dictionary["dictionary_id"].startswith(prefix):
            return dictionary
    raise SystemExit(f"No completed dictionary {prefix}")


def _translation(record: dict) -> str:  # some senses (وكيل) carry their English name only among the translations
    return next((t.get("word") or "" for t in record.get("translations") or [] if t.get("language") == "en"), "")


def _senses(dictionary: dict) -> list[dict]:
    reviews = current_reviews(dictionary, current_generations(dictionary))
    return [{"sense_id": r["sense_id"], "term": r.get("term_without_diacritics") or r["term"], "english": clean_english(r.get("english_term") or _translation(r)),
             "definition": " ".join((r.get("definition") or "").split())[:110],
             "existing": [v["form"] for v in (reviews.get(r["sense_id"]) or {}).get("variants") or []]}
            for r in dictionary["records"]]


def mine(sense: dict) -> list[dict]:
    english, words = sense["english"], max(1, len(sense["term"].split()))
    candidates: dict[str, dict] = {}
    for form, sources in from_pages(english).items():
        candidates[form] = {"form": form, "sources": sorted(sources), "count": 0}
    for form, count in from_glosses(english, words).items():
        entry = candidates.setdefault(form, {"form": form, "sources": [], "count": 0})
        entry["sources"] = sorted(set(entry["sources"]) | {"paren"})
        entry["count"] += count
    taken = {normalize(f) for f in sense["existing"]} | {article_free_key(f) for f in sense["existing"]}
    taken |= {normalize(sense["term"]), article_free_key(sense["term"])}
    kept = []
    for entry in candidates.values():
        form = " ".join(re.sub(r"\([^)]*\)", " ", entry["form"]).split())
        if (form and ARABIC_ONLY.match(form) and 1 <= len(form.split()) <= 5
                and normalize(form) not in taken and article_free_key(form) not in taken):
            kept.append({**entry, "form": form})
    return sorted(kept, key=lambda e: (-len(e["sources"]), -e["count"]))


def cmd_run(args) -> None:
    dictionary = _dictionary(args.dictionary)
    path = OUT / f"{dictionary['dictionary_id']}.jsonl"
    OUT.mkdir(parents=True, exist_ok=True)
    done = {r["sense_id"] for r in read_jsonl(path)} if path.exists() else set()
    work = [s for s in _senses(dictionary) if s["english"] and s["sense_id"] not in done]
    if args.term:
        work = [s for s in work if s["term"] in args.term]
    work = work[: args.limit]
    print(f"{len(work)} senses to mine", flush=True)
    found = 0
    for n, sense in enumerate(work, 1):
        candidates = mine(sense)
        found += bool(candidates)
        append_jsonl(path, [{"sense_id": sense["sense_id"], "term": sense["term"], "english": sense["english"], "candidates": candidates}])
        if n % 50 == 0 or n == len(work):
            print(f"  {n}/{len(work)}, {found} with candidates", flush=True)


def cmd_show(args) -> None:
    dictionary = _dictionary(args.dictionary)
    senses = {s["sense_id"]: s for s in _senses(dictionary)}
    rows = [r for r in read_jsonl(OUT / f"{dictionary['dictionary_id']}.jsonl") if r["candidates"]]
    print(f"# {len(rows)} senses with candidates, from {args.offset}")
    for r in rows[args.offset: args.offset + args.limit]:
        s = senses[r["sense_id"]]
        forms = " ; ".join(f"{c['form']}[{','.join(x[0] for x in c['sources'])}{c['count'] or ''}]" for c in r["candidates"])
        print(f"{r['term']} | {r['english']} | {s['definition']} || {' ; '.join(s['existing'][:6])} || {forms}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("dictionary")
    run.add_argument("--limit", type=int)
    run.add_argument("--term", action="append")
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
