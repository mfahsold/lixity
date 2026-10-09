"""The image-attachment CLI preserves atomic research writes and retention gates."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_research_images import JPEG, png

from lixity.api import about
from lixity.cli import main
from lixity.research import api
from lixity.research.limits import MAX_IMAGE_BYTES
from lixity.research.repository import Repository


class TestDossierImageCLI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.project = self.directory / "project"
        self.project_id = api.init(self.project, title="Synthetic image attachment")["project_id"]
        self.body = "# Notes\n\n## Figures\n\nExisting figure note.\n\n## Sources\n\nExisting sources note.\n"
        self.dossier = api.create_dossier(self.project, "Synthetic dossier", self.body)["dossier_id"]
        self.file = self.directory / "picture.png"
        self.file.write_bytes(png())

    def arguments(self):
        loaded = api.get_record(self.project, "dossier", self.dossier)
        return ["research", "dossier-image", "--project", str(self.project),
                "--dossier-id", self.dossier, "--file", str(self.file),
                "--expected-snapshot", loaded["snapshot"],
                "--expected-revision", str(loaded["record"]["revision"])]

    def invoke(self, arguments):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            try:
                status = main(arguments)
            except SystemExit as exc:
                status = exc.code
        return status, output.getvalue(), error.getvalue()

    def assert_unchanged(self, snapshot, revision=1):
        self.assertEqual(Repository(self.project).snapshot().digest, snapshot)
        self.assertEqual(api.list_sources(self.project)["sources"], [])
        self.assertEqual(api.get_record(self.project, "dossier", self.dossier)["record"]["revision"], revision)
        self.assertEqual(list((self.project / "research" / "blobs").glob("*")), [])

    def test_png_and_jpeg_save_exact_bytes_context_and_selected_section(self):
        context = {"provenance_note": "Locally generated synthetic specimen.", "tags": ["synthetic"]}
        context_file = self.directory / "context.json"
        context_file.write_text(json.dumps(context), encoding="utf-8")
        for filename, content, media_type, context_arg in (
            ("one.png", png(), "image/png", str(context_file)),
            ("two.jpeg", JPEG, "image/jpeg", json.dumps(context)),
        ):
            with self.subTest(filename=filename):
                self.file = self.directory / filename
                self.file.write_bytes(content)
                before = api.get_record(self.project, "dossier", self.dossier)
                status, output, error = self.invoke([*self.arguments(),
                    "--allow-retention", "--alt", "A synthetic specimen", "--caption", "A test caption.",
                    "--section", "Figures", "--title", "Synthetic capture", "--context", context_arg,
                    "--origin-url", "https://example.org/synthetic", "--reason", "Add a specimen for review.",
                    "--change-kind", "correction", "--actor", "synthetic-reviewer",
                ])
                self.assertEqual(status, 0, error)
                self.assertEqual(error, "")
                result = json.loads(output)
                self.assertEqual(result["schema_version"], "research-record-local/1")
                self.assertEqual(result["record"]["revision"], before["record"]["revision"] + 1)
                self.assertEqual(result["record"]["created_by"], "synthetic-reviewer")
                self.assertEqual(result["record"]["change"]["change_kind"], "correction")
                self.assertEqual(result["record"]["change"]["reason"], "Add a specimen for review.")
                self.assertEqual(result["capture"]["snapshot"], result["snapshot"])
                self.assertEqual(result["capture"]["passages"], 0)
                capture = result["capture"]
                retained = api.read_image(self.project, project_id=self.project_id,
                                          source_id=capture["source_id"], version_id=capture["source_version_id"])
                self.assertEqual(retained["content"], content)
                self.assertEqual(retained["media_type"], media_type)
                source = api.get_source(self.project, capture["source_id"])
                self.assertEqual(source["title"], "Synthetic capture")
                self.assertEqual(source["context"]["provenance_note"], context["provenance_note"])
                self.assertEqual(source["context"]["tags"], ["synthetic"])
                self.assertEqual(source["context"]["origin_url"], "https://example.org/synthetic")
                figures = api.get_dossier(self.project, self.dossier, section="Figures")["content"]
                sources = api.get_dossier(self.project, self.dossier, section="Sources")["content"]
                self.assertIn("![A synthetic specimen](lixity:image/", figures)
                self.assertIn("A test caption.", figures)
                self.assertNotIn("lixity:image/", sources)
                self.assertEqual(api.get_record(self.project, "dossier", self.dossier,
                                                revision=before["record"]["revision"])["record"]["body"],
                                 before["record"]["body"])
                self.assertTrue(api.audit(self.project)["ok"])

    def test_default_attachment_appends_without_replacing_dossier_body(self):
        status, output, error = self.invoke([*self.arguments(), "--allow-retention"])
        self.assertEqual(status, 0, error)
        result = json.loads(output)
        self.assertTrue(result["record"]["body"].startswith(self.body))
        self.assertIn("![](lixity:image/", result["record"]["body"])
        self.assertEqual(result["record"]["change"]["change_kind"], "supersession")
        self.assertIn("picture.png", result["record"]["change"]["reason"])

    def test_stale_snapshot_and_revision_accept_neither_capture_nor_dossier_edit(self):
        loaded = api.get_record(self.project, "dossier", self.dossier)
        api.revise_record(self.project, "dossier", self.dossier, changes={"title": "Concurrent correction"},
                          expected_snapshot=loaded["snapshot"], expected_revision=1,
                          change_kind="correction", reason="Synthetic concurrent edit.")
        for option, stale in (("--expected-snapshot", loaded["snapshot"]), ("--expected-revision", "1")):
            with self.subTest(option=option):
                arguments = self.arguments()
                snapshot = Repository(self.project).snapshot().digest
                arguments[arguments.index(option) + 1] = stale
                status, output, error = self.invoke([*arguments, "--allow-retention"])
                self.assertEqual(status, 1)
                self.assertEqual(output, "")
                self.assertIn("changed", error)
                self.assert_unchanged(snapshot, revision=2)

    def test_unknown_section_does_not_retain_an_orphan_image(self):
        snapshot = Repository(self.project).snapshot().digest
        status, output, error = self.invoke([*self.arguments(), "--allow-retention", "--section", "Missing"])
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertIn("heading", error)
        self.assert_unchanged(snapshot)

    def test_retention_denial_precedes_image_and_context_file_reads(self):
        self.file = self.directory / "not-authorized.png"
        context = self.directory / "context.json"
        context.write_text("Invalid synthetic JSON; must not be read without permission.", encoding="utf-8")
        snapshot = Repository(self.project).snapshot().digest
        status, output, error = self.invoke([*self.arguments(), "--context", str(context)])
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertIn("retention", error)
        self.assert_unchanged(snapshot)

    def test_oversize_input_is_read_with_a_bound_and_never_retained(self):
        with self.file.open("wb") as stream:
            stream.truncate(MAX_IMAGE_BYTES * 2)
        snapshot = Repository(self.project).snapshot().digest
        original_open = Path.open
        read_sizes = []

        @contextlib.contextmanager
        def bounded_open(path, *args, **kwargs):
            with original_open(path, *args, **kwargs) as stream:
                if path == self.file and args == ("rb",):
                    class BoundedReader:
                        def read(reader, size=-1):
                            self.assertEqual(size, MAX_IMAGE_BYTES + 1, "Image input must have a bounded read")
                            read_sizes.append(size)
                            return stream.read(size)
                    yield BoundedReader()
                else:
                    yield stream

        arguments = [*self.arguments(), "--allow-retention"]
        with patch.object(Path, "open", bounded_open):
            status, output, error = self.invoke(arguments)
        self.assertEqual(read_sizes, [MAX_IMAGE_BYTES + 1])
        self.assertEqual(status, 1)
        self.assertEqual(output, "")
        self.assertIn("16 MiB", error)
        self.assert_unchanged(snapshot)

    def test_malformed_input_and_context_errors_do_not_echo_source_bytes(self):
        sentinel = "SYNTHETIC-CONTENT-NOT-FOR-ERROR-OUTPUT"
        for content, extra in ((sentinel.encode(), []), (png(), ["--context", '{"provenance_note": ' + sentinel])):
            with self.subTest(context=bool(extra)):
                self.file.write_bytes(content)
                snapshot = Repository(self.project).snapshot().digest
                status, output, error = self.invoke([*self.arguments(), "--allow-retention", *extra])
                self.assertEqual(status, 1)
                self.assertEqual(output, "")
                self.assertNotIn(sentinel, error)
                self.assert_unchanged(snapshot)

    def test_nonobject_and_malformed_contexts_are_handled_for_attachment_and_ingestion(self):
        context_file = self.directory / "invalid-context.json"
        invalid = ("1", "true", '"SYNTHETIC-CONTEXT"', "[]",
                   '[["provenance_note", "SYNTHETIC-CONTEXT"]]', "null", "{SYNTHETIC-CONTEXT")
        for command in ("dossier-image", "ingest"):
            for value_index, value in enumerate(invalid):
                context_file.write_text(value, encoding="utf-8")
                for input_index, context_arg in enumerate((value, str(context_file))):
                    with self.subTest(command=command, value=value, from_file=context_arg == str(context_file)):
                        self.project = self.directory / f"context-{command}-{value_index}-{input_index}"
                        api.init(self.project, title="Synthetic context rejection")
                        self.dossier = api.create_dossier(self.project, "Synthetic dossier", self.body)["dossier_id"]
                        arguments = self.arguments() if command == "dossier-image" else [
                            "research", "ingest", "--project", str(self.project), "--file", str(self.file)]
                        snapshot = Repository(self.project).snapshot().digest
                        status, output, error = self.invoke([
                            *arguments, "--allow-retention", "--context", context_arg])
                        self.assertEqual(status, 1)
                        self.assertEqual(output, "")
                        self.assertIn("[error]", error)
                        self.assertNotIn("SYNTHETIC-CONTEXT", error)
                        self.assert_unchanged(snapshot)

    def test_empty_object_and_absent_context_remain_valid(self):
        for command in ("dossier-image", "ingest"):
            for context_option in (["--context", "{}"], []):
                with self.subTest(command=command, context=bool(context_option)):
                    arguments = self.arguments() if command == "dossier-image" else [
                        "research", "ingest", "--project", str(self.project), "--file", str(self.file)]
                    status, output, error = self.invoke([*arguments, "--allow-retention", *context_option])
                    self.assertEqual(status, 0, error)
                    result = json.loads(output)
                    capture = result["capture"] if command == "dossier-image" else result
                    self.assertIsNone(api.get_source(self.project, capture["source_id"])["context"]["provenance_note"])

    def test_missing_required_cas_or_identity_arguments_fail_before_writing(self):
        for option in ("--project", "--dossier-id", "--file", "--expected-snapshot", "--expected-revision"):
            with self.subTest(option=option):
                arguments = [*self.arguments(), "--allow-retention"]
                offset = arguments.index(option)
                del arguments[offset:offset + 2]
                snapshot = Repository(self.project).snapshot().digest
                status, output, error = self.invoke(arguments)
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertIn(option, error)
                self.assert_unchanged(snapshot)

    def test_about_advertises_the_native_json_command(self):
        research = next(command for command in about()["commands"] if command["name"] == "research")
        command = next((item for item in research["subcommands"] if item["name"] == "dossier-image"), None)
        self.assertIsNotNone(command)
        self.assertEqual(command["default_output"], "json")
        self.assertEqual(command["output_formats"], ["json"])
