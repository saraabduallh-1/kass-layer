"""Background Arabic enrichment pass (Qwen only, no Claude usage). Precision first.

For every reviewed sense not yet covered by an Arabic pass:
  1. Qwen proposes Arabic-script variants twice, independently (two prompts, two temperatures).
  2. Only forms proposed by BOTH runs survive (self-consistency).
  3. Deterministic filters: Arabic script, 1-4 words, not the term or an existing variant, and a
     transliteration must match the English term's consonant skeleton.
  4. A separate Qwen judge call rates each surviving form; only "same meaning + common usage" is kept.
Kept forms are merged into the sense's current review (existing variants untouched) and tagged
origin=arabic-auto. Every candidate and the reason it was kept or rejected is logged for audit in
variants/raw/arabic_auto/<dictionary_id>.jsonl. A sense with nothing that passes gets no addition.

  .venv/bin/python scripts/enrich/arabic_auto.py run [--dictionary ID ...] [--limit N] [--workers 8]
        [--dry-run] [--votes 1|2] [--min-sim 0.4] [--no-semantic]
  Pilot first:  run --dictionary 4cd164a7 --limit 30 --dry-run   (then audit pilot-<id>.jsonl)
  .venv/bin/python scripts/enrich/arabic_auto.py status
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from kass_layer.dictionary.enrichment import (  # noqa: E402
    OUT_DIR,
    REVIEW_DIR,
    append_jsonl,
    article_free_key,
    complete_dictionaries,
    current_generations,
    current_reviews,
    dictionary_name,
    extract_json,
    finalize,
    load_dotenv,
    normalize,
    review_hash,
)
from kass_layer.dictionary.qwen_client import QwenClient, QwenError  # noqa: E402

AUDIT_DIR = OUT_DIR / "raw" / "arabic_auto"
SOURCE = "arabic-auto"
ARABIC_TYPES = {"transliteration", "informal_synonym", "colloquial", "spelling_variant", "abbreviation"}

GEN_PROMPT = """أنت خبير في اللغة العربية المعاصرة كما يكتبها الناس فعلًا في التقارير والمقالات والأخبار ووسائل التواصل في السعودية والخليج.

المهمة: لمصطلح قياسي من معجم متخصص، اذكر الصيغ العربية (بالحروف العربية فقط) التي يكتبها غير المتخصصين فعلًا بدلًا منه وبالمعنى نفسه تمامًا. ستستبدل طبقة آلية هذه الصيغ بالمصطلح القياسي في نصوص عربية.

الأنواع المقبولة:
- transliteration: الكلمة الإنجليزية مكتوبة بحروف عربية (مودل، داتا، أوتوميشن، بيغ داتا).
- informal_synonym: تعبير عربي غير قياسي شائع للمفهوم نفسه (ترجمة حرفية متداولة، مصطلح قديم أو إقليمي).
- colloquial: صيغة عامية خليجية أو سعودية شائعة.
- spelling_variant: طريقة إملائية أخرى شائعة للمصطلح نفسه (همزة، تاء مربوطة، فصل أو وصل).

قواعد صارمة:
1. الاستخدام الحقيقي فقط. لا تخترع ولا تترجم من عندك. إذا لم تكن متأكدًا أن الناس يكتبونها فلا تذكرها.
2. المعنى نفسه تمامًا: لا مفهوم أعم ولا أخص ولا مرتبط.
3. الصيغة الأساسية فقط: بلا جمع ولا "ال" مضافة ولا ضمائر.
4. لا تكرر المصطلح نفسه ولا الصيغ الموجودة مسبقًا.
5. القائمة الفارغة هي الجواب الصحيح لكثير من المصطلحات، خاصة المصطلحات التقنية الطويلة التي لا يعيد أحد صياغتها.

أمثلة:
- نموذج (model) ← [{"form": "مودل", "type": "transliteration", "confidence": "high"}, {"form": "موديل", "type": "transliteration", "confidence": "high"}]
- بيانات ضخمة (big data) ← [{"form": "بيغ داتا", "type": "transliteration", "confidence": "high"}, {"form": "البيانات الكبيرة", "type": "informal_synonym", "confidence": "medium"}]
- مؤشر أداء رئيسي (KPI) ← [{"form": "كي بي آي", "type": "transliteration", "confidence": "medium"}]
- اكتشاف الشذوذ شبه الموجه (semi-supervised anomaly detection) ← []

أجب بـ JSON فقط بهذا الشكل: {"variants": [{"form": "...", "type": "...", "confidence": "high|medium|low"}]}"""

GEN_PROMPT_B = """You list how Arabic writers in Saudi Arabia and the Gulf actually write a specialised concept in everyday Arabic text (reports, articles, news, social media) instead of the official dictionary term. Arabic script only.

Give only forms you are sure are in real use with exactly the same meaning:
- transliteration: the English word in Arabic letters (e.g. model -> مودل, data -> داتا, dashboard -> داشبورد)
- informal_synonym: a common non-standard Arabic wording for the same concept
- colloquial: a common Gulf/Saudi dialect form
- spelling_variant: a common alternative spelling of the term
Never invent, never translate yourself, no broader/narrower concepts, no plurals or added ال, never the term itself or the forms already listed. Most long technical terms have no such forms: answer with an empty list then.

Reply with JSON only: {"variants": [{"form": "...", "type": "...", "confidence": "high|medium|low"}]}"""

JUDGE_PROMPT = """أنت مدقق لغوي صارم. أمامك مصطلح قياسي من معجم متخصص، وقائمة صيغ عربية مقترحة يُفترض أن الناس يكتبونها بدلًا منه.
احكم على كل صيغة منفردة:
- same_meaning: true فقط إذا كانت تعني المفهوم نفسه تمامًا (ليست أعم ولا أخص ولا مفهومًا مرتبطًا).
- usage: "common" إذا كانت شائعة فعلًا في الكتابة العربية بهذا المعنى، "rare" إذا كانت نادرة، "none" إذا لم تكن مستخدمة أو مخترعة.
- ambiguous: true إذا كانت تعني في الاستعمال اليومي شيئًا آخر غير هذا المصطلح.
- ambiguity_note: عند ambiguous=true اذكر باختصار متى لا تعني هذا المصطلح، وإلا فاتركها فارغة.
- example: جملة عربية قصيرة طبيعية يكتبها غير متخصص تستخدم الصيغة بهذا المعنى (فقط إذا same_meaning=true و usage="common"، وإلا فارغة).
كن صارمًا: إذا شككت فاحكم بالرفض.

أجب بـ JSON فقط: {"judgements": [{"form": "...", "same_meaning": true, "usage": "common|rare|none", "ambiguous": false, "ambiguity_note": "", "example": "..."}]}"""

_AR2LAT = str.maketrans({"ب": "b", "پ": "b", "ت": "t", "ث": "t", "ج": "g", "ح": "h", "خ": "k", "د": "d", "ذ": "z",
                         "ر": "r", "ز": "z", "س": "s", "ش": "s", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "",
                         "غ": "g", "ف": "f", "ڤ": "f", "ق": "k", "ك": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n",
                         "ه": "h", "ة": "", "و": "", "ي": "", "ى": "", "ا": "", "أ": "", "إ": "", "آ": "", "ء": "",
                         "ئ": "", "ؤ": ""})


def _skeleton_ar(text: str) -> str:
    return re.sub(r"[^a-z]", "", normalize(text).replace("ه", "ة").translate(_AR2LAT))


def _skeleton_en(text: str) -> str:
    t = text.lower()
    for a, b in (("ph", "f"), ("ch", "s"), ("sh", "s"), ("th", "t"), ("ck", "k"), ("x", "ks"), ("qu", "k"),
                 ("q", "k"), ("p", "b"), ("v", "f"), ("j", "g"), ("c", "k"), ("w", ""), ("y", "")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z]|[aeiou]", "", t)


def transliteration_matches(form: str, english: str) -> bool:
    """True when the Arabic form's consonants plausibly spell (part of) the English term."""
    ar = _skeleton_ar(form)
    if not ar or not english:
        return False
    words = re.findall(r"[A-Za-z]+", english)
    candidates = {_skeleton_en(english)} | {_skeleton_en(" ".join(words[i:j]))
                                            for i in range(len(words)) for j in range(i + 1, len(words) + 1)}
    acronym = "".join(w[0] for w in words if w[0].isupper()) if len(words) > 1 else ""
    best = max((SequenceMatcher(None, ar, c).ratio() for c in candidates if c), default=0.0)
    return best >= 0.75 or (bool(acronym) and len(ar) >= 2 and best >= 0.6)


def _has_latin(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text))


def _has_arabic(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text))


def _term_block(record: dict, existing: list[str], name: str) -> str:
    term = record.get("term_without_diacritics") or record["term"]
    definition = " ".join((record.get("definition") or "").split())[:400]
    return (f"المعجم: {name}\nالمصطلح القياسي: {term}\nالمقابل الإنجليزي: {record.get('english_term') or '-'}\n"
            f"التعريف: {definition}\nالصيغ الموجودة مسبقًا: {' ، '.join(existing) or '-'}")


def _ask(client: QwenClient, system: str, user: str) -> dict:
    text, _ = client.complete([{"role": "system", "content": system}, {"role": "user", "content": user}], {})
    payload = extract_json(text)
    return payload if isinstance(payload, dict) else {}


class Semantic:
    """Optional EmbeddingGemma check: how close a candidate is in meaning to the term + definition."""

    def __init__(self, min_sim: float | None) -> None:
        from sentence_transformers import SentenceTransformer
        import torch
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.model = SentenceTransformer("google/embeddinggemma-300m", device=device)
        self.min_sim = min_sim
        self.lock = threading.Lock()

    def scores(self, term_text: str, forms: list[str]) -> list[float]:
        with self.lock:
            vectors = self.model.encode_document([term_text] + forms, normalize_embeddings=True)
        return [float(vectors[0] @ v) for v in vectors[1:]]


def process(record: dict, review: dict, name: str, gen_a: QwenClient, gen_b: QwenClient, judge: QwenClient,
            votes: int = 2, semantic: Semantic | None = None) -> dict:
    term = record.get("term_without_diacritics") or record["term"]
    english = record.get("english_term") or ""
    existing = [v["form"] for v in review.get("variants") or []]
    taken = {normalize(f) for f in existing} | {article_free_key(f) for f in existing}
    term_keys = {normalize(term), article_free_key(term)}
    block = _term_block(record, existing, name)

    runs = [_ask(gen_a, GEN_PROMPT, block).get("variants") or [], _ask(gen_b, GEN_PROMPT_B, block).get("variants") or []]
    proposed: list[dict[str, dict]] = []
    for run in runs:
        forms = {}
        for v in run if isinstance(run, list) else []:
            if isinstance(v, dict) and str(v.get("form", "")).strip():
                forms[normalize(v["form"])] = v
        proposed.append(forms)
    audit = {"sense_id": record["sense_id"], "term": term, "english": english, "candidates": []}

    def reject(form: str, reason: str) -> None:
        audit["candidates"].append({"form": form, "kept": False, "reason": reason})

    survivors = []
    for key in sorted(set(proposed[0]) | set(proposed[1])):
        v = proposed[0].get(key) or proposed[1][key]
        form = " ".join(str(v["form"]).split())
        kind = v.get("type") if v.get("type") in ARABIC_TYPES else "informal_synonym"
        if votes == 2 and (key not in proposed[0] or key not in proposed[1]):
            reject(form, "single_run_only")
        elif _has_latin(form) or not _has_arabic(form):
            reject(form, "not_arabic_script")
        elif not 1 <= len(form.split()) <= 4 or len(form.split()) > len(term.split()) + 2:
            reject(form, "length")
        elif key in term_keys or article_free_key(form) in term_keys:
            reject(form, "same_as_term")
        elif key in taken or article_free_key(form) in taken:
            reject(form, "already_present")
        elif kind == "transliteration" and not transliteration_matches(form, english):
            reject(form, "transliteration_mismatch")
        else:
            survivors.append({"form": form, "type": kind,
                              "confidence": min(str(proposed[0].get(key, {}).get("confidence", "low")),
                                                str(proposed[1].get(key, {}).get("confidence", "low")),
                                                key=["high", "medium", "low"].index)
                              if all(str(p.get(key, {}).get("confidence")) in {"high", "medium", "low"} for p in proposed)
                              else "medium"})

    if survivors and semantic is not None:
        definition = " ".join((record.get("definition") or "").split())[:300]
        sims = semantic.scores(f"{term}: {definition}" if definition else term, [s["form"] for s in survivors])
        passing = []
        for s, sim in zip(survivors, sims):
            s["similarity"] = round(sim, 3)
            if semantic.min_sim is not None and sim < semantic.min_sim:
                reject(s["form"], f"low_similarity_{sim:.2f}")
            else:
                passing.append(s)
        survivors = passing

    kept = []
    if survivors:
        verdicts = _ask(judge, JUDGE_PROMPT, block + "\nالصيغ المقترحة: " + " ، ".join(s["form"] for s in survivors))
        by_form = {normalize(j.get("form", "")): j for j in verdicts.get("judgements") or [] if isinstance(j, dict)}
        for s in survivors:
            j = by_form.get(normalize(s["form"]))
            if j is None:
                reject(s["form"], "judge_missing")
            elif j.get("same_meaning") is not True:
                reject(s["form"], "judge_not_same_meaning")
            elif j.get("usage") != "common":
                reject(s["form"], f"judge_usage_{j.get('usage')}")
            else:
                variant = {"form": s["form"], "type": s["type"], "confidence": s["confidence"],
                           "ambiguous": bool(j.get("ambiguous")),
                           "ambiguity_note": str(j.get("ambiguity_note") or "") if j.get("ambiguous") else "",
                           "example": str(j.get("example") or "").strip(), "action": "added", "original_form": "",
                           "origin": SOURCE}
                if "similarity" in s:
                    variant["similarity"] = s["similarity"]
                kept.append(variant)
                audit["candidates"].append({"form": s["form"], "kept": True, "reason": "passed",
                                            "similarity": s.get("similarity")})
    audit["kept"] = [v["form"] for v in kept]
    return {"audit": audit, "kept": kept}


def _pending(dictionary: dict) -> list[tuple[dict, dict, dict]]:
    generations = current_generations(dictionary)
    reviews = current_reviews(dictionary, generations)
    return [(record, reviews[record["sense_id"]], generations[record["sense_id"]]) for record in dictionary["records"]
            if record["sense_id"] in reviews
            and not str(reviews[record["sense_id"]].get("source", "")).startswith("arabic-")]


def cmd_run(args) -> None:
    load_dotenv()
    try:
        gen_a = QwenClient(thinking=False, temperature=0.2, max_tokens=800)
        gen_b = QwenClient(thinking=False, temperature=0.7, max_tokens=800)
        judge = QwenClient(thinking=False, temperature=0.0, max_tokens=1200)
    except QwenError as error:
        raise SystemExit(str(error))
    semantic = None if args.no_semantic else Semantic(args.min_sim)
    print(f"model {gen_a.model}; votes={args.votes}; semantic filter="
          f"{'off' if semantic is None else ('log only' if args.min_sim is None else f'min {args.min_sim}')}", flush=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    dictionaries = [d for d in complete_dictionaries()
                    if not args.dictionary or any(d["dictionary_id"].startswith(p) for p in args.dictionary)]
    for dictionary in dictionaries:
        work = _pending(dictionary)
        if args.limit is not None:
            work = work[: args.limit]
        if not work:
            continue
        name = dictionary_name(dictionary)
        print(f"== {name}: {len(work)} senses", flush=True)
        stats = {"senses": 0, "with_additions": 0, "forms_added": 0, "failed": 0}
        buffer: list[dict] = []

        def flush() -> None:
            if buffer:
                append_jsonl(REVIEW_DIR / f"{dictionary['dictionary_id']}.jsonl", buffer)
                buffer.clear()

        def job(item):
            record, review, generation = item
            return item, process(record, review, name, gen_a, gen_b, judge, args.votes, semantic)

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(job, item) for item in work]
            for done, future in enumerate(as_completed(futures), start=1):
                try:
                    (record, review, generation), result = future.result()
                except (QwenError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                    stats["failed"] += 1
                    print(f"  failed: {str(error)[:120]}", flush=True)
                    continue
                row = dict(review)
                row.update({"variants": list(review.get("variants") or []) + result["kept"],
                            "input_sha256": review_hash(generation), "source": f"{SOURCE}:qwen-2vote+judge",
                            "arabic_pass_added": [v["form"] for v in result["kept"]],
                            "arabic_pass_model": gen_a.model,
                            "arabic_pass_at": datetime.now(timezone.utc).isoformat()})
                with lock:
                    if args.dry_run:  # pilot: audit file only, nothing is marked done or added
                        append_jsonl(AUDIT_DIR / f"pilot-{dictionary['dictionary_id']}.jsonl", [result["audit"]])
                        continue
                    append_jsonl(AUDIT_DIR / f"{dictionary['dictionary_id']}.jsonl", [result["audit"]])
                    buffer.append(row)
                    if len(buffer) >= 50:
                        flush()
                stats["senses"] += 1
                stats["with_additions"] += bool(result["kept"])
                stats["forms_added"] += len(result["kept"])
                if done % 100 == 0 or done == len(work):
                    print(f"  {done}/{len(work)}  {stats}", flush=True)
        with lock:
            flush()
        if not args.dry_run:
            finalize(complete_dictionaries())
        print(f"  done {name}: {stats}", flush=True)


def cmd_status(args) -> None:
    total_done = total = 0
    for dictionary in complete_dictionaries():
        generations = current_generations(dictionary)
        reviews = current_reviews(dictionary, generations)
        done = [r for r in reviews.values() if str(r.get("source", "")).startswith("arabic-")]
        added = sum(len(r.get("arabic_pass_added") or []) for r in done)
        total_done += len(done)
        total += len(dictionary["records"])
        print(f"{len(done):>6}/{len(dictionary['records']):<6} +{added:<6} {dictionary_name(dictionary)}")
    print(f"total {total_done}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--dictionary", action="append")
    run.add_argument("--limit", type=int)
    run.add_argument("--workers", type=int, default=8)
    run.add_argument("--votes", type=int, choices=[1, 2], default=2,
                     help="2 = keep only forms both generations propose (strict); 1 = either generation")
    run.add_argument("--min-sim", type=float, default=None,
                     help="reject forms whose EmbeddingGemma similarity to the term is below this (default: log only)")
    run.add_argument("--dry-run", action="store_true",
                     help="pilot: write the audit to variants/raw/arabic_auto/pilot-<id>.jsonl only, change nothing")
    run.add_argument("--no-semantic", action="store_true", help="skip the EmbeddingGemma check")
    run.set_defaults(handler=cmd_run)
    commands.add_parser("status").set_defaults(handler=cmd_status)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
