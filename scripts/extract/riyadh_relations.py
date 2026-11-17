"""Links between ordinary Arabic word forms, from معجم الرياض للغة العربية المعاصرة (the user's JSONL export).

The Riyadh dictionary is general Arabic, not terminology, so it never proposes replacements. Kass uses it only to tell
the unification step which written forms are one word or one concept:
  syn     word -> nouns the dictionary lists as its synonyms AND translates the same way
          (حاسوب، حاسب، كمبيوتر = computer), not حاسبة (calculator);
  own     feminine forms that are their own word, not the feminine of the other one (حاسبة is not «حاسب» + ة);
  place   place names ending in «يا» (سوريا), so «سورية / سوريه» is read as a spelling of the same name.
Plurals are not taken from it: its «جمع …» definitions are too uneven (ظروف is given as the plural of ظريف).

Run: .venv/Scripts/python scripts/extract/riyadh_relations.py data/dictionaries/raw/riyadh/riyadh-published.jsonl demo_local/riyadh.json
The input file is only read.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from kass_layer.detector.engine import bare, normalize  # noqa: E402

FEM_ONLY = re.compile(r"^\s*مؤنث")


def key(word: str) -> str:
    return bare(normalize(word))


def main(src: str, out: str) -> None:
    rows = [json.loads(line) for line in open(src, encoding="utf-8") if line.strip()]
    single = [r for r in rows if r.get("type") == "singleWord" and len(normalize(r["word"]).split()) == 1]

    heads: dict[str, list[dict]] = defaultdict(list)
    for r in single:
        heads[key(r["word"])].append(r)

    def translations(k: str) -> set[str]:
        return {t.strip().lower() for r in heads.get(k, []) for s in r["senses"] for t in s.get("translations") or [] if t.strip()}

    # syn: a noun and a listed synonym that is itself a headword with a shared translation (direct links only, never
    # chained: «مصدر = source» and «ناشر = publisher» must not meet through a third word)
    links: dict[str, set[str]] = defaultdict(set)
    for r in single:
        if not (r.get("pos") or "").startswith("N"):
            continue
        a = key(r["word"])
        for s in r["senses"]:
            tr = {t.strip().lower() for t in s.get("translations") or [] if t.strip()}
            for w in s.get("synonyms") or []:
                b = key(w)
                if b != a and len(b.split()) == 1 and len(a) >= 3 and len(b) >= 3 and tr & translations(b):
                    links[a].add(b)
                    links[b].add(a)
    syn = {a: sorted(bs) for a, bs in sorted(links.items())}

    # own: «حاسبة» has its own meaning (no sense is «مؤنث …») and «حاسب» is a headword too, translated differently
    own = []
    for k, rs in heads.items():
        if not k.endswith("ه") or len(k) < 4 or k[:-1] not in heads:
            continue
        senses = [s for r in rs for s in r["senses"]]
        if any(FEM_ONLY.match(s.get("definition", "")) for s in senses):
            continue
        tk, tm = translations(k), translations(k[:-1])
        if tk and tm and not tk & tm:
            own.append(k)

    place = sorted({key(r["word"]) for r in single if r.get("pos") == "NL" and key(r["word"]).endswith("يا")})

    data = {"source": "معجم الرياض للغة العربية المعاصرة", "syn": syn, "own": sorted(own), "place": place}
    Path(out).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(rows)} entries: {len(syn)} words with synonyms, {len(own)} own feminine forms, "
          f"{len(place)} place names -> {out} ({Path(out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
