"""Agreement step: after the user has put SIWAR terms into the text, a language model fixes number and gender
(singular, dual, plural, masculine, feminine) of the inserted term and of the words that agree with it.

«درّبنا المودلز الكبيرة» → the user picks «نموذج» → «درّبنا النموذج الكبيرة» → the model → «درّبنا النماذج الكبيرة».

The model never chooses or replaces a term and never rewrites the sentence. A guard checks every answer and keeps the
user's text whenever the model changed anything else: another word, the number of words, or the inserted term itself.

The model is any OpenAI-compatible chat endpoint (the company model, vLLM, Ollama, ...), configured by the environment:
  KASS_AGREE_URL    base URL ending in /v1          (unset: the step is off and /agree answers 503)
  KASS_AGREE_KEY    API key (optional for a local server)
  KASS_AGREE_MODEL  model name
  KASS_AGREE_TIMEOUT seconds (default 30)
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass

from .detector.engine import bare, normalize

OPEN, CLOSE = "⟦", "⟧"
WINDOW = 3  # words on each side of an inserted term that may change to agree with it

SYSTEM = (
    "أنت مدقق صرفي للغة العربية. ستصلك جملة أُدرج فيها مصطلح أو أكثر بين العلامتين ⟦ و⟧، ومع كل مصطلح الكلمة التي كتبها "
    "المستخدم في مكانه.\n"
    "مهمتك الوحيدة: ضبط الإفراد والتثنية والجمع والتذكير والتأنيث في المصطلح المُدرج وفي الكلمات المرتبطة به نحويًّا "
    "(الصفة، الفعل، اسم الإشارة، الضمير)، بحيث يطابق عدد الكلمة الأصلية وجنسها وتستقيم الجملة.\n"
    "ممنوع: تغيير أي كلمة أخرى، أو استبدال المصطلح بمرادف، أو إعادة الصياغة، أو إضافة كلمات أو حذفها، أو تغيير الترقيم.\n"
    "إذا كانت الجملة صحيحة فأعدها كما هي.\n"
    'أعد JSON فقط بهذا الشكل: {"text": "الجملة بعد الضبط من دون العلامتين"}'
)


@dataclass
class Replacement:
    start: int      # position of the inserted term in the text the user sees
    end: int
    original: str   # what the user had written there (المودلز)
    term: str       # the SIWAR term as inserted (النموذج)


def configured() -> bool:
    return bool(os.environ.get("KASS_AGREE_URL"))


def marked(text: str, reps: list[Replacement]) -> str:
    out, pos = [], 0
    for r in sorted(reps, key=lambda r: r.start):
        out += [text[pos:r.start], OPEN, text[r.start:r.end], CLOSE]
        pos = r.end
    return "".join(out + [text[pos:]])


def prompt(text: str, reps: list[Replacement]) -> str:
    lines = [f"الجملة: {marked(text, reps)}", "المصطلحات المُدرجة:"]
    lines += [f"- «{r.term}» في مكان «{r.original}»" for r in sorted(reps, key=lambda r: r.start)]
    return "\n".join(lines)


def ask(text: str, reps: list[Replacement]) -> str:
    """The model's sentence (markers removed). Raises on network or format errors."""
    base = os.environ["KASS_AGREE_URL"].rstrip("/")
    body = {"model": os.environ.get("KASS_AGREE_MODEL", ""), "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt(text, reps)}],
            "response_format": {"type": "json_object"}}
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json"})
    if os.environ.get("KASS_AGREE_KEY"):
        req.add_header("Authorization", "Bearer " + os.environ["KASS_AGREE_KEY"])
    with urllib.request.urlopen(req, timeout=float(os.environ.get("KASS_AGREE_TIMEOUT", "30"))) as resp:
        content = json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    answer = json.loads(m.group(0))["text"] if m else content
    return answer.replace(OPEN, "").replace(CLOSE, "").strip()


def _core(w: str) -> str:
    w = normalize(w)
    w = re.sub("^[وفبلك](?=ال)", "", w)
    return bare(w)


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def same_word(a: str, b: str) -> bool:
    """Another form of the same word (نموذج/نماذج، الكبيرة/الكبير، ذكي/ذكية/أذكياء), not a different word."""
    x, y = _core(a), _core(b)
    if x == y:
        return True
    if not x or not y:
        return False
    return _lev(x, y) <= max(2, (max(len(x), len(y)) + 1) // 2) and (x[0] == y[0] or x[-1] == y[-1] or x[:2] in y or y[:2] in x)


def guard(text: str, reps: list[Replacement], answer: str) -> str | None:
    """None if the answer only changed the inserted terms and the words that agree with them; else the reason."""
    before, after = text.split(), answer.split()
    if len(before) != len(after):
        return "تغيّر عدد الكلمات"
    # word index of every character, to find which words the terms cover
    starts, pos = [], 0
    for w in before:
        pos = text.index(w, pos)
        starts.append((pos, pos + len(w)))
        pos += len(w)
    covered = {i for i, (s, e) in enumerate(starts) for r in reps if s < r.end and e > r.start}
    near = {j for i in covered for j in range(i - WINDOW, i + WINDOW + 1)}
    for i, (b, a) in enumerate(zip(before, after)):
        if b == a:
            continue
        if i not in near:
            return f"غيّر كلمة بعيدة عن المصطلح: «{b}» ← «{a}»"
        if not same_word(b, a):
            return f"استبدل كلمة بكلمة أخرى: «{b}» ← «{a}»"
    return None


def agree(text: str, reps: list[Replacement], ask_fn=ask) -> dict:
    """The adjusted text and what happened. On any error or guard refusal the user's text comes back unchanged."""
    if not reps:
        return {"text": text, "changed": False, "accepted": True, "reason": None}
    try:
        answer = ask_fn(text, reps)
    except Exception as e:  # network, timeout, bad JSON: keep the user's text
        return {"text": text, "changed": False, "accepted": False, "reason": f"تعذّر الوصول إلى النموذج ({type(e).__name__})"}
    reason = guard(text, reps, answer)
    if reason:
        return {"text": text, "changed": False, "accepted": False, "reason": reason, "rejected": answer}
    return {"text": answer, "changed": answer != text, "accepted": True, "reason": None}
