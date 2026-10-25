"""New dossier language follows the explicit research project, unless supplied."""

import json

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.repository import ResearchError


@pytest.mark.parametrize("language", ["de", "fr", "nl", "generic"])
def test_api_dossier_inherits_research_project_language(tmp_path, language):
    api.init(tmp_path, title="Synthetic project", language=language)
    created = api.create_dossier(tmp_path, "Notes", "Synthetic notes.")
    assert api.get_record(tmp_path, "dossier", created["dossier_id"])["record"]["language"] == language


def test_api_explicit_language_wins_and_invalid_value_does_not_write(tmp_path):
    api.init(tmp_path, title="Synthetic project", language="de")
    created = api.create_dossier(tmp_path, "Notes", "Synthetic notes.", language="en")
    assert api.get_record(tmp_path, "dossier", created["dossier_id"])["record"]["language"] == "en"
    before = (tmp_path / "research/HEAD.json").read_bytes()
    for language in ("", "auto", "unknown"):
        with pytest.raises(ResearchError, match="Unsupported language"):
            api.create_dossier(tmp_path, "Invalid", "No write.", language=language)
        assert (tmp_path / "research/HEAD.json").read_bytes() == before


def test_dossier_default_is_research_language_not_manuscript_settings(tmp_path):
    api.init(tmp_path, title="Synthetic project", language="fr")
    (tmp_path / "lixity.toml").write_text('language = "de"\n')
    created = api.create_dossier(tmp_path, "Notes", "Synthetic notes.")
    assert api.get_record(tmp_path, "dossier", created["dossier_id"])["record"]["language"] == "fr"


@pytest.mark.parametrize("explicit", [False, True])
def test_cli_omitted_language_inherits_and_explicit_language_wins(tmp_path, capsys, explicit):
    api.init(tmp_path, title="Synthetic project", language="de")
    args = ["research", "dossier", "--project", str(tmp_path), "--title", "Notes", "--body", "Synthetic notes.", "--json"]
    if explicit:
        args += ["--language", "en"]
    assert main(args) == 0
    created = json.loads(capsys.readouterr().out)
    record = api.get_record(tmp_path, "dossier", created["dossier_id"])["record"]
    assert record["language"] == ("en" if explicit else "de")


def test_default_english_research_project_keeps_english(tmp_path):
    api.init(tmp_path, title="Synthetic project")
    created = api.create_dossier(tmp_path, "Notes", "Synthetic notes.")
    assert api.get_record(tmp_path, "dossier", created["dossier_id"])["record"]["language"] == "en"


def test_updates_preserve_an_explicit_existing_dossier_language(tmp_path):
    api.init(tmp_path, title="Synthetic project", language="de")
    created = api.create_dossier(tmp_path, "Notes", "Synthetic notes.", language="en")
    revised = api.revise_record(tmp_path, "dossier", created["dossier_id"],
                                changes={"body": "Revised notes."}, expected_revision=1,
                                change_kind="correction", reason="Synthetic correction.")
    assert revised["record"]["language"] == "en"


@pytest.mark.parametrize(("language", "expected"), [(None, "de"), ("en", "en")])
def test_native_dossier_creation_respects_project_language(tmp_path, language, expected):
    from tests.support import recording_handler

    api.init(tmp_path, title="Synthetic project", language="de")
    handler = recording_handler(tmp_path, research_dir=tmp_path)
    payload = {"title": "Notes", "body": "Synthetic notes."}
    if language is not None:
        payload["language"] = language
    handler._handle_research_dossier(payload)
    code, response = handler.response
    assert code == 200 and response["ok"]
    record = api.get_record(tmp_path, "dossier", response["dossier_id"])["record"]
    assert record["language"] == expected


@pytest.mark.parametrize("language", ["", "auto", "unknown", 42, False])
def test_native_invalid_language_never_creates_a_dossier(tmp_path, language):
    from tests.support import recording_handler

    api.init(tmp_path, title="Synthetic project", language="de")
    before = (tmp_path / "research/HEAD.json").read_bytes()
    handler = recording_handler(tmp_path, research_dir=tmp_path)
    handler._handle_research_dossier({"title": "Notes", "body": "Synthetic notes.", "language": language})
    assert handler.response[0] == 400
    assert (tmp_path / "research/HEAD.json").read_bytes() == before


def test_http_dossier_creation_inherits_language_and_rejects_invalid_explicit_value(tmp_path):
    from tests.support import LoopbackServer, make_handler

    api.init(tmp_path, title="Synthetic project", language="de")
    with LoopbackServer(make_handler(tmp_path, research_dir=tmp_path)) as server:
        code, response = server.request_json("/api/research-dossier", payload={
            "title": "Notes", "body": "Synthetic notes."})
        assert code == 200 and response["ok"]
        record = api.get_record(tmp_path, "dossier", response["dossier_id"])["record"]
        assert record["language"] == "de"
        before = (tmp_path / "research/HEAD.json").read_bytes()
        code, response = server.request_json("/api/research-dossier", payload={
            "title": "Invalid", "body": "Synthetic notes.", "language": "auto"})
        assert code == 400 and response["ok"] is False
        assert (tmp_path / "research/HEAD.json").read_bytes() == before
