"""Server middleware helpers and POST /api/motif-search endpoint tests."""

from __future__ import annotations

import hashlib
import json

import pytest

from lixity.server.middleware import (
    analysis_open_overrides,
    build_manuscript_store,
    load_selected_project_config,
    parse_single_query_params,
)
from tests.support import LoopbackServer, make_handler


def test_parse_single_query_params_enforces_keys_and_non_empty():
    assert parse_single_query_params("/api/test?a=1&b=two", required=("a",), optional=("b",)) == {
        "a": "1",
        "b": "two",
    }
    assert parse_single_query_params("/api/test", optional=("a",)) == {}
    with pytest.raises(ValueError):
        parse_single_query_params("/api/test", required=("a",))
    with pytest.raises(ValueError):
        parse_single_query_params("/api/test?a=1&a=2", required=("a",))
    with pytest.raises(ValueError):
        parse_single_query_params("/api/test?a=1&extra=2", required=("a",))
    with pytest.raises(ValueError):
        parse_single_query_params("/api/test?a=", required=("a",), non_empty=("a",))


def test_config_loading_and_store_factory_apply_explicit_project_settings(tmp_path):
    manuscript = tmp_path / "book.md"
    manuscript.write_text("## Eins\n\nHallo Welt.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('language = "de"\nshort_sentence_max = 4\n', encoding="utf-8")
    assert analysis_open_overrides({"language": "de", "tense_model": "german"}) == {
        "tense_model": "german",
    }
    cfg = load_selected_project_config(
        str(manuscript),
        project_root=tmp_path,
        overrides={"tense_scope": "narration", "unrelated": "ignored"},
    )
    assert cfg["short_sentence_max"] == 4
    assert cfg["tense_scope"] == "narration"
    assert "unrelated" not in cfg

    store = build_manuscript_store(
        tmp_path,
        str(manuscript),
        language="de",
        project_root=tmp_path,
        overrides={"tense_model": "german"},
    )
    assert store.project_config["short_sentence_max"] == 4
    assert store.project_config["tense_model"] == "german"

    with pytest.raises(ValueError):
        build_manuscript_store(tmp_path, None)


def test_motif_search_endpoint_searches_phrases_regex_and_quotation_context(tmp_path):
    manuscript = tmp_path / "book.md"
    content = (
        "## Eins\n\n"
        'Am Fenster stand es ist so, dass der Nebel stieg. '
        '„Es ist so, dass wir gehen“, sagte Mara.\n'
    )
    manuscript.write_text(content, encoding="utf-8")
    from lixity.server.pdf_context import manuscript_pdf_token

    handler = make_handler(tmp_path, source_input=manuscript, language="de")
    handler.refresh()
    token = manuscript_pdf_token(
        str(manuscript),
        project_root=handler.workspace_root,
        language=handler.language,
        title=handler.title,
        thresholds=handler.thresholds,
    )

    with LoopbackServer(handler) as server:
        api_doc = server.request("/api").json
        assert api_doc["capabilities"]["motif_search"] is True
        assert "/api/motif-search" in api_doc["routes"]["POST"]

        # Phrase search with punctuation, Unicode quotation context, and valid project_token
        res = server.request(
            "/api/motif-search",
            payload={"query": "es ist so, dass", "project_token": token},
        )
        assert res.status == 200
        data = res.json
        assert data["ok"] is True
        assert data["schema_version"] == "lixity-motif-search/1"
        assert data["source_sha256"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert data["language"] == "de"
        assert data["offset_unit"] == "unicode_codepoint"
        assert data["total_matches"] == 2
        assert data["truncated"] is False
        assert [occ["quotation_context"] for occ in data["occurrences"]] == [
            "outside_quotation",
            "in_quotation",
        ]
        assert data["occurrences"][0]["paragraph_id"] == "p-0"
        assert data["occurrences"][0]["start_line"] == 3

        # Regex search with limit
        reg = server.request(
            "/api/motif-search",
            payload={"query": r"\bNebel\b", "regex": True, "limit": 1},
        )
        assert reg.status == 200
        assert reg.json["total_matches"] == 1
        assert reg.json["occurrences"][0]["quote"] == "Nebel"

        # Invalid regex and empty query return 400
        bad_regex = server.request(
            "/api/motif-search", payload={"query": "[broken", "regex": True}
        )
        assert bad_regex.status == 400 and bad_regex.json["ok"] is False
        assert bad_regex.json["code"] == "invalid-regex"

        empty_query = server.request("/api/motif-search", payload={"query": "   "})
        assert empty_query.status == 400 and empty_query.json["ok"] is False

        # Stale project token returns 409
        stale = server.request(
            "/api/motif-search",
            payload={"query": "Nebel", "project_token": "0" * 64},
        )
        assert stale.status == 409
        assert stale.json["code"] == "stale-context"

        # Origin and Host guards apply
        evil = server.request(
            "/api/motif-search",
            payload={"query": "Nebel"},
            headers={"Origin": "https://evil.invalid"},
        )
        assert evil.status == 403


def test_motif_search_endpoint_rejects_missing_manuscript(tmp_path):
    with LoopbackServer(make_handler(tmp_path)) as server:
        res = server.request("/api/motif-search", payload={"query": "Nebel"})
        assert res.status == 400
        assert json.loads(res.body)["ok"] is False
