"""Build the compact lookup file used by the browser demo page (terms + every reviewed variant).

  .venv/bin/python scripts/demo/build_demo_index.py <out_dir>
Writes <out_dir>/index.json: dictionary names, one row per sense [term, dictionary, english, short definition],
and a form -> [[sense, flags, type], ...] map. flags: 1 accepted, 2 ambiguous, 4 the form is the standard term.
vocab maps each Arabic word (leading ال removed) seen in terms and definitions to the number of senses using it.
Keys are normalized like the Python pipeline, plus an article-free key (leading ال removed) for each form.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from kass_layer.dictionary.enrichment import normalize  # noqa: E402

INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")  # bidi/zero-width marks found in some source terms
TYPES = {"foreign": "f", "transliteration": "t", "abbreviation": "a", "informal_synonym": "i",
         "colloquial": "c", "spelling_variant": "s"}


def keys(form: str) -> set[str]:
    key = normalize(form)
    out = {key} if key else set()
    words = key.split()
    if words and words[0].startswith("ال") and len(words[0]) > 3:
        out.add(" ".join([words[0][2:]] + words[1:]))
    if len(words) > 1:  # also without ال on every word: «تضارب مصالح» = «تضارب المصالح»
        out.add(" ".join(w[2:] if w.startswith("ال") and len(w) > 3 else w for w in words))
    return out


def main(out_dir: str) -> None:
    dictionaries, senses, forms, vocab = [], [], {}, {}
    for path in sorted((ROOT / "data" / "dictionaries" / "enriched").glob("*.enriched.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        d = len(dictionaries)
        dictionaries.append(" ".join(data["dictionary_name"].split()))
        for record in data["records"]:
            term = " ".join(INVISIBLE.sub(" ", record.get("term_without_diacritics") or record["term"]).split())
            definition = " ".join(INVISIBLE.sub(" ", record.get("definition") or "").split())
            if len(definition) > 90:
                definition = definition[:88].rsplit(" ", 1)[0] + "…"
            english = (record.get("english_term") or "").strip()
            english = "" if english in {"None", "none"} else english
            s = len(senses)
            senses.append([term, d, english, definition])
            # Arabic vocabulary seen in terms and full definitions: tells native words from foreign spellings
            for word in set(re.findall(r"[\u0621-\u064a]{3,}", normalize(term + " " + (record.get("definition") or "")))):
                bare = word[2:] if word.startswith("ال") and len(word) > 4 else word
                vocab[bare] = vocab.get(bare, 0) + 1
            plain = " ".join(re.sub(r"\([^)]*\)", " ", term).split())  # «بيانات التدريب (أو مجموعة التدريب)» is also «بيانات التدريب»
            for key in keys(term) | (keys(plain) if plain and plain != term else set()):
                forms.setdefault(key, []).append([s, 1 | 4, ""])
            for v in (record.get("enrichment") or {}).get("variants") or []:
                flags = (1 if v.get("status") == "accepted" else 0) | (2 if v.get("ambiguous") else 0)
                for key in keys(v["form"]):
                    if len(key) >= 2:
                        forms.setdefault(key, []).append([s, flags, TYPES.get(v.get("type"), "")])
    for key, rows in forms.items():  # one row per sense, keep the strongest flags
        best = {}
        for s, flags, kind in rows:
            if s not in best or flags > best[s][1]:
                best[s] = [s, flags, kind]
        forms[key] = list(best.values())
    out = Path(out_dir) / "index.json"
    out.write_text(json.dumps({"dictionaries": dictionaries, "senses": senses, "forms": forms, "vocab": vocab},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(dictionaries)} dictionaries, {len(senses)} senses, {len(forms)} keys, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
