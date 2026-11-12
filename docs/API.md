# Kass API — guide for a system that uses Kass (written for linking Kass to Saleem)

Kass finds non-standard ways of writing a specialist term in Arabic text (المودل، الداتا، عميل ذكي) and proposes the
standard SIWAR dictionary term (نموذج، بيانات، وكيل ذكي). It also finds one concept written in several forms in the same
text and lets the writer unify them. Kass only **proposes**: nothing in the text changes unless the writer chooses it.

- Code: `src/kass_layer/detector/` — `engine.py` (detection), `unify.py` (term unification), `api.py` (FastAPI).
- Data: `demo_local/` (`index.json`, `context.json`, `senses.txt`, ...), built by `scripts/demo/build_*.py`.
  Point `KASS_DATA_DIR` elsewhere to use another copy.
- Cost: CPU only, no language model at query time. ~1.2 s to load once, ~200 MB RAM. A 300-word page: ~23 ms for
  `/analyse`, ~41 ms for `/unify` (`reports/presentation/speed/`).
- Live: https://kass.arai.center (the page at `/`, the API on the same host). Interactive docs: `/docs`.

## Run it
```
pip install -r requirements-api.txt
uvicorn kass_layer.detector.api:app --app-dir src --port 8000
```
Or the container: `Dockerfile` + `deploy/docker-compose.yml` (set `KASS_SERVE_PAGE=1` to also serve the page).
CORS is open to every origin (GET, POST). Texts are limited to 5,000 characters.

## Endpoints

### `GET /domains`
The domains the writer can choose (`tech`, `legal`, `finance`, `media`, `eng`, `culture`, ...) with their dictionaries.
The domain decides which dictionaries are searched. Ask the writer, or keep one per document type.

### `POST /analyse` — term suggestions
Request: `{"text": "درّبنا المودل على الداتا", "domain": "tech"}`

Response (main fields):
- `items[]`: one per term found, in text order.
  - `original`, `start`, `end`: the words as written and their position (character offsets in `text`).
  - `state`: `replace` (confident: propose it), `review` (possible: the writer must check), `std` (already the standard
    term; nothing to do).
  - `suggestion`: the best term: `term`, `replacement` (the term as it should be written **at that place**, with the
    writer's و/ب/ال and pronoun endings carried over: «بالمودل» → «بالنموذج»), `dictionary`, `english`, `definition`.
  - `choices[]`: up to 6 terms in the same shape (the first is the suggestion). Show them as a menu, plus «keep my word».
  - `reasons[]`: why a `review` item needs checking (shown to the writer).
- `unknown[]`: borrowed-looking words with no term in this domain (to check by hand, or try another domain).
- `suggested_text`: the text with only the `replace` items replaced. Convenience; a UI should let the writer choose.

To apply the writer's choices: replace `text[start:end]` with the chosen `choices[k].replacement`, working from the last
item to the first so the offsets stay valid.

### `POST /unify` — one concept, one form
Same request as `/analyse`. Response `groups[]`, one per concept written in two or more forms:
- `kind`: `dictionary` (the dictionaries link the forms to one term) or `spelling` (spellings of one borrowed word that
  no dictionary has, like الدرايف / Drive).
- `keep`: the suggested form: the SIWAR term for `dictionary`, the most frequent form for `spelling`.
- `review`: true when the writer should check before unifying (always true for `spelling`).
- `forms[]`: each form as written, with `count` and `standard` (already the term).
- `options[]`: **the forms the writer may choose to keep**, the suggested one first.
- `uses[]`: every place the concept occurs: `text`, `start`, `end`, and `replacements` = `{option: text to write
  here}` for every option (each place keeps its own و/ب/ال).

**The writer decides** (the page does exactly this, `scripts/demo/kass-lab.html`, function `drawUnify`):
1. Show `options` as a choice; preselect `keep` and say why (the standard term, or the most frequent form).
2. Let the writer choose «every place» or tick the places they want (show each use with a few words around it).
3. On «unify», write `use.replacements[chosen]` at `use.start:use.end` for the chosen uses that differ from the text.
4. Offer undo. Never unify without the writer asking.

Example: «درّبنا المودل … الموديل الجديد بالنموذج القديم» → `options` `["نموذج", "مودل", "موديل"]`; keeping «مودل»
writes «المودل … المودل الجديد بالمودل القديم».

### `POST /agree` (optional) and `GET /agree/status`
After the writer inserted terms, a language model can fix number and gender around them
(«النموذج الكبيرة» → «النماذج الكبيرة»). Off unless `KASS_AGREE_URL` (an OpenAI-compatible endpoint) is set; check
`/agree/status` first. See `src/kass_layer/agreement.py`.

### `GET /health`
`{"ok", "senses", "dictionaries", "context", "vectors"}`.

## Rules the integration must keep
- Suggestions only: no automatic replacement. `review` items and every unification need the writer's decision.
- Show where a term comes from (`dictionary`) and its `definition` when the writer hesitates.
- Do not send texts to outside services for Kass: everything runs on the Kass server.

## Tests
`pytest -q tests/test_detector_api.py` covers the endpoints, including the writer's choice in `/unify`.
