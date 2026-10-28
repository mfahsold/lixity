"""Route discovery and explicit CLI JSON selection use synthetic local projects."""

import contextlib
import io
import json
import warnings

import pytest

from lixity import __version__, api, cli
from lixity.cli import main
from lixity.config import TOOL_KEYS
from lixity.models import CorpusConfig
from lixity.publication import PublicationSettings
from lixity.research import api as research
from lixity.research import cli as research_cli
from lixity.research.repository import Repository
from lixity.style_fingerprint import FingerprintThresholds
from tests.support import LoopbackServer, make_handler


@pytest.fixture
def endpoint(tmp_path):
    handler = make_handler(tmp_path)
    with LoopbackServer(handler) as server:
        def request(path, headers=None, *, method="GET", body=None):
            response = server.request(path, method=method, body=body, headers=headers)
            return response.status, response.body, response.headers.get("content-type")

        yield handler, request


@pytest.mark.parametrize("path", ["/api", "/api/"])
def test_api_index_without_a_loaded_project(endpoint, path):
    _, request = endpoint
    status, body, content_type = request(path)
    assert status == 200 and content_type.startswith("application/json")
    data = json.loads(body)
    assert data["schema_version"] == "lixity-api-index/1"
    assert data["version"] == __version__
    assert data["project"]["manuscript_loaded"] is False
    assert data["project"]["research_store_present"] is False
    assert data["documentation"] == "https://mfahsold.github.io/lixity/AGENTS.md"
    assert "/api/research/record" in data["routes"]["GET"]
    assert "/api/research/history" in data["routes"]["GET"]
    assert "/api/research/ocr-status" in data["routes"]["GET"]
    for route in ("analyze", "rebuild", "marker-add", "marker-resolve", "research-zotero", "research-zotero-ingest"):
        assert f"/api/{route}" in data["routes"]["POST"]
    assert "/api/export" not in data["routes"]["POST"]
    assert not any(route in data["routes"]["POST"] for route in ("/api/nda-list", "/api/nda-unlock", "/api/nda-add"))


def test_index_reflects_registered_routes_without_archive_or_source_reads(endpoint, tmp_path, monkeypatch):
    handler, request = endpoint
    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text("Synthetic manuscript sentinel; excluded from discovery.")
    research.init(tmp_path, title="Synthetic archive title excluded from discovery")
    handler.source_input = str(manuscript)
    handler.research_dir = str(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Discovery must not read source or archive records")

    monkeypatch.setattr(Repository, "snapshot", forbidden)
    monkeypatch.setattr(type(manuscript), "read_text", forbidden)
    monkeypatch.setattr(type(manuscript), "read_bytes", forbidden)
    status, body, _ = request("/api")
    assert status == 200
    data = json.loads(body)
    assert data["project"]["manuscript_loaded"] and data["project"]["research_store_present"]
    assert "Synthetic manuscript sentinel" not in body.decode()
    assert "Synthetic archive title" not in body.decode()
    assert str(tmp_path) not in body.decode()
    assert set(data["routes"]["GET"]) == set(handler.GET_ROUTES)
    assert set(data["routes"]["POST"]) == {f"/api/{action}" for action in handler.POST_ROUTES}


def test_index_keeps_the_existing_host_guard(endpoint):
    _, request = endpoint
    status, body, _ = request("/api", {"Host": "untrusted.example"})
    assert status == 403 and json.loads(body)["ok"] is False


def test_index_tracks_the_same_registry_used_by_dispatch(endpoint):
    handler, request = endpoint

    def synthetic_route(self):
        self._json({"ok": True, "synthetic": True})

    handler._synthetic_discovery_route = synthetic_route
    handler.GET_ROUTES = {**handler.GET_ROUTES, "/api/synthetic-discovery": "_synthetic_discovery_route"}
    status, body, _ = request("/api")
    assert status == 200 and "/api/synthetic-discovery" in json.loads(body)["routes"]["GET"]
    status, body, _ = request("/api/synthetic-discovery")
    assert status == 200 and json.loads(body)["synthetic"] is True


def test_implicit_research_root_is_the_project_not_its_archive(endpoint, tmp_path):
    handler, request = endpoint
    research.init(tmp_path, title="Synthetic default research root")
    assert handler.get_research_root() == tmp_path
    status, body, _ = request("/api/research/status")
    assert status == 200 and json.loads(body)["initialized"] is True
    assert json.loads(body)["project_root"] == str(tmp_path)


@pytest.mark.parametrize("command", ["sources", "audit", "review", "decision-impact", "compare", "matrix"])
def test_json_alias_selects_real_cli_machine_output(tmp_path, command):
    project = tmp_path / "project"
    research.init(project, title="Synthetic CLI project")
    flags = []
    if command == "decision-impact":
        decision = research.record_decision(project, title="Synthetic decision", rationale="Author supplied rationale.")
        flags = ["--decision-id", decision["decision_id"]]
    elif command == "compare":
        source = tmp_path / "source.txt"
        source.write_text("Synthetic archive record about a reading room. " * 100)
        captured = research.ingest(project, source, allow_retention=True)
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Synthetic manuscript\n\n## Chapter One\n\n" + "A reader entered the quiet reading room. " * 100)
        flags = ["--source-id", captured["source_id"], "--manuscript", str(manuscript)]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = main(["research", command, "--project", str(project), *flags, "--json"])
    assert status == 0 and isinstance(json.loads(output.getvalue()), dict)


def test_json_alias_is_exclusive_with_other_output_formats(tmp_path):
    errors = io.StringIO()
    with contextlib.redirect_stderr(errors), pytest.raises(SystemExit) as failure:
        main(["research", "review", "--project", str(tmp_path), "--json", "--format", "md"])
    assert failure.value.code == 2
    assert "not allowed with argument" in errors.getvalue()


def test_about_reports_research_formats_from_the_command_parser():
    research_command = next(command for command in api.about()["commands"] if command["name"] == "research")
    commands = {command["name"]: command for command in research_command["subcommands"]}
    assert commands["review"]["default_output"] == "text"
    assert commands["decision-impact"]["json_flag"] == "--json"
    assert commands["matrix"]["default_output"] == "md"
    assert commands["dashboard"]["output_formats"] == ["html"]
    assert commands["sources"]["default_output"] == "json"


def test_about_format_metadata_tracks_parser_configuration(monkeypatch):
    monkeypatch.setitem(research_cli.OUTPUT_FORMATS, "review", (("text", "md", "json"), "md"))
    research_command = next(command for command in api.about()["commands"] if command["name"] == "research")
    review = next(command for command in research_command["subcommands"] if command["name"] == "review")
    assert review["default_output"] == "md"


def test_about_reports_supported_research_record_and_manifest_versions():
    research_command = next(command for command in api.about()["commands"] if command["name"] == "research")
    assert "research-local/5" in research_command["record_schema_versions"]
    assert "research-manifest-local/5" in research_command["manifest_schema_versions"]


@pytest.mark.parametrize("arguments", [["about", "--json"], ["schema"], ["completion", "bash"]])
def test_installed_discovery_does_not_load_configuration(arguments, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("Installed discovery must not read project or user configuration")

    monkeypatch.setattr(cli, "load_project_config", forbidden)
    assert main(arguments) == 0
    assert capsys.readouterr().out


@pytest.mark.parametrize("arguments", [["about", "--json"], ["schema"], ["completion", "bash"]])
def test_installed_discovery_works_beside_malformed_configuration(arguments, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "synthetic-home"))
    (tmp_path / "lixity.toml").write_text('title = "Synthetic unclosed title\n', encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert main(arguments) == 0
    assert "Synthetic unclosed title" not in capsys.readouterr().out


@pytest.mark.parametrize("command", ["about", "schema"])
@pytest.mark.parametrize("section", ["languages", "features", "heuristics", "commands", "configuration"])
def test_installed_discovery_can_select_one_versioned_section(command, section, capsys):
    assert main([command, "--section", section]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"meta", section}
    assert data["meta"]["version"] == __version__
    if section == "configuration":
        assert data[section]["schema_version"] == "lixity-configuration/1"
    else:
        assert data[section]


def test_configuration_discovery_describes_installed_models_and_threshold_domain():
    settings = api.about()["configuration"]
    assert settings["schema_version"] == "lixity-configuration/1"
    assert set(settings["accepted_keys"]) == TOOL_KEYS
    assert settings["uninterpreted_keys"] == ["capabilities", "phrases"]
    corpus = settings["corpus_schema"]["properties"]
    assert set(corpus) == set(CorpusConfig.model_fields)
    assert corpus["chapter_regex"]["default"] == r"(?m)^##\s+"
    assert corpus["language"]["default"] == "en"
    assert corpus["word_regex"]["default"] is None
    assert corpus["register_profiles"]["default"] == {}
    thresholds = settings["threshold_schema"]["properties"]
    assert thresholds["z_mild"] == {"type": "number", "default": 2.5, "minimum": 0}
    assert thresholds["fdr_q"] == {"type": "number", "default": 0.05, "exclusiveMinimum": 0, "exclusiveMaximum": 1}
    assert thresholds["min_chapters"] == {"type": "integer", "default": 2, "minimum": 2}
    assert thresholds["flag_min_severity"]["enum"] == [1, 2, 3]
    assert thresholds["fdr_method"]["enum"] == ["bh", "by"]
    assert settings["threshold_schema"]["additionalProperties"] is False
    assert "z_mild <= z_strong" in settings["threshold_schema"]["$comment"]
    assert "audio" in settings["project_only_keys"]
    audio_version = settings["audio_schema"]["properties"]["schema_version"]
    assert audio_version["default"] == "lixity-audio-settings/1"
    assert audio_version["enum"] == ["lixity-audio-settings/1", "lixity-audio-settings/2"]
    assert settings["audio_schema"]["additionalProperties"] is False
    assert "author_name" in settings["project_only_keys"]
    assert "title" not in settings["project_only_keys"]
    assert settings["native_settings"]["persisted_keys"] == [
        "title", "author_name", "publication", "site_publications", "dossier_collections", "terms", "register_profiles", "chapter_registers", "audio",
    ]
    assert set(settings["native_settings"]["session_keys"]) == {
        "language", "z_mild", "z_strong", "fdr_q", "fdr_method", "min_chapters",
        "dim_score_threshold", "flag_min_severity",
    }
    optional = settings["native_settings"]["optional_persistence"]
    assert optional["flag"] == "save_analysis_defaults"
    assert optional["default"] is False and optional["requires_project_token"] is True
    assert set(optional["keys"]) == {
        "language", "z_mild", "z_strong", "fdr_q", "fdr_method", "min_chapters",
        "dim_score_threshold", "flag_min_severity",
    }


def test_configuration_discovery_tracks_shared_numeric_policy(monkeypatch):
    policy = FingerprintThresholds.numeric_inputs["fdr_q"]
    monkeypatch.setattr(FingerprintThresholds, "numeric_inputs", {
        **FingerprintThresholds.numeric_inputs, "fdr_q": type(policy)(0.01, 0.9),
    })
    described = api.about()["configuration"]["threshold_schema"]["properties"]["fdr_q"]
    assert described == {"type": "number", "default": 0.05, "minimum": 0.01, "maximum": 0.9}
    assert FingerprintThresholds(fdr_q=0.01).fdr_q == 0.01
    with pytest.raises(ValueError):
        FingerprintThresholds(fdr_q=0.001)


def test_publication_discovery_describes_defaults_and_normalized_text_limits():
    schema = api.about()["configuration"]["publication_schema"]
    assert schema["additionalProperties"] is False
    fields = schema["properties"]
    assert set(fields) == set(PublicationSettings.model_fields)
    assert fields["enabled"] == {"default": False, "title": "Enabled", "type": "boolean"}
    assert fields["publisher_name"]["default"] == ""
    assert fields["publisher_name"]["x-lixity-text"] == {"kind": "text", "max_chars": 500, "length_after": "strip"}
    assert fields["publisher_address"]["x-lixity-text"] == {"kind": "multiline", "max_chars": 2000, "length_after": "strip"}
    assert fields["year"]["x-lixity-text"]["max_chars"] == 4
    assert fields["isbn_print"]["x-lixity-text"]["max_chars"] == 32
    assert "maxLength" not in fields["publisher_name"], "Bounds apply after normalization, not to raw JSON text"
    assert "0001" in schema["description"] and "9999" in schema["description"]
    assert "ISBN" in schema["description"]


def test_character_discovery_uses_the_owning_profile_schema_without_project_values():
    from lixity.characters import CharacterProfile

    settings = api.about()["configuration"]
    assert "characters" in settings["accepted_keys"]
    assert "characters" in settings["project_only_keys"]
    schema = settings["characters_schema"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] == CharacterProfile.model_json_schema()
    assert schema["additionalProperties"]["additionalProperties"] is False
    assert schema["additionalProperties"]["properties"]["pov_in_chapters"]["items"] == {
        "minimum": 1, "type": "integer",
    }
    assert PublicationSettings(publisher_name=" " * 1000 + "Synthetic publisher").publisher_name == "Synthetic publisher"


@pytest.mark.parametrize("values", [
    {"enabled": "yes"}, {"publisher_name": "x" * 501},
    {"publisher_address": "x" * 2001}, {"year": "0000"}, {"year": "202X"},
    {"isbn_print": "9781234567890"}, {"publisher_name": "Synthetic\x00publisher"},
    {"isbn_print": "0-306-40615-2", "isbn_digital": "978-0-306-40615-7"},
    {"unknown_field": "Synthetic value"},
])
def test_publication_discovery_preserves_component_validation(values):
    assert api.about()["configuration"]["publication_schema"]["additionalProperties"] is False
    with pytest.raises(ValueError):
        PublicationSettings.model_validate(values)


def test_publication_discovery_tracks_the_shared_text_policy(monkeypatch):
    from dataclasses import replace

    from lixity import publication

    monkeypatch.setitem(publication._FIELDS, "publisher_name", replace(publication._FIELDS["publisher_name"], max_chars=5))
    field = api.about()["configuration"]["publication_schema"]["properties"]["publisher_name"]
    assert field["x-lixity-text"]["max_chars"] == 5
    assert PublicationSettings(publisher_name="  Short  ").publisher_name == "Short"
    with pytest.raises(ValueError):
        PublicationSettings(publisher_name="Longer")


def test_configuration_discovery_does_not_expose_or_share_project_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "synthetic-home"))
    (tmp_path / "lixity.toml").write_text(
        'title = "Synthetic private sentinel"\nz_mild = 1.5\n'
        '[publication]\npublisher_name = "Synthetic private publisher"\n', encoding="utf-8",
    )
    first = api.about()["configuration"]
    assert "Synthetic private sentinel" not in json.dumps(first)
    assert "Synthetic private publisher" not in json.dumps(first)
    assert str(tmp_path) not in json.dumps(first)
    assert first["threshold_schema"]["properties"]["z_mild"]["default"] == 2.5
    first["accepted_keys"].append("synthetic_mutation")
    first["corpus_schema"]["properties"]["language"]["default"] = "synthetic_mutation"
    first["threshold_schema"]["properties"]["fdr_q"]["default"] = 0.8
    first["publication_schema"]["properties"]["publisher_name"]["default"] = "synthetic_mutation"
    assert "synthetic_mutation" not in json.dumps(api.about()["configuration"])
    assert api.about()["configuration"]["threshold_schema"]["properties"]["fdr_q"]["default"] == 0.05


@pytest.mark.parametrize("status", ["applied", "review_needed"])
def test_acknowledgement_http_route_uses_explicit_revision_tokens(endpoint, tmp_path, status):
    handler, request = endpoint
    research.init(tmp_path, title="Synthetic HTTP acknowledgement")
    dossier = research.create_dossier(tmp_path, "Synthetic dossier", "Synthetic untouched dossier.")["dossier_id"]
    decision = research.record_decision(tmp_path, title="Synthetic decision", rationale="Synthetic unchanged rationale.",
                                        dossier_ids=[dossier])["decision_id"]
    handler.research_dir = str(tmp_path)
    snapshot = Repository(tmp_path).snapshot()
    payload = {"decision_id": decision, "dossier_id": dossier, "expected_snapshot": snapshot.digest,
               "expected_decision_revision": 1, "expected_dossier_revision": 1, "status": status,
               "note": "Synthetic author statement."}
    code, body, _ = request("/api/research-decision-acknowledge", {"Content-Type": "application/json"},
                             method="POST", body=json.dumps(payload))
    data = json.loads(body)
    assert code == 200 and data["ok"] is True and data["status"] == status
    assert data["decision_revision"] == 1 and data["dossier_revision"] == 1
    assert data["snapshot"] != snapshot.digest
    assert research.get_dossier(tmp_path, dossier)["body"] == "Synthetic untouched dossier."


@pytest.mark.parametrize("invalid", ["snapshot", "decision", "dossier", "missing", "status"])
def test_acknowledgement_http_conflict_or_invalid_body_writes_nothing(endpoint, tmp_path, invalid):
    handler, request = endpoint
    research.init(tmp_path, title="Synthetic HTTP acknowledgement")
    dossier = research.create_dossier(tmp_path, "Synthetic dossier", "Synthetic unchanged body.")["dossier_id"]
    decision = research.record_decision(tmp_path, title="Synthetic decision", rationale="Synthetic rationale.",
                                        dossier_ids=[dossier])["decision_id"]
    handler.research_dir = str(tmp_path)
    before = Repository(tmp_path).snapshot().digest
    payload = {"decision_id": decision, "dossier_id": dossier, "expected_snapshot": before,
               "expected_decision_revision": 1, "expected_dossier_revision": 1, "status": "applied"}
    if invalid == "snapshot":
        payload["expected_snapshot"] = "0" * 64
    elif invalid in ("decision", "dossier"):
        payload[f"expected_{invalid}_revision"] = 2
    elif invalid == "missing":
        del payload["expected_snapshot"]
    else:
        payload["status"] = "verified"
    code, body, _ = request("/api/research-decision-acknowledge", {"Content-Type": "application/json"},
                             method="POST", body=json.dumps(payload))
    assert code == (409 if invalid in ("snapshot", "decision", "dossier") else 400)
    assert json.loads(body)["ok"] is False
    assert Repository(tmp_path).snapshot().digest == before
