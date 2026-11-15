"""Kass client for Saleem: one file, Python standard library only (copy it into the Saleem repository as is).

Kass proposes standard SIWAR terms; it never changes text by itself. Saleem can use it in two ways:
  1. Writer's tool: show `analyse()` / `unify()` results and apply only what the writer picks (`apply_choices`).
  2. Rewrite context: `terminology_context()` turns Kass's findings into a short block of terms and definitions
     to put in Saleem's rewrite prompt, so the model writes the standard terms.

Server: KASS_URL (default http://localhost:8000). Start it from the Kass repository:
  uvicorn kass_layer.detector.api:app --app-dir src --port 8000
Try it:
  python kass_client.py "درّبنا المودل على الداتا" --domain tech
"""
import json
import os
import sys
import urllib.request

KASS_URL = os.environ.get("KASS_URL", "http://localhost:8000").rstrip("/")


def _call(path, body=None, timeout=30):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(KASS_URL + path, data=data, headers={"Content-Type": "application/json"},
                                 method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def health():
    return _call("/health")


def domains():
    """Domains the writer can choose (tech, legal, finance, ...); the domain decides which dictionaries are searched."""
    return _call("/domains")


def analyse(text, domain="tech"):
    """Term suggestions: items[] with state replace / review / std, suggestion, choices, positions."""
    return _call("/analyse", {"text": text, "domain": domain})


def unify(text, domain="tech"):
    """Concepts written in several forms in the same text: groups[] with options and uses."""
    return _call("/unify", {"text": text, "domain": domain})


def apply_choices(text, analysis, picks):
    """Applies the writer's picks. picks = {item index: choice index}; items not in picks stay as written.
    Works from the last item to the first so the offsets stay valid."""
    items = analysis["items"]
    for i in sorted(picks, reverse=True):
        it = items[i]
        if it["state"] == "std":
            continue
        text = text[:it["start"]] + it["choices"][picks[i]]["replacement"] + text[it["end"]:]
    return text


def apply_unify(text, group, keep, uses=None):
    """Unifies one group on the form `keep` (one of group["options"]); uses = indexes of the places to change
    (None = every place). Only call this when the writer asked for it."""
    chosen = [u for k, u in enumerate(group["uses"]) if uses is None or k in uses]
    for u in sorted(chosen, key=lambda u: u["start"], reverse=True):
        new = u["replacements"][keep]
        if new != u["text"]:
            text = text[:u["start"]] + new + text[u["end"]:]
    return text


def terminology_context(analysis, include_review=True, max_items=20):
    """Short Arabic block of the terms Kass found, for Saleem's rewrite prompt.
    `replace` items are confident; `review` items are marked as needing a check from context."""
    lines, seen = [], set()
    for it in analysis["items"]:
        if it["state"] == "std" or (it["state"] == "review" and not include_review):
            continue
        s = it["suggestion"]
        key = (it["original"], s["term"])
        if key in seen:
            continue
        seen.add(key)
        line = f"- «{it['original']}» ← المصطلح المعتمد «{s['term']}»"
        if s.get("english"):
            line += f" ({s['english']})"
        if s.get("definition"):
            line += f": {s['definition']}"
        if it["state"] == "review":
            others = [c["term"] for c in it["choices"][1:4]]
            line += " [يحتاج تحققًا من السياق" + (f"؛ بدائل: {'، '.join(others)}" if others else "") + "]"
        lines.append(line)
        if len(lines) >= max_items:
            break
    if not lines:
        return ""
    return "مصطلحات معتمدة من معاجم سوار (اقتراحات خصص):\n" + "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    dom = "tech"
    if "--domain" in args:
        k = args.index("--domain")
        dom = args[k + 1]
        del args[k:k + 2]
    txt = " ".join(args) or "درّبنا المودل على الداتا ثم رفعنا الموديل على السيرفر"
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a = analyse(txt, dom)
    for it in a["items"]:
        print(it["state"], it["original"], "->", (it["suggestion"] or {}).get("replacement"))
    print("\nsuggested_text:", a["suggested_text"])
    print("\n" + terminology_context(a))
    for g in unify(txt, dom)["groups"]:
        print("\nunify:", g["kind"], g["options"], "keep:", g["keep"], "->", apply_unify(txt, g, g["keep"]))
