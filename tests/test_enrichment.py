import json

import pytest

from kass_layer.dictionary import enrichment as en
from kass_layer.dictionary.qwen_client import QwenClient, QwenError


def _dictionary(dictionary_id, records):
    return {"dictionary_id": dictionary_id, "dictionary_name": "معجم تجريبي", "status": "complete", "records": records}


def _record(entry_id, term, definition="تعريف.", english=""):
    return {"entry_id": entry_id, "sense_id": f"{entry_id}:0", "term": term, "term_without_diacritics": term,
            "definition": definition, "english_term": english}


def _variant(form, kind="transliteration", confidence="high", ambiguous=False, **extra):
    return {"form": form, "type": kind, "confidence": confidence, "ambiguous": ambiguous,
            "ambiguity_note": "", "example": "جملة.", **extra}


def _write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_normalize_unifies_arabic_spelling():
    assert en.normalize("أَلإِدارَة") == en.normalize("الادارة")
    assert en.normalize("مستشفى") == en.normalize("مستشفي")
    assert en.normalize("«Model»") == "model"


def test_extract_json_tolerates_thinking_and_fences():
    text = '<think>let me think {not json}</think>\n```json\n{"items": [{"index": 1, "variants": []}]}\n```'
    assert en.extract_json(text) == {"items": [{"index": 1, "variants": []}]}


def test_parse_items_ignores_out_of_range_and_repeated_indices():
    payload = {"items": [{"index": 1, "variants": []}, {"index": 1, "variants": [1]}, {"index": 9, "variants": []}]}
    assert en.parse_items(payload, 2) == {1: {"index": 1, "variants": []}}


def test_validate_drops_and_flags():
    d = _dictionary("d1", [_record("a", "نموذج", english="Model"), _record("b", "بيانات")])
    rows = en.generation_rows(d, d["records"][:1], {1: {"variants": [
        _variant("مودل"),
        _variant("model", "foreign"),
        _variant("نَموذج"),                          # same as term once diacritics are removed
        _variant("مودل"),                            # duplicate
        _variant("modl", "transliteration"),         # Latin text labelled as Arabic transliteration
        _variant("بيانات", "informal_synonym"),      # standard term of another entry
        _variant("موديل", ambiguous=True),
    ]}}, "qwen")
    record = en.validate([{**rows[0], "reviewed": True}], en.term_index([d]))[0]
    statuses = {v["form"]: (v["status"], v["review_reasons"]) for v in record["variants"]}
    assert statuses["مودل"] == ("accepted", [])
    assert statuses["model"] == ("accepted", [])
    assert statuses["بيانات"] == ("review", ["is_standard_term_elsewhere"])
    assert statuses["موديل"] == ("review", ["ambiguous"])
    assert sorted(x["reason"] for x in record["dropped"]) == ["duplicate", "same_as_term", "script_does_not_match_type"]


def test_unreviewed_variants_are_never_accepted():
    d = _dictionary("d1", [_record("a", "نموذج")])
    rows = en.generation_rows(d, d["records"], {1: {"variants": [_variant("مودل")]}}, "qwen")
    record = en.validate([{**rows[0], "reviewed": False}], en.term_index([d]))[0]
    assert record["variants"][0]["review_reasons"] == ["not_reviewed_by_claude"]


def test_two_stage_pipeline(tmp_path):
    d = _dictionary("d1", [_record("a", "نموذج"), _record("b", "بيانات")])
    qwen_dir, review_dir, out_dir = tmp_path / "qwen", tmp_path / "review", tmp_path / "out"

    assert len(en.pending_generation(d, qwen_dir)) == 2
    generated = en.generation_rows(d, d["records"], {
        1: {"variants": [_variant("مودل"), _variant("المودلات")]},
        2: {"variants": []},
    }, "qwen")
    _write_rows(qwen_dir / "d1.jsonl", generated)
    assert en.pending_generation(d, qwen_dir) == []

    pairs = en.pending_review(d, qwen_dir, review_dir)
    assert [record["sense_id"] for record, _ in pairs] == ["a:0", "b:0"]
    params = en.review_params("معجم", pairs, "claude-opus-5-5", "high")
    assert '"proposed": [{"form": "مودل"' in params["messages"][0]["content"]

    reviewed = en.review_rows(d, pairs[:1], {1: {
        "variants": [_variant("مودل", action="kept", original_form=""),
                     _variant("داتا مودل", confidence="low", action="added", original_form="")],
        "dropped": [{"form": "المودلات", "reason": "inflected"}],
    }}, "claude", "sync")
    _write_rows(review_dir / "d1.jsonl", reviewed)
    assert [record["sense_id"] for record, _ in en.pending_review(d, qwen_dir, review_dir)] == ["b:0"]

    report = en.finalize([d], qwen_dir, review_dir, out_dir, state={"batches": {}, "sync_usage": []})
    final = {r["sense_id"]: r for r in en.read_jsonl(out_dir / "d1.variants.jsonl")}
    assert final["a:0"]["reviewed"] and final["a:0"]["variants"][0]["status"] == "accepted"
    assert final["a:0"]["variants"][1]["review_reasons"] == ["low_confidence"]
    assert final["a:0"]["dropped"] == [{"form": "المودلات", "reason": "inflected"}]
    assert report["totals"]["reviewed"] == 1 and report["totals"]["generated"] == 2

    # Regenerating a sense with a new proposal invalidates its old review.
    _write_rows(qwen_dir / "d1.jsonl", en.generation_rows(d, d["records"][:1], {1: {"variants": [_variant("موديل")]}}, "qwen"))
    assert "a:0" in [record["sense_id"] for record, _ in en.pending_review(d, qwen_dir, review_dir)]


class _Response:
    def __init__(self, status, payload=None, text=""):
        self.status_code, self._payload, self.text, self.headers = status, payload, text, {}

    def json(self):
        return self._payload


def test_qwen_client_retries_then_returns_text(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    client = QwenClient(base_url="http://qwen.test/v1", max_retries=2)
    replies = iter([_Response(503), _Response(200, {"choices": [{"message": {"content": '{"items": []}'}}],
                                                    "usage": {"prompt_tokens": 5}})])
    sent = []
    monkeypatch.setattr(client.session, "post", lambda url, json, timeout: sent.append(json) or next(replies))
    text, usage = client.complete([{"role": "user", "content": "x"}], en.GENERATION_SCHEMA)
    assert text == '{"items": []}' and usage == {"prompt_tokens": 5}
    assert "response_format" not in sent[0] and sent[0]["model"] == "Qwen/Qwen3.5-4B"


def test_qwen_client_does_not_retry_bad_request(monkeypatch):
    client = QwenClient(base_url="http://qwen.test/v1")
    monkeypatch.setattr(client.session, "post", lambda url, json, timeout: _Response(400, text="bad schema"))
    with pytest.raises(QwenError, match="HTTP 400"):
        client.complete([{"role": "user", "content": "x"}], en.GENERATION_SCHEMA)


def test_review_import_from_session_pack(tmp_path, monkeypatch):
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("enrich_cli", "scripts/enrich/enrich_dictionaries.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    d = _dictionary("d1", [_record("a", "نموذج")])
    qwen_dir, review_dir = tmp_path / "qwen", tmp_path / "review"
    _write_rows(qwen_dir / "d1.jsonl", en.generation_rows(d, d["records"], {1: {"variants": [_variant("المودل")]}}, "qwen"))
    for module in (en, cli):
        monkeypatch.setattr(module, "QWEN_DIR", qwen_dir, raising=False)
        monkeypatch.setattr(module, "REVIEW_DIR", review_dir, raising=False)
    monkeypatch.setattr(cli, "complete_dictionaries", lambda: [d])
    monkeypatch.setattr(cli, "pending_review", lambda dictionary: en.pending_review(dictionary, qwen_dir, review_dir))
    monkeypatch.setattr(cli, "finalize", lambda dictionaries: {"totals": {}})
    decisions = tmp_path / "decisions.jsonl"
    _write_rows(decisions, [{"sense_id": "a:0", "variants": [_variant("مودل", action="corrected", original_form="المودل")],
                             "dropped": []}])
    cli.cmd_review_import(type("Args", (), {"file": str(decisions)}))
    row = en.read_jsonl(review_dir / "d1.jsonl")[0]
    assert row["variants"][0]["original_form"] == "المودل" and row["model"] == cli.SESSION_REVIEWER
    assert en.pending_review(d, qwen_dir, review_dir) == []


def test_parse_items_accepts_bare_list_and_field_slips():
    payload = en.extract_json('[{"index": 1, "variants": [{"form": "مودل", "variant_type": "transliteration", "ambiguous_note": "x"}]}]')
    variant = en.parse_items(payload, 1)[1]["variants"][0]
    assert variant["type"] == "transliteration" and variant["ambiguity_note"] == "x"


def test_import_chatgpt_part_matches_by_sense_id(tmp_path):
    d = _dictionary("d1", [_record("a", "نموذج"), _record("b", "بيانات"), _record("c", "خوارزمية")])
    output = tmp_path / "part-001.jsonl"
    output.write_text("\n".join([
        "```jsonl",
        json.dumps({"sense_id": "b:0", "variants": [_variant("داتا")]}, ensure_ascii=False),
        json.dumps({"sense_id": "a:0", "variants": [_variant("مودل", variant_type="x")]}, ensure_ascii=False),
        json.dumps({"sense_id": "zzz", "variants": []}),
        "not json",
    ]), encoding="utf-8")
    rows, problems = en.import_chatgpt_part(d, d["records"], output)
    assert {r["sense_id"]: [v["form"] for v in r["variants"]] for r in rows} == {"a:0": ["مودل"], "b:0": ["داتا"]}
    assert problems == {"unknown_sense_id": 1, "unparseable_lines": 1, "missing_senses": 1}
    assert all(r["prompt_version"] == en.CHATGPT_PROMPT_VERSION for r in rows)
    qwen_dir = tmp_path / "gen"
    _write_rows(qwen_dir / "d1.jsonl", rows)
    assert set(en.current_generations(d, qwen_dir)) == {"a:0", "b:0"}


def test_enriched_deliverable_keeps_source_records(tmp_path):
    d = _dictionary("d1", [_record("a", "نموذج"), _record("b", "بيانات")])
    qwen_dir, review_dir, out_dir = tmp_path / "gen", tmp_path / "rev", tmp_path / "enriched" / "variants"
    gen = en.generation_rows(d, d["records"], {1: {"variants": [_variant("مودل")]}, 2: {"variants": []}}, "qwen")
    _write_rows(qwen_dir / "d1.jsonl", gen)
    pairs = en.pending_review(d, qwen_dir, review_dir)
    _write_rows(review_dir / "d1.jsonl", en.review_rows(d, pairs[:1], {1: {
        "variants": [_variant("مودل", action="kept", original_form="")], "dropped": []}}, "claude", "sync"))
    en.finalize([d], qwen_dir, review_dir, out_dir, state={"batches": {}, "sync_usage": []})
    payload = json.loads((tmp_path / "enriched" / "d1.enriched.json").read_text(encoding="utf-8"))
    assert payload["enrichment_status"] == "partial" and payload["counts"]["senses_reviewed"] == 1
    first, second = payload["records"]
    assert first["term"] == "نموذج" and first["enrichment"]["variants"][0]["form"] == "مودل"
    assert second["enrichment"] is None and second["definition"] == "تعريف."


def test_session_decision_parsing():
    import importlib.util
    spec = importlib.util.spec_from_file_location("session_review", "scripts/enrich/session_review.py")
    sr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sr)
    proposals = [_variant("مودل"), _variant("المودلات"), _variant("نموذج رياضي", "informal_synonym")]
    parsed = sr.parse_decision("مودل|t|h ; مودل|t|m|was=المودلات ; model|f|h ; موديل|t|m|amb=عارضة أزياء", proposals)
    actions = [(v["form"], v["action"]) for v in parsed["variants"]]
    assert actions == [("مودل", "kept"), ("مودل", "corrected"), ("model", "added"), ("موديل", "added")]
    assert parsed["variants"][3]["ambiguous"] and parsed["variants"][3]["ambiguity_note"] == "عارضة أزياء"
    assert parsed["dropped"] == [{"form": "نموذج رياضي", "reason": "rejected_in_review"}]
    assert sr.parse_decision("-", proposals)["variants"] == []


def test_article_free_key_keeps_hamza_initial_words():
    assert en.article_free_key("التجارة الإلكترونية") == en.article_free_key("تجارة إلكترونية")
    assert en.article_free_key("إلكترونية") != en.article_free_key("كترونية")
