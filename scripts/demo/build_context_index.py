"""Build context.json for the demo: a few distinctive Arabic keywords per sense (TF-IDF over term + definition).

  .venv/bin/python scripts/demo/build_context_index.py <out_dir>
When a word could be several terms, the page scores each candidate by how many of its keywords also occur in
the user's text: «الفيوز» near «القذيفة» → فتيلة انفجار; near «الدائرة الكهربائية» → مصهر. Lightweight: no model.
Row i of "kw" belongs to sense i of index.json (same file order).
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from kass_layer.dictionary.enrichment import normalize  # noqa: E402

STOP = set(normalize("""التي الذي الذين وهو وهي هذا هذه ذلك تلك على الى إلى من في عن مع او أو ثم بين عند كل بعض غير
قبل بعد حيث كما مثل لدى خلال ضمن عبر ايضا أيضا يتم يكون تكون كان كانت هو هي هم وفق وفقا اي أي ما لا لم لن قد
يمكن عملية مجموعة استخدام طريقة نوع جزء شكل حالة""").split())
INVISIBLE = re.compile("[​-‏‪-‮⁦-⁩﻿]")


def words(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[ء-ي]{3,}", normalize(INVISIBLE.sub(" ", text))):
        w = w[2:] if w.startswith("ال") and len(w) > 4 else w
        w = w[1:] if w[0] in "وبل" and len(w) > 4 and w[1:2] != "ا" else w
        if w not in STOP:
            out.append(w)
    return out


def main(out_dir: str) -> None:
    docs = []
    for path in sorted((ROOT / "data" / "dictionaries" / "enriched").glob("*.enriched.json")):
        for record in json.loads(path.read_text(encoding="utf-8"))["records"]:
            docs.append(words((record.get("term_without_diacritics") or record["term"]) + " " + (record.get("definition") or "")))
    df = Counter(w for doc in docs for w in set(doc))
    n = len(docs)
    kw = []
    for doc in docs:
        tf = Counter(doc)
        ranked = sorted(tf, key=lambda w: -(tf[w] * math.log(n / df[w])))
        kw.append(" ".join(w for w in ranked if df[w] < n * 0.02)[:80].rsplit(" ", 1)[0] if ranked else "")
    out = Path(out_dir) / "context.json"
    out.write_text(json.dumps({"kw": kw}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{n} senses, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
