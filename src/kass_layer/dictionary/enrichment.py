"""Two-stage vocabulary enrichment for completed dictionaries.

Stage 1 (generate, open model): Qwen proposes, for every dictionary sense, the other ways Arabic writers
refer to the same concept (transliterations, English forms, informal synonyms, dialect and spelling variants).
Stage 2 (review, Claude): Claude checks every sense against Qwen's proposal, keeps, corrects or drops each
form, and adds forms Qwen missed. Deterministic checks then flag collisions across all dictionaries.

Layout under data/dictionaries/enriched/variants/:
  raw/qwen/<dictionary_id>.jsonl           stage-1 output, one line per sense, append-only
  raw/claude_review/<dictionary_id>.jsonl  stage-2 output, one line per sense, append-only
  <dictionary_id>.variants.jsonl           validated variants per generated sense (built by ``finalize``)
  state.json                               Claude batches and token usage
  report.json                              counts, review queue, usage
Deliverable, one per dictionary, next to the variants working area:
  data/dictionaries/enriched/<dictionary_id>.enriched.json   the export's records unchanged, each with an
                                                              ``enrichment`` block holding the reviewed variants
Each raw line carries a hash of its inputs and prompt version, so changed inputs or prompts are redone
and unchanged ones are skipped. Sources are never modified.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
EXPORT_DIR = ROOT / "data" / "dictionaries" / "exports"
ENRICHED_DIR = ROOT / "data" / "dictionaries" / "enriched"
OUT_DIR = ENRICHED_DIR / "variants"
GENERATION_DIR = OUT_DIR / "raw" / "generation"  # stage-1 output from Qwen or ChatGPT; each row names its model
QWEN_DIR = GENERATION_DIR  # backwards-compatible name
CHATGPT_DIR = OUT_DIR / "chatgpt"  # inputs/ pushed for ChatGPT, outputs/ returned by it
REVIEW_DIR = OUT_DIR / "raw" / "claude_review"
STATE_PATH = OUT_DIR / "state.json"
EXCLUDED_DICTIONARIES = {"Riyadh"}  # general-language dictionary, not specialised terminology

GENERATION_PROMPT_VERSION = "3"
CHATGPT_PROMPT_VERSION = "chatgpt-1"
CHATGPT_PART_SIZE = 200
REVIEW_PROMPT_VERSION = "1"
DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
DEFAULT_CLAUDE_EFFORT = "high"
AUTO_ARABIC_TRUSTED = False  # set True once an audit of the arabic_auto pass shows acceptable precision
QWEN_CHUNK_SIZE = 5
REVIEW_CHUNK_SIZE = 15
MAX_TOKENS = 16000
VARIANT_TYPES = ["transliteration", "foreign", "abbreviation", "informal_synonym", "colloquial", "spelling_variant"]
ARABIC_TYPES = {"transliteration", "informal_synonym", "colloquial", "spelling_variant"}

_TASK = """The terminology layer finds non-standard wording in ordinary Arabic text and replaces it with the standard dictionary term, for example «المودل تدرب على بيانات وحقق نتائج جيدة» becomes «النموذج تدرب على بيانات وحقق نتائج جيدة». It needs, for each standard term, the other ways Arabic writers actually refer to the same concept in real text: news, social media, reports, workplace and student writing.

Variant types:
- transliteration: the English or other foreign word written in Arabic letters (مودل، داتا، كاش فلو، ترند، بودكاست).
- foreign: the English word or acronym written in Latin letters inside Arabic text (model, cash flow, KPI).
- abbreviation: a shortened form or acronym used in Arabic writing.
- informal_synonym: a non-standard Arabic wording in common use for the same concept, such as a literal translation, an older term or a regional term.
- colloquial: a Saudi, Gulf or widely used dialect form.
- spelling_variant: a common alternative spelling of the term itself (hamza, taa marbuta, alif maqsura, joined or separated words).

Rules for a valid variant:
1. Real usage only. Arabic writers must really use the form for this concept. Never invent forms. An empty list is the right answer for many terms, especially long multi-word technical terms that nobody rephrases.
2. Same concept only: not a broader, narrower or related concept. If the form's usual meaning has its own standard term, it is not a variant.
3. Base form only: no plurals, duals, added definite article ال, possessive suffixes or verb conjugations; a later stage handles inflection. Match the grammatical form of the term.
4. Not the standard term itself, and not a difference in diacritics only.
5. foreign: the English term as people commonly write it; an English acronym only when the acronym itself is common.
6. ambiguous is true when the form also commonly means something unrelated in everyday text (for example موديل also means a fashion model or a car's model year); ambiguity_note then says briefly in Arabic when the form does not refer to this term, otherwise it is empty.
7. example: one short, natural Arabic sentence, as a non-specialist would write it, using the form with this meaning.
8. confidence: high when the form is very common, medium when it is used but less common, low when it is rare."""

GENERATION_PROMPT = f"""You enrich Arabic specialised-terminology dictionaries for a rewriting layer.

{_TASK}

You are the first, recall-oriented stage: propose candidate variants generously, and a careful reviewer will remove the wrong ones afterwards. Missing a real variant is worse than proposing a doubtful one; mark doubtful ones with confidence "low".

For each term, go through this checklist:
- Is the English equivalent (or its acronym, e.g. RPA, AI, KPI) written in Latin letters inside Arabic text? Add it as foreign.
- Do people write the English word in Arabic letters (e.g. داتا، مودل، بيغ داتا، تورينج تست)? Add it as transliteration.
- Is there a looser Arabic wording, an older or literal translation, or a dialect form people use for it? Add it.
- Is the term itself often spelled differently? Add it as spelling_variant.
Still follow rules 3 and 4: no plurals, no added ال, never the standard term itself.

Reply with JSON only, no explanations, in exactly this shape and with exactly these field names:
{{"items": [
  {{"index": 1, "variants": [
    {{"form": "مودل", "type": "transliteration", "confidence": "high", "ambiguous": false, "ambiguity_note": "", "example": "درّبنا المودل على بيانات العملاء."}},
    {{"form": "model", "type": "foreign", "confidence": "high", "ambiguous": false, "ambiguity_note": "", "example": "الـ model أعطى نتائج ممتازة."}}
  ]}},
  {{"index": 2, "variants": []}}
]}}
type is one of: transliteration (Arabic letters only), foreign (Latin letters only), abbreviation, informal_synonym, colloquial, spelling_variant. Return one item for every input index."""

REVIEW_PROMPT = f"""You are the quality reviewer for an Arabic terminology-enrichment dataset. A small open model proposed variants for each standard term; your output is the final, trusted list.

{_TASK}

For each input term, decide the final list of variants:
- keep a proposed form that satisfies every rule (action "kept"), correcting its type, confidence, ambiguity or example if needed;
- fix a proposed form that is right in substance but wrong in spelling or inflection, for example remove an added ال or a plural (action "corrected", original_form = the proposed form);
- add a valid variant the model missed only when you are confident it is in common use (action "added");
- drop everything else and give the reason in dropped: invented, not_used, different_concept, inflected, same_as_term, wrong_meaning or other.
For kept and added forms, original_form is the empty string. Return one item for every input index."""

_VARIANT_PROPERTIES = {
    "form": {"type": "string"},
    "type": {"type": "string", "enum": VARIANT_TYPES},
    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    "ambiguous": {"type": "boolean"},
    "ambiguity_note": {"type": "string"},
    "example": {"type": "string"},
}


def _items_schema(variant_properties: dict[str, Any], extra_item_properties: dict[str, Any]) -> dict[str, Any]:
    variant = {"type": "object", "properties": variant_properties,
               "required": list(variant_properties), "additionalProperties": False}
    item_properties = {"index": {"type": "integer"}, "variants": {"type": "array", "items": variant},
                       **extra_item_properties}
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {
            "type": "object", "properties": item_properties,
            "required": list(item_properties), "additionalProperties": False}}},
        "required": ["items"],
        "additionalProperties": False,
    }


GENERATION_SCHEMA = _items_schema(_VARIANT_PROPERTIES, {})
REVIEW_SCHEMA = _items_schema(
    {**_VARIANT_PROPERTIES,
     "action": {"type": "string", "enum": ["kept", "corrected", "added"]},
     "original_form": {"type": "string"}},
    {"dropped": {"type": "array", "items": {
        "type": "object",
        "properties": {"form": {"type": "string"}, "reason": {"type": "string", "enum": [
            "invented", "not_used", "different_concept", "inflected", "same_as_term", "wrong_meaning", "other"]}},
        "required": ["form", "reason"], "additionalProperties": False}}},
)


# --------------------------------------------------------------------------- io helpers


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"batches": {}, "sync_usage": []}


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Load ANTHROPIC_* and QWEN_* keys from .env without overriding the environment or printing them."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key.startswith(("ANTHROPIC_", "QWEN_")) and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


# --------------------------------------------------------------------------- sources


def dictionary_name(dictionary: dict[str, Any]) -> str:
    return " ".join(str(dictionary.get("dictionary_name", "")).split())


def complete_dictionaries(export_dir: Path = EXPORT_DIR) -> list[dict[str, Any]]:
    dictionaries = []
    for path in sorted(export_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") == "complete" and payload.get("dictionary_id") not in EXCLUDED_DICTIONARIES:
            dictionaries.append(payload)
    return dictionaries


def term_input(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "term": record.get("term_without_diacritics") or record["term"],
        "definition": (record.get("definition") or "").strip(),
        "english": record.get("english_term") or "",
    }


def _sha256(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def generation_hash(record: dict[str, Any], name: str, prompt_version: str = GENERATION_PROMPT_VERSION) -> str:
    return _sha256({"prompt_version": prompt_version, "dictionary": name, **term_input(record)})


def review_hash(generation_row: dict[str, Any]) -> str:
    return _sha256({"prompt_version": REVIEW_PROMPT_VERSION, "generation": generation_row["input_sha256"],
                    "proposed": generation_row["variants"]})


def latest_rows(path: Path, current_hashes: dict[str, str | set[str]]) -> dict[str, dict[str, Any]]:
    """Latest row per sense whose input hash still matches ``current_hashes`` (one hash or a set)."""
    latest: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        expected = current_hashes.get(row["sense_id"])
        if row["input_sha256"] == expected or (isinstance(expected, set) and row["input_sha256"] in expected):
            latest[row["sense_id"]] = row
    return latest


def current_generations(dictionary: dict[str, Any], qwen_dir: Path = QWEN_DIR) -> dict[str, dict[str, Any]]:
    name = dictionary_name(dictionary)
    hashes = {record["sense_id"]: {generation_hash(record, name, version)
                                   for version in (GENERATION_PROMPT_VERSION, CHATGPT_PROMPT_VERSION)}
              for record in dictionary["records"]}
    return latest_rows(qwen_dir / f"{dictionary['dictionary_id']}.jsonl", hashes)


def current_reviews(dictionary: dict[str, Any], generations: dict[str, dict[str, Any]],
                    review_dir: Path = REVIEW_DIR) -> dict[str, dict[str, Any]]:
    hashes = {sense_id: review_hash(row) for sense_id, row in generations.items()}
    return latest_rows(review_dir / f"{dictionary['dictionary_id']}.jsonl", hashes)


def pending_generation(dictionary: dict[str, Any], qwen_dir: Path = QWEN_DIR) -> list[dict[str, Any]]:
    done = current_generations(dictionary, qwen_dir)
    return [record for record in dictionary["records"] if record["sense_id"] not in done]


def pending_review(dictionary: dict[str, Any], qwen_dir: Path = QWEN_DIR, review_dir: Path = REVIEW_DIR,
                   in_flight: set[str] = frozenset()) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(record, generation row) pairs that Qwen has done and Claude has not reviewed yet."""
    generations = current_generations(dictionary, qwen_dir)
    reviewed = current_reviews(dictionary, generations, review_dir)
    return [
        (record, generations[record["sense_id"]]) for record in dictionary["records"]
        if record["sense_id"] in generations and record["sense_id"] not in reviewed
        and record["sense_id"] not in in_flight
    ]


def chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[start:start + size] for start in range(0, len(items), size)]


# --------------------------------------------------------------------------- prompts


def generation_messages(name: str, chunk: list[dict[str, Any]]) -> list[dict[str, str]]:
    terms = [{"index": index, **term_input(record)} for index, record in enumerate(chunk, start=1)]
    content = (f"Dictionary: {name}\n\nTerms (JSON, one per line):\n"
               + "\n".join(json.dumps(term, ensure_ascii=False) for term in terms))
    return [{"role": "system", "content": GENERATION_PROMPT}, {"role": "user", "content": content}]


def review_params(name: str, pairs: list[tuple[dict[str, Any], dict[str, Any]]], model: str, effort: str) -> dict[str, Any]:
    terms = [
        {"index": index, **term_input(record),
         "proposed": [{k: v.get(k) for k in ("form", "type", "confidence", "ambiguous", "example")}
                      for v in generation["variants"]]}
        for index, (record, generation) in enumerate(pairs, start=1)
    ]
    content = (f"Dictionary: {name}\n\nTerms with the open model's proposals (JSON, one per line):\n"
               + "\n".join(json.dumps(term, ensure_ascii=False) for term in terms))
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": REVIEW_PROMPT,
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
        "messages": [{"role": "user", "content": content}],
    }


# --------------------------------------------------------------------------- parsing model output


_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def extract_json(text: str) -> Any:
    """Parse a JSON object or array from model text, tolerating <think> blocks and code fences."""
    text = _THINK.sub("", text or "").strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise json.JSONDecodeError("no JSON found", text, 0)
    start = min(starts)
    end = text.rfind("}" if text[start] == "{" else "]")
    if end <= start:
        raise json.JSONDecodeError("no JSON found", text, 0)
    return json.loads(text[start:end + 1])


_FIELD_ALIASES = {"variant_type": "type", "ambiguous_note": "ambiguity_note", "variant": "form"}


def parse_items(payload: Any, chunk_size: int) -> dict[int, dict[str, Any]]:
    """Map 1-based input index -> item. Indices outside the chunk and repeats are ignored.

    Accepts {"items": [...]} or a bare list, and common field-name slips from smaller models.
    """
    items = payload.get("items", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    parsed: dict[int, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("variants"), list):
            item = {**item, "variants": [
                {_FIELD_ALIASES.get(k, k): v for k, v in variant.items()} if isinstance(variant, dict) else variant
                for variant in item["variants"]]}
        index = item.get("index") if isinstance(item, dict) else None
        if isinstance(index, int) and 1 <= index <= chunk_size and index not in parsed:
            parsed[index] = item
    return parsed


def _clean_variants(variants: Any) -> list[dict[str, Any]]:
    cleaned = []
    for variant in variants if isinstance(variants, list) else []:
        if not isinstance(variant, dict) or not str(variant.get("form", "")).strip():
            continue
        cleaned.append({
            "form": " ".join(str(variant["form"]).split()),
            "type": variant.get("type") if variant.get("type") in VARIANT_TYPES else None,
            "confidence": variant.get("confidence") if variant.get("confidence") in {"high", "medium", "low"} else "low",
            "ambiguous": bool(variant.get("ambiguous")),
            "ambiguity_note": str(variant.get("ambiguity_note") or ""),
            "example": str(variant.get("example") or ""),
            **({"action": variant["action"], "original_form": variant.get("original_form") or ""}
               if "action" in variant else {}),
        })
    return cleaned


def generation_rows(dictionary: dict[str, Any], chunk: list[dict[str, Any]], parsed: dict[int, dict[str, Any]],
                    model: str, prompt_version: str = GENERATION_PROMPT_VERSION) -> list[dict[str, Any]]:
    name = dictionary_name(dictionary)
    now = datetime.now(timezone.utc).isoformat()
    return [
        {"sense_id": record["sense_id"], "entry_id": record.get("entry_id"), "dictionary_id": dictionary["dictionary_id"],
         "term": record["term"], "variants": _clean_variants(parsed[index].get("variants")), "model": model,
         "prompt_version": prompt_version, "input_sha256": generation_hash(record, name, prompt_version),
         "generated_at": now}
        for index, record in enumerate(chunk, start=1) if index in parsed
    ]


def review_rows(dictionary: dict[str, Any], pairs: list[tuple[dict[str, Any], dict[str, Any]]],
                parsed: dict[int, dict[str, Any]], model: str, source: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for index, (record, generation) in enumerate(pairs, start=1):
        if index not in parsed:
            continue
        dropped = [d for d in parsed[index].get("dropped") or [] if isinstance(d, dict)]
        rows.append({"sense_id": record["sense_id"], "entry_id": record.get("entry_id"),
                     "dictionary_id": dictionary["dictionary_id"], "term": record["term"],
                     "variants": _clean_variants(parsed[index].get("variants")), "dropped_by_reviewer": dropped,
                     "model": model, "prompt_version": REVIEW_PROMPT_VERSION, "input_sha256": review_hash(generation),
                     "source": source, "reviewed_at": now})
    return rows


# --------------------------------------------------------------------------- ChatGPT hand-off


CHATGPT_PROMPT = """You are enriching an Arabic specialised-terminology dictionary for a rewriting layer.

""" + _TASK + """

Input: the JSONL file at the link below. Each line is one dictionary sense with sense_id, term, definition and english.

For every input line, list the term's valid variants. Aim for both: include every form you are confident Arabic writers really use (English words and acronyms in Latin letters, English words in Arabic letters, looser Arabic wordings, dialect and spelling variants), and never invent forms. An empty list is correct when nobody rephrases the term.

Output: a downloadable file named exactly like the input file, in JSONL (one JSON object per line, UTF-8, no markdown), with exactly one line per input line, in the same order, never skipping a line:
{"sense_id": "<copied unchanged from the input>", "variants": [{"form": "مودل", "type": "transliteration", "confidence": "high", "ambiguous": false, "ambiguity_note": "", "example": "درّبنا المودل على بيانات العملاء."}]}
type is one of transliteration (Arabic letters), foreign (Latin letters), abbreviation, informal_synonym, colloquial, spelling_variant. confidence is high, medium or low. Use exactly these field names. Process the whole file; if it is long, work through it in parts but return one complete file."""


def chatgpt_parts(dictionary: dict[str, Any], part_size: int = CHATGPT_PART_SIZE) -> list[list[dict[str, Any]]]:
    return chunks(dictionary["records"], part_size)


def chatgpt_input_lines(part: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"sense_id": record["sense_id"], **term_input(record)} for record in part]


def import_chatgpt_part(dictionary: dict[str, Any], part: list[dict[str, Any]], output_path: Path,
                        model: str = "chatgpt") -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Turn one ChatGPT output file into generation rows. Lines are matched by sense_id, never by position."""
    expected = {record["sense_id"]: record for record in part}
    parsed_by_sense: dict[str, dict[str, Any]] = {}
    problems: Counter = Counter()
    for line in output_path.read_text(encoding="utf-8").splitlines():
        line = line.strip().strip(",")
        if not line or line.startswith("```"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            problems["unparseable_lines"] += 1
            continue
        sense_id = item.get("sense_id") if isinstance(item, dict) else None
        if sense_id not in expected:
            problems["unknown_sense_id"] += 1
        elif sense_id in parsed_by_sense:
            problems["repeated_sense_id"] += 1
        else:
            parsed_by_sense[sense_id] = parse_items([{"index": 1, "variants": item.get("variants") or []}], 1)[1]
    chunk = [expected[sense_id] for sense_id in expected if sense_id in parsed_by_sense]
    rows = generation_rows(dictionary, chunk, {i: parsed_by_sense[r["sense_id"]] for i, r in enumerate(chunk, 1)},
                           model, CHATGPT_PROMPT_VERSION)
    problems["missing_senses"] = len(part) - len(rows)
    return rows, dict(problems)


# --------------------------------------------------------------------------- validation


_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")  # also invisible bidi/zero-width marks
_PUNCTUATION = re.compile(r"[\"'«»“”‘’()\[\]{}.,،؛:!?؟]")


def normalize(text: str) -> str:
    text = _DIACRITICS.sub("", text or "")
    text = re.sub("[أإآٱ]", "ا", text).replace("ى", "ي").replace("ة", "ه")
    text = _PUNCTUATION.sub(" ", text.lower())
    return " ".join(text.split())


def article_free_key(text: str) -> str:
    """Normalized key with a leading ال removed from each word.

    The article is stripped before hamza forms are unified, so a word that starts with إل/أل (إلكترونية)
    keeps its first letters, while الإلكترونية loses only its article.
    """
    words = _DIACRITICS.sub("", text or "").split()
    return normalize(" ".join(word[2:] if word.startswith("ال") and len(word) > 3 else word for word in words))


def _has_arabic(text: str) -> bool:
    return any("؀" <= char <= "ۿ" for char in text)


def _has_latin(text: str) -> bool:
    return any("a" <= char.lower() <= "z" for char in text)


def term_index(dictionaries: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Normalized standard term (with and without ال) -> entry ids across all completed dictionaries."""
    index: dict[str, set[str]] = defaultdict(set)
    for dictionary in dictionaries:
        for record in dictionary["records"]:
            key = normalize(record.get("term_without_diacritics") or record["term"])
            entry = record.get("entry_id") or record["sense_id"]
            index[key].add(entry)
            index[article_free_key(record.get("term_without_diacritics") or record["term"])].add(entry)
    return index


def validate(rows: list[dict[str, Any]], terms: dict[str, set[str]]) -> list[dict[str, Any]]:
    """Give each variant status accepted / review (with reasons), or drop it with a reason.

    Rows carry ``reviewed``: variants Claude has not reviewed are never accepted automatically.
    """
    proposals: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for variant in row["variants"]:
            proposals[normalize(variant.get("form", ""))].add(row.get("entry_id") or row["sense_id"])

    enriched = []
    for row in rows:
        entry = row.get("entry_id") or row["sense_id"]
        term_key = normalize(row["term"])
        seen: set[str] = set()
        kept, dropped = [], list(row.get("dropped_by_reviewer") or [])
        for variant in row["variants"]:
            form = variant["form"]
            key = normalize(form)
            kind = variant.get("type")
            if not key:
                dropped.append({"form": form, "reason": "empty"})
                continue
            if key == term_key or article_free_key(form) == article_free_key(row["term"]):
                dropped.append({"form": form, "reason": "same_as_term"})
                continue
            if key in seen:
                dropped.append({"form": form, "reason": "duplicate"})
                continue
            if any(_has_arabic(token) and _has_latin(token) for token in form.split()):
                dropped.append({"form": form, "reason": "mixed_script_word"})
                continue
            if kind is None or (kind in ARABIC_TYPES and not _has_arabic(form)) or (kind == "foreign" and not _has_latin(form)):
                dropped.append({"form": form, "reason": "script_does_not_match_type"})
                continue
            seen.add(key)

            reasons = []
            if not row.get("reviewed"):
                reasons.append("not_reviewed_by_claude")
            conflicts = sorted((terms.get(key, set()) | terms.get(article_free_key(form), set())) - {entry})
            if conflicts:
                reasons.append("is_standard_term_elsewhere")
            shared = sorted(proposals[key] - {entry})
            if shared:
                reasons.append("proposed_for_other_terms")
            if variant.get("ambiguous"):
                reasons.append("ambiguous")
            if variant.get("confidence") == "low":
                reasons.append("low_confidence")
            if variant.get("origin") == "arabic-auto" and not AUTO_ARABIC_TRUSTED:
                reasons.append("auto_added_unaudited")  # Qwen-only Arabic pass, until a precision audit clears it
            first_word, term_first = (key.split() or [""])[0], (term_key.split() or [""])[0]
            if (not row.get("reviewed") and kind in ARABIC_TYPES
                    and first_word.startswith("ال") and not term_first.startswith("ال")):
                reasons.append("has_definite_article")  # reviewers apply rule 3 themselves
            kept.append({**variant, "status": "review" if reasons else "accepted", "review_reasons": reasons,
                         "conflicting_entries": conflicts, "shared_with_entries": shared})
        enriched.append({"sense_id": row["sense_id"], "entry_id": row.get("entry_id"),
                         "dictionary_id": row["dictionary_id"], "term": row["term"],
                         "reviewed": bool(row.get("reviewed")), "generated_by": row.get("generated_by"),
                         "reviewed_by": row.get("reviewed_by"), "variants": kept, "dropped": dropped})
    return enriched


def merged_rows(dictionary: dict[str, Any], qwen_dir: Path = QWEN_DIR, review_dir: Path = REVIEW_DIR) -> list[dict[str, Any]]:
    """One row per generated sense: Claude's reviewed list when present, otherwise Qwen's proposal."""
    generations = current_generations(dictionary, qwen_dir)
    reviews = current_reviews(dictionary, generations, review_dir)
    rows = []
    for sense_id, generation in generations.items():
        review = reviews.get(sense_id)
        source = review or generation
        rows.append({**source, "reviewed": review is not None, "generated_by": generation["model"],
                     "reviewed_by": review["model"] if review else None})
    return rows


def write_enriched_dictionary(dictionary: dict[str, Any], records: list[dict[str, Any]], directory: Path) -> Path | None:
    """Write <dictionary_id>.enriched.json: the export unchanged plus an ``enrichment`` block per reviewed sense.

    Only reviewed senses carry variants; the source export file itself is never modified.
    """
    reviewed = {record["sense_id"]: record for record in records if record["reviewed"]}
    path = directory / f"{dictionary['dictionary_id']}.enriched.json"
    if not reviewed:
        path.unlink(missing_ok=True)
        return None
    enriched_records = []
    for source in dictionary["records"]:
        record = reviewed.get(source["sense_id"])
        enrichment = None
        if record is not None:
            enrichment = {
                "variants": [{k: v[k] for k in ("form", "type", "confidence", "ambiguous", "ambiguity_note", "example",
                                                "status", "review_reasons")} for v in record["variants"]],
                "generated_by": record["generated_by"],
                "reviewed_by": record["reviewed_by"],
            }
        enriched_records.append({**source, "enrichment": enrichment})
    variants = [v for record in reviewed.values() for v in record["variants"]]
    complete = len(reviewed) == len(dictionary["records"])
    write_json(path, {
        "dictionary_id": dictionary["dictionary_id"],
        "dictionary_name": dictionary_name(dictionary),
        "source_export": f"data/dictionaries/exports/{dictionary['dictionary_id']}.json",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "enrichment_status": "complete" if complete else "partial",
        "counts": {
            "senses": len(dictionary["records"]),
            "senses_reviewed": len(reviewed),
            "senses_with_variants": sum(bool(r["variants"]) for r in reviewed.values()),
            "variants_accepted": sum(v["status"] == "accepted" for v in variants),
            "variants_needing_review": sum(v["status"] == "review" for v in variants),
        },
        "variant_types": {"transliteration": "English/foreign word in Arabic letters",
                          "foreign": "English word or acronym in Latin letters",
                          "abbreviation": "shortened form", "informal_synonym": "non-standard Arabic wording",
                          "colloquial": "dialect form", "spelling_variant": "alternative spelling of the term"},
        "records": enriched_records,
    })
    return path


def finalize(dictionaries: list[dict[str, Any]], qwen_dir: Path = QWEN_DIR, review_dir: Path = REVIEW_DIR,
             out_dir: Path = OUT_DIR, state: dict[str, Any] | None = None,
             deliverable_dir: Path | None = None) -> dict[str, Any]:
    terms = term_index(dictionaries)
    rows_by_dictionary = {d["dictionary_id"]: merged_rows(d, qwen_dir, review_dir) for d in dictionaries}
    validated = {r["sense_id"]: r for r in validate([row for rows in rows_by_dictionary.values() for row in rows], terms)}

    per_dictionary, status_counts, type_counts, reasons, actions = {}, Counter(), Counter(), Counter(), Counter()
    for dictionary in dictionaries:
        dictionary_id = dictionary["dictionary_id"]
        records = [validated[row["sense_id"]] for row in rows_by_dictionary[dictionary_id]]
        path = out_dir / f"{dictionary_id}.variants.jsonl"
        path.unlink(missing_ok=True)
        if records:
            append_jsonl(path, records)
        write_enriched_dictionary(dictionary, records, deliverable_dir or out_dir.parent)
        variants = [v for record in records for v in record["variants"]]
        status_counts.update(v["status"] for v in variants)
        type_counts.update(v["type"] for v in variants)
        reasons.update(reason for v in variants for reason in v["review_reasons"])
        actions.update(v.get("action", "unreviewed") for v in variants)
        per_dictionary[dictionary_id] = {
            "dictionary_name": dictionary_name(dictionary),
            "senses": len(dictionary["records"]),
            "generated": len(records),
            "reviewed": sum(r["reviewed"] for r in records),
            "senses_with_variants": sum(bool(r["variants"]) for r in records),
            "variants_accepted": sum(v["status"] == "accepted" for v in variants),
            "variants_review": sum(v["status"] == "review" for v in variants),
            "variants_dropped": sum(len(r["dropped"]) for r in records),
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_versions": {"generation": GENERATION_PROMPT_VERSION, "review": REVIEW_PROMPT_VERSION},
        "totals": {
            "dictionaries": len(dictionaries),
            "senses": sum(d["senses"] for d in per_dictionary.values()),
            "generated": sum(d["generated"] for d in per_dictionary.values()),
            "reviewed": sum(d["reviewed"] for d in per_dictionary.values()),
            "variants_by_status": dict(status_counts),
            "variants_by_type": dict(type_counts),
            "reviewer_actions": dict(actions),
            "review_reasons": dict(reasons),
        },
        "claude_token_usage": usage_totals(state or load_state()),
        "dictionaries": per_dictionary,
    }
    write_json(out_dir / "report.json", report)
    return report


def usage_totals(state: dict[str, Any]) -> dict[str, int]:
    totals: Counter = Counter()
    for batch in state.get("batches", {}).values():
        totals.update(batch.get("usage", {}))
    for usage in state.get("sync_usage", []):
        totals.update(usage)
    return dict(totals)
