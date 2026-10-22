"""Configured motif patterns agree across chapter measurements and reports."""

import copy
import json
import re
from xml.etree import ElementTree

import pytest

from lixity import api
from lixity.analyzer import CorpusAnalyzer
from lixity.cli import main
from lixity.models import CorpusConfig
from lixity.motifs import motif_report
from lixity.pipeline import resolve_document_config
from lixity.server.views import build_server_dashboard

TEXT = "## One\n\nA door opens. Another door closes. A window shines.\n"


@pytest.mark.parametrize("settings,expected", [
    ({"motif_regexes": {"Door": r"\bdoor\b"}}, {"Door": 2}),
    ({"motifs": {"Window": r"\bwindow\b"}}, {"Window": 1}),
    ({"motif_regexes": {"Door": "door"}, "motifs": {"Window": "window"}}, {"Door": 2, "Window": 1}),
    ({"motif_regexes": {"Door": "door"}, "motifs": {"Door": "door"}}, {"Door": 2}),
    ({"motif_regexes": {"Disabled": ""}}, {"Disabled": 0}),
])
def test_project_patterns_agree_in_metrics_api_cli_native_and_build(tmp_path, capsys, settings, expected):
    original = copy.deepcopy(settings)
    config, _ = resolve_document_config(TEXT, project_config=settings)
    assert CorpusAnalyzer(config).analyze_text(TEXT).chapters[0].motif_counts == expected
    report = motif_report(TEXT, config=config).to_dict()
    assert {item["name"]: item["mentions"] for item in report["motifs"]} == expected
    assert api.motifs(TEXT, project_config=settings)["motifs"] == report["motifs"]
    assert settings == original

    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text(TEXT, encoding="utf-8")
    configuration = tmp_path / "lixity.toml"
    configuration.write_text('language = "en"\n' + "\n".join(
        f"[{key}]\n" + "\n".join(f"{json.dumps(name)} = {json.dumps(pattern)}" for name, pattern in patterns.items())
        for key, patterns in settings.items()
    ), encoding="utf-8")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert main(["motifs", str(manuscript), "--project", str(tmp_path), "--json"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["motifs"] == report["motifs"]

    document, _ = build_server_dashboard(str(manuscript), project_root=tmp_path)
    panel = re.search(r'<section[^>]*id="motifs".*?</section>', document, re.DOTALL)
    assert panel is not None
    root = ElementTree.fromstring(panel[0])  # noqa: S314
    rows = root.findall("./div/table/tbody/tr")
    assert {row.find("td").text: int(row.findall("td")[1].text) for row in rows} == expected
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before

    assert main(["build", str(manuscript), "--project", str(tmp_path)]) == 0
    capsys.readouterr()
    built = next((tmp_path / "exports").glob("*_dashboard.html"))
    built_panel = re.search(r'<section[^>]*id="motifs".*?</section>', built.read_text(), re.DOTALL)
    assert built_panel is not None
    assert built_panel[0] == panel[0]
    assert all((tmp_path / name).read_bytes() == content for name, content in before.items())


@pytest.mark.parametrize("explicit,expected", [({}, {}), ({"Explicit": "window"}, {"Explicit": 1})])
def test_explicit_report_mapping_replaces_configured_patterns(explicit, expected):
    config = CorpusConfig(motif_regexes={"Configured": "door"})
    result = motif_report(TEXT, explicit, config)
    assert {item.name: item.mentions for item in result.motifs} == expected
    assert {item["name"]: item["mentions"] for item in api.motifs(
        TEXT, explicit, project_config={"motif_regexes": {"Configured": "door"}},
    )["motifs"]} == expected


def test_explicit_corpus_override_replaces_both_project_spellings():
    settings = {"motif_regexes": {"Conflict": "door"}, "motifs": {"Conflict": "window"}}
    config, _ = resolve_document_config(TEXT, project_config=settings, motif_regexes={"Override": "window"})
    assert config.motif_regexes == {"Override": "window"}
    assert {item["name"]: item["mentions"] for item in api.motifs(
        TEXT, {}, project_config=settings,
    )["motifs"]} == {}
    empty, _ = resolve_document_config(TEXT, project_config=settings, motif_regexes={})
    assert empty.motif_regexes == {}


def test_shared_motif_matching_preserves_unicode_case_and_scoped_flags():
    text = "## One\n\nÄpfel. äpfel.\n"
    config = CorpusConfig(motif_regexes={"Folded": "ÄPFEL", "Exact": "(?-i:Äpfel)"})
    expected = {"Folded": 2, "Exact": 1}
    assert CorpusAnalyzer(config).analyze_text(text).chapters[0].motif_counts == expected
    assert {item.name: item.mentions for item in motif_report(text, config=config).motifs} == expected


def test_cli_explicit_motif_replaces_conflicting_project_patterns(tmp_path, capsys):
    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text(TEXT, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        '[motif_regexes]\nConflict = "door"\n[motifs]\nConflict = "window"\n', encoding="utf-8",
    )
    assert main(["motifs", str(manuscript), "--project", str(tmp_path),
                 "--motif", "Explicit=window", "--json"]) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert {item["name"]: item["mentions"] for item in json.loads(output.out)["motifs"]} == {"Explicit": 1}


def test_conflicting_labels_fail_explicitly_across_project_entrypoints(tmp_path, capsys):
    settings = {"motif_regexes": {"Conflict": "door"}, "motifs": {"Conflict": "window"}}
    with pytest.raises(ValueError, match=r"motif_regexes.*motifs|motifs.*motif_regexes"):
        api.motifs(TEXT, project_config=settings)
    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text(TEXT, encoding="utf-8")
    (tmp_path / "lixity.toml").write_text(
        '[motif_regexes]\nConflict = "door"\n[motifs]\nConflict = "window"\n', encoding="utf-8",
    )
    assert main(["motifs", str(manuscript), "--project", str(tmp_path), "--json"]) == 1
    output = capsys.readouterr()
    assert output.out == "" and "Conflict" in output.err
    assert main(["build", str(manuscript), "--project", str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert output.out == "" and "Conflict" in output.err
    assert not (tmp_path / "exports").exists()
    with pytest.raises(ValueError, match="Conflict"):
        build_server_dashboard(str(manuscript), project_root=tmp_path)


@pytest.mark.parametrize("key,patterns", [
    ("motifs", []), ("motifs", {"Door": 2}), ("motifs", {"Door": "["}),
    ("motif_regexes", {"Door": "["}),
])
def test_invalid_configured_patterns_never_become_an_empty_report(key, patterns):
    with pytest.raises(ValueError, match=key):
        api.motifs(TEXT, project_config={key: patterns})
