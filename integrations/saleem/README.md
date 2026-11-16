# Linking Kass to Saleem

`kass_client.py` is the only file Saleem needs (Python standard library, no packages). Copy it into the Saleem
repository on a new branch, never on `main`. The API it calls is described in `docs/API.md`.

1. Run the Kass server from this repository: `uvicorn kass_layer.detector.api:app --app-dir src --port 8000`
   (or the container in `deploy/`). Saleem points `KASS_URL` at it. The default is `http://localhost:8000`.
2. Check it: `python kass_client.py "درّبنا المودل على الداتا" --domain tech`.

The two ways to use it:
- **Writer's tool**: show `analyse()` and `unify()` results. Apply only what the writer picks, using
  `apply_choices()` and `apply_unify()`.
- **Rewrite context**: `terminology_context(analyse(text, domain))` gives an Arabic block of the terms Kass found,
  with their English equivalents and definitions. Saleem adds it to its rewrite prompt so the model writes the
  standard terms. Items in `review` are marked as needing a check from context.

Rules: Kass only proposes. Nothing is replaced unless the writer chooses it, or unless Saleem's rewrite step chooses
it from the context block. Texts stay on the Kass server and are never sent to outside services.

Riyadh dictionary: when it is added to Kass, this client does not change. Only the server data
(`demo_local/`) is rebuilt.

## In Saleem's web editor (through the gateway)

The web editor calls Kass directly from the browser through Saleem's gateway. The Python client is not used there.

| Saleem side | What it does |
|---|---|
| Gateway (`KSGAAL-DotNET`, `ocelot*.json`) | `POST /kass/analyse` → `/analyse` and `POST /kass/unify` → `/unify` on host `ksgaal-kass` port 8000 (`127.0.0.1:8000` in Development). Authenticated like the other NLP tools. No other Kass path is exposed: no `/agree`, no page. |
| Web UI (`KSGAAL-UI`, `features/editor/kass-terms`) | While the writer types, sends the editor text and the document's المجال المعرفي, mapped to a Kass domain. Shows term cards and unify cards under «تصحيح كل الأخطاء» and underlines the words. Writes only what the writer picks. |
| Lookup (`KnowledgeDomain`) | The knowledge-domain list is the Kass domain list. |

Settings for the Kass container beside Saleem:

| Variable | Value for Saleem | Why |
|---|---|---|
| `KASS_MAX_CHARS` | e.g. `50000` | A Saleem document can be longer than the default limit of 5,000 characters. Above the limit Kass answers 422 and the editor shows no Kass suggestions. |
| `KASS_CORS_ORIGINS` | the gateway's origin | The browser never calls Kass directly. The default is any origin. |
| `KASS_AGREE_URL` | **unset** | `/agree` would send text to a language model. It is not routed, so keep it off. |

Domain ids the editor sends (`kassDomainFor` in the UI): `legal`, `tech`, `finance`, `media`, `eng`, `culture`,
`linguistics` (لغوي وأدبي), `heritage` (تراثي). The last two must be added to `DOMAINS` in
`src/kass_layer/detector/engine.py` **with exactly these ids**. Until then Kass answers 422 for them and the editor
stays silent.
