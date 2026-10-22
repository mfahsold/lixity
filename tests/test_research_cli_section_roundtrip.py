"""Selected dossier source can be reviewed and revised without presentation text."""

import contextlib
import io
import json
import subprocess
import sys

import pytest

from lixity.research import api, cli
from lixity.research.repository import Repository
from tests.research_support import capture_research, parse_research_args, retained_files
from tests.research_support import revise_record as revise


@pytest.fixture
def archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic section workflow")
    return project


def read_section(project, identifier, section, *flags):
    return capture_research("dossier", identifier, "--project", str(project),
                            "--section", section, *flags)


@pytest.mark.parametrize("level", range(1, 7))
def test_selected_text_preserves_actual_heading_level(archive, level):
    heading = "#" * level + " Selected"
    identifier = api.create_dossier(archive, "Notebook", heading + "\n\nDetails.\n")["dossier_id"]

    status, output, errors = read_section(archive, identifier, "selected", "--format", "text")

    assert (status, errors) == (0, "")
    assert output.splitlines()[4] == heading
    selected = api.get_dossier(archive, identifier, section="Selected")
    assert selected["section_level"] == level
    status, output, errors = read_section(archive, identifier, "Selected")
    assert (status, errors) == (0, "")
    assert json.loads(output) == selected


@pytest.mark.parametrize(("body", "section", "content"), (
    ("Preamble only.", "Overview", "Preamble only."),
    ("Preamble first.\n\n## Details\n\nA detail.", "Overview", "Preamble first."),
    ("Preamble first.\n\n# Overview\n\nA detail.", "Introduction", "Preamble first."),
))
def test_implicit_preamble_is_labelled_without_inventing_a_heading(archive, body, section, content):
    identifier = api.create_dossier(archive, "Notebook", body)["dossier_id"]

    selected = api.get_dossier(archive, identifier, section=section)
    status, output, errors = read_section(archive, identifier, section, "--format", "text")

    assert selected["section_level"] is None
    assert section not in selected["editable_sections"]
    assert (status, errors) == (0, "")
    assert f"Section: {section} (implicit preamble)" in output
    assert f"## {section}" not in output
    assert read_section(archive, identifier, section, "--format", "text", "--body-only") == (0, content, "")


def test_body_only_section_roundtrip_preserves_other_content_and_stale_guard(archive, tmp_path):
    prefix = "Preamble.\r\n\r\n# Notebook\r\n\r\nOpening.\r\n\r\n## Selected\r\n\r\n"
    content = "  Original café.  \r\n\r\n### Child\r\n\r\nNested detail."
    suffix = "\r\n\r\n## Sibling\r\n\r\nKeep this sibling exactly.  \r\n\r\n# Appendix\r\n\r\nKeep.\r\n"
    identifier = api.create_dossier(archive, "Notebook", prefix + content + suffix)["dossier_id"]
    unrelated = api.create_dossier(archive, "Other notes", "Keep the other dossier.")["dossier_id"]
    before = retained_files(archive)
    other_before = api.get_record(archive, "dossier", unrelated)["record"]
    reviewed = api.get_dossier(archive, identifier, section="Selected")

    status, output, errors = read_section(archive, identifier, "Selected", "--format", "text", "--body-only")

    assert (status, errors) == (0, "")
    assert output == content
    edited = output.replace("Original café.", "Reviewed café.")
    draft = tmp_path / "selected.md"
    draft.write_bytes(edited.encode("utf-8"))
    flags = ("dossier", identifier, "--project", str(archive), "--section", "Selected", "--file", str(draft))
    guard = ("--expected-revision", str(reviewed["revision"]), "--expected-snapshot", reviewed["snapshot"],
             "--change-kind", "correction", "--reason", "Synthetic reviewed section correction")

    status, output, errors = capture_research(*flags, "--diff", "--format", "text")
    assert (status, errors) == (0, "")
    assert "-  Original café.  " in output and "+  Reviewed café.  " in output
    status, output, errors = capture_research(*flags, "--update", "--dry-run", *guard)
    assert (status, errors) == (0, "")
    assert json.loads(output)["schema_version"] == "research-revision-write-preview-local/1"
    assert retained_files(archive) == before

    status, output, errors = capture_research(*flags, "--update", *guard)
    assert (status, errors) == (0, "")
    assert json.loads(output)["record"]["revision"] == 2
    assert api.get_dossier(archive, identifier)["body"] == prefix + edited + suffix
    assert api.get_record(archive, "dossier", unrelated)["record"] == other_before
    after = retained_files(archive)
    assert all(after[path] == data for path, data in before.items() if not path.endswith("/HEAD.json"))

    status, output, errors = read_section(archive, identifier, "Selected", "--revision", "1",
                                          "--format", "text", "--body-only")
    assert (status, errors, output) == (0, "", content)
    assert retained_files(archive) == after

    reviewed = api.get_dossier(archive, identifier, section="Selected")
    draft.write_bytes(edited.replace("Reviewed café.", "Another review.").encode("utf-8"))
    guard = ("--expected-revision", "2", "--expected-snapshot", reviewed["snapshot"],
             "--change-kind", "correction", "--reason", "Synthetic second section correction")
    revise(archive, "dossier", identifier, {"title": "Concurrent author title"})
    concurrent = retained_files(archive)
    status, output, errors = capture_research(*flags, "--update", *guard)
    assert status == 1 and output == ""
    assert "changed" in errors and "--prepare" in errors
    assert retained_files(archive) == concurrent
    assert api.get_dossier(archive, identifier)["body"] == prefix + edited + suffix


def test_body_only_empty_section_has_no_synthetic_newline(archive):
    identifier = api.create_dossier(archive, "Notebook", "## Empty\n\n## Sibling\n\nKeep.")["dossier_id"]

    assert read_section(archive, identifier, "Empty", "--format", "text", "--body-only") == (0, "", "")


def test_body_only_redirect_preserves_utf8_crlf_and_control_bytes(archive, tmp_path):
    content = "Café.\r\n\r\n### Child\r\n\tData \x1b[2J \u202e."
    identifier = api.create_dossier(archive, "Notebook", "## Selected\r\n\r\n" + content + "\r\n")["dossier_id"]
    destination = tmp_path / "selected.md"

    with destination.open("wb") as output:
        result = subprocess.run([sys.executable, "-m", "lixity", "research", "dossier", identifier,  # noqa: S603 - synthetic local archive
                                 "--project", str(archive), "--section", "Selected", "--format", "text", "--body-only"],
                                stdout=output, stderr=subprocess.PIPE, check=False)

    assert (result.returncode, result.stderr) == (0, b"")
    assert destination.read_bytes() == content.encode("utf-8")


@pytest.mark.parametrize("control", ("\x1b[2J", "\x07", "\u202e", "\u2066", "\r"))
def test_body_only_refuses_unsafe_terminal_content_without_mutating_source(archive, control):
    content = "First line.\n\nLiteral " + control + " data."
    identifier = api.create_dossier(archive, "Notebook", "## Selected\n\n" + content)["dossier_id"]
    before = retained_files(archive)

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    output, errors = Terminal(), io.StringIO()
    args = parse_research_args("dossier", identifier, "--project", str(archive), "--section", "Selected",
                               "--format", "text", "--body-only")
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = cli.run(args)

    assert status == 1 and output.getvalue() == ""
    assert "redirect" in errors.getvalue().lower()
    assert retained_files(archive) == before
    status, output, errors = read_section(archive, identifier, "Selected", "--format", "text")
    assert (status, errors) == (0, "")
    assert control not in output
    assert control.encode("unicode_escape").decode("ascii") in output


def test_body_only_allows_safe_multiline_terminal_content(archive):
    content = "Café.\r\n\r\n### Child\r\n\tIndented detail."
    identifier = api.create_dossier(archive, "Notebook", "## Selected\r\n\r\n" + content)["dossier_id"]

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    output, errors = Terminal(), io.StringIO()
    args = parse_research_args("dossier", identifier, "--project", str(archive), "--section", "Selected",
                               "--format", "text", "--body-only")
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = cli.run(args)

    assert (status, errors.getvalue(), output.getvalue()) == (0, "", content)


@pytest.mark.parametrize("flags", (
    (), ("--format", "json"), ("--format", "table"),
    ("--format", "text", "--summary"),
    ("--format", "text", "--history"),
    ("--format", "text", "--diff", "--body", "Replacement."),
    ("--format", "text", "--prepare", "--base-revision", "1", "--body", "Replacement."),
    ("--format", "text", "--update", "--latest", "--body", "Replacement.",
     "--change-kind", "correction", "--reason", "Synthetic update"),
    ("--format", "text", "--body", "Ignored authored field."),
    ("--format", "text", "--title", "Ignored title"),
    ("--format", "text", "--file", "missing.md"),
    ("--format", "text", "--export-edit", "must-not-be-created.md"),
    ("--format", "text", "--edit-file", "missing.md", "--prepare"),
    ("--format", "text", "--output", "must-not-be-created.json"),
))
def test_body_only_rejects_non_source_read_modes_before_writing(archive, flags):
    identifier = api.create_dossier(archive, "Notebook", "## Selected\n\nOriginal.")["dossier_id"]
    before = retained_files(archive)

    status, output, errors = read_section(archive, identifier, "Selected", "--body-only", *flags)

    assert status == 1 and output == ""
    assert "--body-only" in errors
    assert retained_files(archive) == before


@pytest.mark.parametrize("selector", ((), ("list",), ("--section", "Selected")))
def test_body_only_requires_a_selected_section_read(archive, selector):
    before = retained_files(archive)

    status, output, errors = capture_research("dossier", *selector, "--project", str(archive),
                                             "--format", "text", "--body-only")

    assert status == 1 and output == ""
    assert "--body-only" in errors
    assert retained_files(archive) == before


def test_body_only_requires_section_even_with_a_selected_id(archive):
    identifier = api.create_dossier(archive, "Notebook", "## Selected\n\nOriginal.")["dossier_id"]

    status, output, errors = capture_research("dossier", identifier, "--project", str(archive),
                                             "--format", "text", "--body-only")

    assert status == 1 and output == ""
    assert "--body-only" in errors and "--section" in errors


def test_section_level_and_body_output_use_one_archive_observation(archive, monkeypatch):
    identifier = api.create_dossier(archive, "Notebook", "#### Selected\n\nDetails.")["dossier_id"]
    observe = Repository.snapshot
    observations = []

    def snapshot(repository):
        accepted = observe(repository)
        observations.append(accepted.digest)
        return accepted

    monkeypatch.setattr(Repository, "snapshot", snapshot)
    assert read_section(archive, identifier, "Selected", "--format", "text", "--body-only") == (0, "Details.", "")
    assert len(observations) == 1
