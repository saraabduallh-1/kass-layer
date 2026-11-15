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
