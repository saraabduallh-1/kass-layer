"""Collect Arabic Wikipedia articles per writing domain (CC BY-SA text), as examples of specialist writing.

  .venv/bin/python scripts/corpus/fetch_wikipedia.py [--per-domain 300]

Each domain is a list of Wikipedia categories (plus their direct subcategories); "general" is random
articles, the baseline for "ordinary" writing. Output: data/corpus/wikipedia/<domain>.jsonl
({"title", "text"}; text cut to 6,000 characters). Resumable: titles already saved are skipped.
The dictionaries are not touched; build_word_index.py turns this corpus into word statistics.
"""
from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "corpus" / "wikipedia"
API = "https://ar.wikipedia.org/w/api.php"
SSL = ssl.create_default_context(cafile=certifi.where())  # python.org builds ship without CA certificates
UA = "kass-layer-research/0.1 (https://github.com/saraabduallh-1/kass-layer)"
MAX_CHARS = 6000

CATEGORIES = {
    "tech": ["تعلم الآلة", "ذكاء اصطناعي", "علم البيانات", "قواعد بيانات", "هندسة البرمجيات", "أمن الحاسوب", "شبكات الحاسوب", "حوسبة سحابية", "معالجة اللغات الطبيعية", "برمجيات", "لغات برمجة", "إنترنت", "حواسيب", "رؤية حاسوبية"],
    "legal": ["قانون", "عقود", "قانون جنائي", "قانون مدني", "قانون تجاري", "قانون العمل", "إجراءات قانونية", "محاكم"],
    "finance": ["اقتصاد", "محاسبة", "تمويل", "أسواق مالية", "مصارف", "إدارة أعمال", "إحصاء", "موارد بشرية"],
    "media": ["صحافة", "إعلام", "تلفاز", "إذاعة", "إعلان", "وسائل التواصل الاجتماعي", "أفلام وثائقية", "قنوات تلفزيونية", "صحف", "برامج تلفزيونية", "صحفيون", "مذيعون", "علاقات عامة", "بث"],
    "eng": ["هندسة الطيران", "طيران", "طاقة", "هندسة كهربائية", "سيارات", "سكك حديدية", "هندسة مدنية", "طاقة متجددة"],
    "culture": ["رياضة", "كرة القدم", "موسيقى", "آلات موسيقية", "علم الحيوان", "علم السلوك", "رياضة إلكترونية", "حياة برية"],
}


def api(**params) -> dict:
    params.update(format="json", formatversion="2")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30, context=SSL) as r:
                return json.load(r)
        except Exception as e:
            print(f"  request failed ({type(e).__name__}: {e}), retrying", flush=True)
            time.sleep(2 ** attempt)
    return {}


def members(category: str, kind: str) -> list[str]:
    out, cont = [], {}
    while len(out) < 500:
        d = api(action="query", list="categorymembers", cmtitle="تصنيف:" + category, cmtype=kind, cmlimit="200", **cont)
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" not in d:
            break
        cont = {"cmcontinue": d["continue"]["cmcontinue"]}
    return out


def titles_for(domain: str, want: int) -> list[str]:
    if domain == "general":
        out = []
        while len(out) < want * 2:
            d = api(action="query", list="random", rnnamespace="0", rnlimit="100")
            out += [p["title"] for p in d.get("query", {}).get("random", [])]
        return list(dict.fromkeys(out))
    seen = {}
    for cat in CATEGORIES[domain]:
        for t in members(cat, "page"):
            seen[t] = None
        for sub in members(cat, "subcat")[:15]:
            for t in members(sub.split(":", 1)[1], "page")[:40]:
                seen[t] = None
    return list(seen)


def texts(titles: list[str]) -> list[dict]:
    # the API returns one full-text extract per request and hands back a continuation for the rest
    out, cont = {}, {}
    for _ in range(len(titles) + 1):
        d = api(action="query", prop="extracts", explaintext="1", exlimit="20", titles="|".join(titles), **cont)
        for p in d.get("query", {}).get("pages", []):
            if len(p.get("extract", "")) > 400:
                out[p["title"]] = p["extract"][:MAX_CHARS]
        if "continue" not in d:
            break
        cont = {"excontinue": d["continue"]["excontinue"]}
        time.sleep(0.1)
    return [{"title": t, "text": x} for t, x in out.items()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-domain", type=int, default=300)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for domain in [*CATEGORIES, "general"]:
        path = OUT / f"{domain}.jsonl"
        have = {json.loads(l)["title"] for l in path.read_text(encoding="utf-8").splitlines()} if path.exists() else set()
        want = args.per_domain * (3 if domain == "general" else 1)
        if len(have) >= want:
            print(f"{domain}: {len(have)} articles (done)")
            continue
        todo = [t for t in titles_for(domain, want) if t not in have]
        with path.open("a", encoding="utf-8") as f:
            for i in range(0, len(todo), 20):
                if len(have) >= want:
                    break
                for art in texts(todo[i:i + 20]):
                    if art["title"] not in have:
                        f.write(json.dumps(art, ensure_ascii=False) + "\n")
                        have.add(art["title"])
                time.sleep(0.5)  # be polite to Wikipedia
        print(f"{domain}: {len(have)} articles", flush=True)


if __name__ == "__main__":
    main()
