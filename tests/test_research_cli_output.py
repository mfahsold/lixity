"""Human research output preserves machine contracts and treats metadata as data."""

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api, cli
from tests.research_support import capture_research, parse_research_args, retained_files


class TestResearchCliOutput(unittest.TestCase):
    def test_help_groups_registered_commands_without_loading_a_project(self):
        import argparse

        parser = argparse.ArgumentParser(prog="lixity research")
        cli.configure(parser)
        help_text = parser.format_help()
        self.assertIn("COMMAND ...", help_text)
        self.assertNotIn("{schema,init,", help_text)
        groups = {command["group"] for command in cli.command_metadata()}
        for group in groups:
            self.assertIn(group + ":", help_text)
        dossier = next(command for command in cli.command_metadata() if command["name"] == "dossier")
        self.assertEqual(dossier["aliases"], ["dossiers"])
        commands = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        reconcile_help = " ".join(commands.choices["reconcile-manuscript"].format_help().split())
        for scope in ("unchanged quotes", "one publication transaction", "accepted", "skipped"):
            self.assertIn(scope, reconcile_help)
        anchor_help = " ".join(commands.choices["find-anchor"].format_help().split())
        self.assertIn("case-sensitive", anchor_help)
        self.assertIn("Unicode is not normalized", anchor_help)
        self.assertIn("link/code syntax remains", anchor_help)

    def test_shell_completions_follow_the_registered_research_commands(self):
        from lixity.cli import main

        expected = {name for command in cli.command_metadata()
                    for name in (command["name"], *command.get("aliases", []))}
        for shell, pattern in (
            ("bash", r'research\)\s+COMPREPLY=\( \$\(compgen -W "([^"]+)"'),
            ("zsh", r"'1:action:\(([^)]*)\)'"),
        ):
            with self.subTest(shell=shell), patch("lixity.cli.load_project_config", return_value={}):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(["completion", shell]), 0)
                match = re.search(pattern, output.getvalue())
                self.assertIsNotNone(match)
                self.assertEqual(set(match[1].split()), expected)
                self.assertNotIn("__LIXITY_RESEARCH_COMMANDS__", output.getvalue())

    def test_record_commands_accept_an_explicit_list_verb(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="List verb", language="en")
            api.create_dossier(root, "Dossier", "Body text.")
            api.create_claim(root, title="Claim", statement="Statement.")
            api.record_decision(root, title="Decision", rationale="Reason.")
            for command, key in (("dossier", "dossiers"), ("dossiers", "dossiers"),
                                 ("claim", "claims"), ("claims", "claims"),
                                 ("decision", "decisions"), ("decisions", "decisions")):
                with self.subTest(command=command):
                    verb_status, verb_out, verb_err = self.capture(command, "list", "--project", str(root))
                    default_status, default_out, _ = self.capture(command, "--project", str(root))
                    self.assertEqual((verb_status, verb_err), (0, ""), verb_err)
                    self.assertEqual(default_status, 0)
                    self.assertEqual(json.loads(verb_out), json.loads(default_out))
                    self.assertTrue(json.loads(verb_out)[key])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="List verb conflicts", language="en")
            status, _, errors = self.capture("claim", "list", "--project", str(root), "--statement", "x")
            self.assertEqual(status, 1)
            self.assertIn("list verb", errors)

    def test_record_lists_render_tables_and_sources_accepts_list(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Table lists", language="en")
            api.create_dossier(root, "Dossier", "Body text.")
            status, out, err = self.capture("dossier", "list", "--format", "table", "--project", str(root))
            self.assertEqual((status, err), (0, ""), err)
            self.assertIn("ID", out)
            self.assertIn("Dossier", out)
            self.assertIn("1 dossier(s).", out)
            dossiers = json.loads(self.capture("dossier", "list", "--project", str(root))[1])["dossiers"]
            status, _, err = self.capture("dossier", "--format", "table", "--project", str(root),
                                          "--dossier-id", dossiers[0]["id"])
            self.assertEqual(status, 2)
            self.assertIn("list view", err)
            status, out, err = self.capture("sources", "list", "--project", str(root))
            self.assertEqual((status, err), (0, ""), err)
            self.assertIn("sources", json.loads(out))

    def test_authored_text_detail_escapes_controls_and_preserves_prose_lines(self):
        title = "Synthetic \x1b[2J title"
        body = "First paragraph.\n\nSecond \x1b]52;c;synthetic\x07 paragraph. \u202e"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic safe output")
            records = (
                ("dossier", api.create_dossier(root, title, body)["dossier_id"]),
                ("claim", api.create_claim(root, title=title, statement=body)["claim_id"]),
                ("decision", api.record_decision(root, title=title, rationale=body,
                                                impact_on_plot=body)["decision_id"]),
            )
            for kind, identifier in records:
                with self.subTest(kind=kind):
                    status, output, errors = self.capture(kind, "show", identifier, "--project", str(root),
                                                          "--format", "text")
                    self.assertEqual((status, errors), (0, ""))
                    self.assertNotIn("\x1b", output)
                    self.assertNotIn("\x07", output)
                    self.assertNotIn("\u202e", output)
                    self.assertIn(r"\x1b[2J", output)
                    self.assertIn(r"\x1b]52;c;synthetic\x07", output)
                    self.assertIn("First paragraph.\n\nSecond", output)
                    self.assertIn("Revision 1" if kind == "dossier" else "Version 1", output)
                    # JSON preserves the original data instead of rewriting the archive.
                    machine = json.loads(self.capture(kind, "show", identifier, "--project", str(root))[1])
                    self.assertEqual(machine, api.get_record(root, kind, identifier))
                    record = machine["record"]
                    self.assertEqual(record["title"], title)
                    self.assertEqual(record["revision"], 1)

    def test_authored_history_text_preserves_revision_details(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic history output")
            records = (
                ("dossier", api.create_dossier(root, "Dossier", "Dossier body.")["dossier_id"]),
                ("claim", api.create_claim(root, title="Claim", statement="Claim statement.")["claim_id"]),
                ("decision", api.record_decision(root, title="Decision", rationale="Decision rationale.")["decision_id"]),
            )
            for kind, identifier in records:
                with self.subTest(kind=kind):
                    current = api.get_record(root, kind, identifier)
                    api.revise_record(root, kind, identifier, changes={"title": "Revised title"},
                                      expected_snapshot=current["snapshot"], expected_revision=1,
                                      change_kind="correction", reason="Synthetic history correction.")
                    status, output, errors = self.capture(kind, identifier, "--project", str(root),
                                                          "--history", "--format", "text")
                    self.assertEqual((status, errors), (0, ""), errors)
                    self.assertIn(identifier, output)
                    label = "Revision" if kind == "dossier" else "Version"
                    self.assertIn(f"Latest {label.lower()}: 2", output)
                    self.assertIn(f"{label} 2", output)
                    self.assertIn(f"{label} 1", output)
                    self.assertLess(output.index(f"{label} 2"), output.index(f"{label} 1"))
                    self.assertIn("correction", output)
                    self.assertIn("Synthetic history correction.", output)
                    self.assertIn("local-author", output)
                    machine_status, machine, machine_errors = self.capture(kind, identifier, "--project", str(root), "--history")
                    self.assertEqual((machine_status, machine_errors), (0, ""))
                    self.assertEqual(json.loads(machine), api.record_history(root, kind, identifier))

    def test_dossier_text_explains_geography_in_full_summary_and_historical_reads(self):
        geography = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]},
             "properties": {"label": "Harbour"}},
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [0, 1]]},
             "properties": {"label": "Mira's journey\x1b[2J", "time_period": "1902", "actors": ["Mira"],
                            "transport": "walking", "waypoint_labels": ["Harbour", "Station"]}},
            {"type": "Feature", "geometry": None, "properties": {"label": "Unplaced meeting"}},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic geography output")
            identifier = api.create_dossier(root, "Journey notes", "Authored context.",
                                            geography=geography)["dossier_id"]
            before = retained_files(root)
            for selector in (("show", identifier), (identifier, "--summary"),
                             (identifier, "--revision", "1")):
                with self.subTest(selector=selector):
                    status, output, errors = self.capture("dossier", *selector, "--project", str(root),
                                                          "--format", "text")
                    self.assertEqual((status, errors), (0, ""), errors)
                    self.assertIn("Authored context.", output)
                    self.assertIn("Places and routes", output)
                    self.assertIn("2 located / 3", output)
                    self.assertIn("1 unplaced", output)
                    for authored in ("Harbour", "Unplaced meeting", "Mira", "1902", "walking", "Station"):
                        self.assertIn(authored, output)
                    self.assertIn("111.20 km", output)
                    self.assertIn("great-circle", output)
                    self.assertIn("not road routing", output)
                    self.assertIn("travel time", output)
                    self.assertIn(r"\x1b[2J", output)
                    self.assertNotIn("\x1b", output)
            self.assertEqual(retained_files(root), before)

    def test_dossier_text_keeps_unknown_location_distinct_from_a_zero_length_route(self):
        geography = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1, 1], [1, 1]]},
             "properties": {"label": "Recorded stationary path"}},
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[1, 1], [1.00001, 1]]},
             "properties": {"label": "Short crossing"}},
            {"type": "Feature", "geometry": None, "properties": {"label": "Unknown location"}},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic route bounds")
            identifier = api.create_dossier(root, "Known and unknown", "Notes.", geography=geography)["dossier_id"]
            status, output, errors = self.capture("dossier", identifier, "--project", str(root), "--format", "text")
            self.assertEqual((status, errors), (0, ""))
            self.assertIn("Recorded stationary path", output)
            self.assertIn("0.00 km", output)
            self.assertIn("<0.01 km", output)
            self.assertRegex(output, r"Unknown location[^\n]*[Uu]nplaced")

    def test_authored_diff_and_empty_drafts_explain_supported_inputs_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic diff output")
            records = (
                ("dossier", api.create_dossier(root, "Dossier", "Dossier body.\x1b[2J")["dossier_id"],
                 "--body", "Dossier body.", "Revised dossier body.\x1b]52;c;synthetic\x07"),
                ("claim", api.create_claim(root, title="Claim", statement="Claim statement.")["claim_id"],
                 "--statement", "Claim statement.", "Revised claim statement."),
                ("decision", api.record_decision(root, title="Decision", rationale="Decision rationale.")["decision_id"],
                 "--rationale", "Decision rationale.", "Revised decision rationale."),
            )
            before = retained_files(root)
            for kind, identifier, flag, original, replacement in records:
                with self.subTest(kind=kind):
                    for mode in (("--diff",), ("--prepare", "--base-revision", "1"),
                                 ("--update", "--expected-revision", "1", "--change-kind", "correction",
                                  "--reason", "Synthetic reviewed update")):
                        with self.subTest(mode=mode):
                            status, output, errors = self.capture(kind, identifier, "--project", str(root), *mode)
                            self.assertEqual((status, output), (1, ""))
                            self.assertIn(kind, errors)
                            self.assertIn(flag, errors)
                            self.assertIn("--inspect", errors)
                            if kind == "dossier":
                                for supported in ("--title", "--file", "--body", "--tags", "--evidence", "--geography", "--language"):
                                    self.assertIn(supported, errors)
                                self.assertNotIn("--evidence-ids", errors)
                                self.assertNotIn("--statement", errors)
                            else:
                                self.assertNotIn("--file", errors)
                                self.assertNotIn("--body", errors)
                            if kind == "decision":
                                self.assertIn("--no-deviation-from-fact", errors)
                                self.assertIn("--dossiers", errors)
                            self.assertEqual(retained_files(root), before)
                    status, output, errors = self.capture(kind, identifier, "--project", str(root),
                                                          "--diff", "--format", "text", flag, replacement)
                    self.assertEqual((status, errors), (0, ""), errors)
                    self.assertIn("preview only", output)
                    self.assertIn(identifier, output)
                    self.assertIn("-", output)
                    self.assertIn(original, output)
                    self.assertIn(replacement.encode("unicode_escape").decode("ascii"), output)
                    self.assertNotIn("\x1b", output)
                    self.assertNotIn("\x07", output)
                    self.assertEqual(retained_files(root), before)

    def test_diff_reports_nested_scope_and_reference_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic comparison")
            dossier = api.create_dossier(root, "Notes", "Body.")["dossier_id"]
            claim = api.create_claim(root, title="Place", statement="Synthetic statement.",
                                     place="Old harbour", time_period="1924", dossier_id=dossier)["claim_id"]
            from tests.research_support import revise_record
            revise_record(root, "dossier", dossier, {"title": "New notes"})
            status, output, errors = self.capture("claim", claim, "--project", str(root), "--diff",
                                                  "--place", "New harbour", "--time-period", "1925",
                                                  "--dossier-revision", "2")
            self.assertEqual((status, errors), (0, ""))
            self.assertIn('- "Old harbour"', output)
            self.assertIn('- "1924"', output)
            self.assertIn('"revision": 1', output)
            self.assertIn('"revision": 2', output)

    def test_section_diff_explains_the_observed_subtree_without_another_archive_read(self):
        from lixity.research.repository import Repository

        title = "Market\x1b]0;synthetic\x07"
        body = (f"# {title}\n\nOpening.\n\n## Audience\n\nNotes.\n\n"
                "```md\n## Not a heading\n```\n\n### Criteria\n\nDetails.\n\n"
                "# Appendix\n\nPreserve this sibling.\n")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic subtree scope")
            dossier = api.create_dossier(root, "Market notes", body)["dossier_id"]
            before = retained_files(root)
            original_snapshot = Repository.snapshot
            with patch.object(Repository, "snapshot", autospec=True,
                              side_effect=original_snapshot) as observed:
                status, output, errors = self.capture(
                    "dossier", dossier, "--project", str(root), "--diff", "--format", "text",
                    "--section", title, "--body", "Reviewed opening.",
                )
            self.assertEqual((status, errors), (0, ""))
            self.assertIn("Section scope: H1", output)
            self.assertIn("2 descendant headings", output)
            self.assertIn("replaces their content", output)
            self.assertIn(title.encode("unicode_escape").decode("ascii"), output)
            self.assertNotIn("\x1b", output)
            self.assertNotIn("\x07", output)
            self.assertEqual(observed.call_count, 1)
            self.assertEqual(retained_files(root), before)

    def test_section_diff_keeps_leaf_and_machine_output_unchanged(self):
        body = "# Overview\n\nNotes.\n\n## Leaf\n\nOld details.\n\n# Appendix\n\nKeep.\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic leaf and JSON scope")
            dossier = api.create_dossier(root, "Notes", body)["dossier_id"]
            before = retained_files(root)
            comparison = api.preview_record_changes(
                root, "dossier", dossier, changes={"body": "New."}, section="Overview",
            )
            for section in ("Overview", "Leaf"):
                with self.subTest(section=section):
                    status, output, errors = self.capture(
                        "dossier", dossier, "--project", str(root), "--diff", "--json",
                        "--section", section, "--body", "New.",
                    )
                    self.assertEqual((status, errors), (0, ""))
                    self.assertNotIn("Section scope:", output)
            for section, previous in (("Leaf", "Old details."), ("Appendix", "Keep.")):
                with self.subTest(leaf=section):
                    leaf_status, leaf, leaf_errors = self.capture(
                        "dossier", dossier, "--project", str(root), "--diff", "--format", "text",
                        "--section", section, "--body", "New.",
                    )
                    self.assertEqual((leaf_status, leaf_errors), (0, ""))
                    self.assertNotIn("Section scope:", leaf)
                    self.assertIn("-" + previous, leaf)
                    self.assertIn("+New.", leaf)
            self.assertEqual(api.preview_record_changes(
                root, "dossier", dossier, changes={"body": "New."}, section="Overview",
            ), comparison)
            self.assertEqual(retained_files(root), before)

    def test_diff_keeps_one_observation_when_another_writer_advances(self):
        from lixity.research.repository import Repository
        from tests.research_support import revise_record

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api.init(root, title="Synthetic delayed comparison")
            claim = api.create_claim(root, title="Original title", statement="Synthetic statement.")["claim_id"]
            snapshot = Repository.snapshot
            armed = True

            def delayed(repository, *args, **kwargs):
                nonlocal armed
                observed = snapshot(repository, *args, **kwargs)
                if armed:
                    armed = False
                    revise_record(root, "claim", claim, {"title": "Concurrent title"})
                return observed

            with patch.object(Repository, "snapshot", delayed):
                status, output, errors = self.capture("claim", claim, "--project", str(root),
                                                      "--diff", "--title", "Draft title")
            self.assertEqual((status, errors), (0, ""))
            self.assertIn("@r1", output)
            self.assertIn('- "Original title"', output)
            self.assertIn('+ "Draft title"', output)
            self.assertNotIn("Concurrent title", output)
            self.assertEqual(api.get_record(root, "claim", claim)["record"]["title"], "Concurrent title")

    parse = staticmethod(parse_research_args)
    capture = staticmethod(capture_research)

    def source(self, number: int = 0) -> dict:
        return {
            "id": f"urn:uuid:00000000-0000-4000-8000-{number:012d}",
            "version_id": f"urn:uuid:10000000-0000-4000-8000-{number:012d}",
            "title": f"Synthetic source {number}", "language": "de", "sequence": 2,
            "passages": 3, "tags": ["harbour", "history"],
            "context": {"origin_url": "https://example.test/archive?item=7"},
        }

    def listing(self, count: int = 1) -> dict:
        return {
            "schema_version": "research-sources-local/1", "project_id": "urn:uuid:project",
            "project_title": "Synthetic archive", "project_language": "de",
            "sources": [self.source(number) for number in range(count)],
        }

    def test_default_and_explicit_json_preserve_exact_output(self):
        audit = {"ok": False, "records": 4, "snapshot": "a" * 64,
                 "errors": ["Synthetic invalid record"], "scope": "retained records"}
        detail = {**self.source(), "passages": [{"id": "urn:uuid:passage", "verbatim": "Synthetic text"}],
                  "text": "Synthetic text"}
        for command, name, result, extra in (
            ("sources", "list_sources", self.listing(), ()),
            ("sources", "get_source", detail, ("--source-id", self.source()["id"])),
            ("audit", "audit", audit, ()),
        ):
            with self.subTest(command=command, detail=bool(extra)), patch.object(api, name, return_value=result):
                for flags in ((), ("--format", "json")):
                    status, output, errors = self.capture(command, "--project", "/synthetic", *extra, *flags)
                    self.assertEqual(status, 1 if result.get("ok") is False else 0)
                    self.assertEqual(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
                    self.assertEqual(errors, "")

    def test_human_sources_show_verified_metadata_without_source_body(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic archive", language="de")
            source = Path(td) / "source.txt"
            source.write_text("Der Hafen lag still. Die Wache öffnete das Register.", encoding="utf-8")
            capture = api.ingest(project, source, title="Harbour record", allow_retention=True,
                                 context={"tags": ["harbour", "history"],
                                          "origin_url": "https://example.test/harbour"})
            version_id = api.get_source(project, capture["source_id"])["version_id"]
            for output_format in ("text", "md"):
                for extra in ((), ("--source-id", capture["source_id"])):
                    with self.subTest(format=output_format, detail=bool(extra)):
                        status, output, errors = self.capture("sources", "--project", str(project),
                                                             "--format", output_format, *extra)
                        self.assertEqual(status, 0)
                        self.assertEqual(errors, "")
                        for value in ("Harbour record", capture["source_id"], version_id,
                                      "Active", "harbour", "history", "https://example.test/harbour"):
                            self.assertIn(value, output)
                        self.assertNotIn("Der Hafen lag still", output)
                        self.assertIn("Passages", output)

    def test_hostile_titles_tags_and_controls_remain_inert(self):
        listing = self.listing()
        title = '[red]Title[/red] | <script>alert(1)</script>\x1b[31m\x1b]52;c;secret\x07\u202e'
        listing["project_title"] = title
        listing["sources"][0]["title"] = title
        listing["sources"][0]["tags"] = ['[link=javascript:alert(1)]tag[/link]\nNext']
        with patch.object(api, "list_sources", return_value=listing):
            _, plain, _ = self.capture("sources", "--project", "/synthetic", "--format", "text")
            self.assertIn('[red]Title[/red] | <script>alert(1)</script>', plain)
            self.assertIn(r"\x1b[31m", plain)
            self.assertIn(r"\u202e", plain)
            self.assertNotIn("\x1b", plain)
            self.assertNotIn("\x07", plain)
            _, markdown, _ = self.capture("sources", "--project", "/synthetic", "--format", "md")
            self.assertIn(r"\[red\]Title\[/red\]", markdown)
            self.assertIn("&lt;script&gt;", markdown)
            self.assertIn(r"\|", markdown)
            self.assertNotIn("<script>", markdown)

    def test_human_listing_is_bounded_and_reports_total_and_offset(self):
        listing = self.listing(500)
        with patch.object(api, "list_sources", return_value=listing):
            status, output, _ = self.capture("sources", "--project", "/synthetic", "--format", "text",
                                            "--limit", "2", "--offset", "497")
            self.assertEqual(status, 0)
            self.assertIn("498–499 of 500", output)
            self.assertIn("--offset 499", output)
            self.assertIn(self.source(497)["id"], output)
            self.assertIn(self.source(498)["id"], output)
            self.assertNotIn(self.source(496)["id"], output)
            self.assertNotIn(self.source(499)["id"], output)
            self.assertLess(len(output), 3000)
            _, default_page, _ = self.capture("sources", "--project", "/synthetic", "--format", "text")
            self.assertIn("1–50 of 500", default_page)
            self.assertNotIn(self.source(50)["id"], default_page)
            _, beyond, _ = self.capture("sources", "--project", "/synthetic", "--format", "md", "--offset", "500")
            self.assertIn("No sources at offset 500", beyond)

    def test_invalid_paging_and_json_pager_do_not_call_archive(self):
        with patch.object(api, "list_sources") as listing, patch.object(api, "audit") as audit:
            for arguments in (("sources", "--limit", "1"), ("sources", "--offset", "1"),
                              ("sources", "--pager"), ("audit", "--pager"),
                              ("sources", "--source-id", "urn:uuid:source", "--format", "text", "--limit", "1")):
                with self.subTest(arguments=arguments):
                    command, *flags = arguments
                    status, output, errors = self.capture(command, "--project", "/synthetic", *flags)
                    self.assertEqual(status, 2)
                    self.assertEqual(output, "")
                    self.assertTrue(errors)
            listing.assert_not_called()
            audit.assert_not_called()
        for flags in (("--limit", "0"), ("--limit", "101"), ("--offset", "-1")):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.parse("sources", "--project", "/synthetic", "--format", "text", *flags)
            self.assertEqual(error.exception.code, 2)

    def test_pager_is_opt_in_and_never_starts_for_pipes(self):
        from rich.console import Console

        with patch.object(api, "list_sources", return_value=self.listing()), patch.object(Console, "pager") as pager:
            for output_format in ("text", "md"):
                _, direct, _ = self.capture("sources", "--project", "/synthetic", "--format", output_format)
                _, requested, _ = self.capture("sources", "--project", "/synthetic", "--format", output_format, "--pager")
                self.assertEqual(direct, requested)
            pager.assert_not_called()

    def test_explicit_interactive_pager_uses_plain_rich_output(self):
        from rich.console import Console

        class Terminal(io.StringIO):
            def isatty(self):
                return True

        with patch.object(api, "list_sources", return_value=self.listing()), \
                patch.object(Console, "pager", return_value=contextlib.nullcontext()) as pager, \
                patch("sys.stdin", Terminal()), patch("sys.stdout", Terminal()):
            self.assertEqual(cli.run(self.parse("sources", "--project", "/synthetic", "--format", "text")), 0)
            pager.assert_not_called()
            self.assertEqual(cli.run(self.parse("sources", "--project", "/synthetic", "--format", "text", "--pager")), 0)
            pager.assert_called_once_with(styles=False, links=False)

    def test_failed_audit_summary_is_actionable_bounded_and_keeps_exit_one(self):
        result = {"ok": False, "records": 14875, "snapshot": "a" * 64,
                  "scope": "retained records and citations; not factual accuracy or index freshness",
                  "errors": [f"Invalid synthetic record {number} \x1b[31m" for number in range(25)]}
        with patch.object(api, "audit", return_value=result):
            for output_format in ("text", "md"):
                status, output, errors = self.capture("audit", "--project", "/synthetic", "--format", output_format)
                self.assertEqual(status, 1)
                self.assertEqual(errors, "")
                for value in ("FAILED", "14875", "a" * 64, "25", "not factual accuracy", "verified backup", "--format json"):
                    self.assertIn(value, output)
                self.assertIn("Invalid synthetic record 19", output)
                self.assertNotIn("Invalid synthetic record 20", output)
                self.assertNotIn("\x1b", output)

    def test_empty_listing_and_successful_audit_explain_their_scope(self):
        with patch.object(api, "list_sources", return_value=self.listing(0)):
            self.assertIn("No active sources", self.capture("sources", "--project", "/synthetic", "--format", "text")[1])
        with patch.object(api, "audit", return_value={"ok": True, "records": 1, "snapshot": "b" * 64,
                                                     "errors": [], "scope": "not factual accuracy or index freshness"}):
            status, output, errors = self.capture("audit", "--project", "/synthetic", "--format", "text")
            self.assertEqual(status, 0)
            self.assertEqual(errors, "")
            self.assertIn("PASSED", output)
            self.assertIn("Findings: 0", output)
            self.assertIn("not factual accuracy or index freshness", output)

    def test_batch_cli_previews_then_requires_an_explicit_snapshot_to_apply(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic group review")
            identifiers = [api.create_dossier(project, f"Note {i}", "Original.")["dossier_id"] for i in range(2)]
            operations = [{"kind": "dossier", "id": identifier, "expected_revision": 1,
                           "changes": {"body": f"Reviewed note {i}."}, "change_kind": "correction",
                           "reason": "Reviewed together."} for i, identifier in enumerate(identifiers)]
            batch_file = Path(td) / "changes.json"
            batch_file.write_text(json.dumps(operations), encoding="utf-8")
            before = api.audit(project)["snapshot"]
            before_files = retained_files(project)
            status, output, errors = self.capture("revise-batch", "--project", str(project), "--file", str(batch_file))
            self.assertEqual((status, errors), (0, ""))
            preview = json.loads(output)
            self.assertEqual(preview["snapshot"], before)
            self.assertEqual(retained_files(project), before_files)
            batch_file.write_text(output, encoding="utf-8")
            for flags in (("--apply",), ("--expected-snapshot", before), ("--expected-snapshot", "")):
                status, output, errors = self.capture("revise-batch", "--project", str(project),
                                                      "--file", str(batch_file), *flags)
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertIn("--apply", errors)
                self.assertEqual(api.audit(project)["snapshot"], before)
            status, output, errors = self.capture("revise-batch", "--project", str(project),
                "--file", str(batch_file), "--apply", "--expected-snapshot", before, "--actor", "reviewing-author")
            self.assertEqual((status, errors), (0, ""))
            self.assertEqual(len(json.loads(output)["records"]), 2)
            for i, identifier in enumerate(identifiers):
                record = api.get_record(project, "dossier", identifier)["record"]
                self.assertEqual(record["revision"], 2)
                self.assertEqual(record["body"], f"Reviewed note {i}.")
                self.assertEqual(record["created_by"], "reviewing-author")
            status, output, errors = self.capture("revise-batch", "--project", str(project),
                "--file", str(batch_file), "--apply", "--expected-snapshot", before)
            self.assertEqual(status, 1)
            self.assertEqual(output, "")
            self.assertTrue(errors)

    def test_batch_cli_rejects_invalid_packets_without_changing_archive_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic packet validation")
            identifier = api.create_dossier(project, "Note", "Original.")["dossier_id"]
            operations = [{"kind": "dossier", "id": identifier, "expected_revision": 1,
                           "changes": {"body": "Reviewed note."}, "change_kind": "correction",
                           "reason": "Reviewed packet."}]
            packet = api.prepare_record_revisions(project, operations)
            before = retained_files(project)
            path = Path(td) / "changes.json"
            invalid = {
                "missing envelope": {"operations": operations},
                "unknown schema": packet | {"schema_version": "other/1"},
                "not reviewed": packet | {"ready": False},
                "unexpected field": packet | {"unreviewed": True},
                "non-object": "instructions",
            }
            for name, payload in invalid.items():
                path.write_text(json.dumps(payload), encoding="utf-8")
                for apply in (False, True):
                    with self.subTest(packet=name, apply=apply):
                        flags = ("--apply", "--expected-snapshot", packet["snapshot"]) if apply else ()
                        status, output, errors = self.capture("revise-batch", "--project", str(project),
                                                              "--file", str(path), *flags)
                        self.assertEqual(status, 1)
                        self.assertEqual(output, "")
                        self.assertTrue(errors)
                        self.assertEqual(retained_files(project), before)

            # Legacy raw operations still apply through the explicit snapshot guard.
            path.write_text(json.dumps(operations), encoding="utf-8")
            status, output, errors = self.capture("revise-batch", "--project", str(project), "--file", str(path),
                                                  "--apply", "--expected-snapshot", packet["snapshot"])
            self.assertEqual((status, errors), (0, ""))
            self.assertEqual(json.loads(output)["records"], [{"kind": "dossier", "id": identifier, "revision": 2}])
            self.assertEqual(api.get_record(project, "dossier", identifier)["record"]["body"], "Reviewed note.")

    def editorial_results(self) -> tuple[dict, dict]:
        impact = {"schema_version": "research-decision-impact-local/1", "snapshot": "a" * 64,
                  "scope": "Explicit associations and revision ordering; human review only.",
                  "decision": {"id": "decision-1", "title": "Review the date", "revision": 2}, "unlinked": False,
                  "dossiers": [{"id": "dossier-1", "title": "Opening date", "current_revision": 3,
                                "pinned_revisions": [1], "sections": ["Evidence", "Uncertainty"],
                                "flags": ["stale_dossier_pin"],
                                "links": [{"via": "claim", "pinned_revision": 1, "claim_id": "claim-1",
                                           "claim_revision": 2, "claim_current_revision": 3}]}]}
        review = {"schema_version": "research-editorial-review-local/1", "snapshot": "a" * 64,
                  "scope": impact["scope"], "decision_count": 1, "candidate_count": 1,
                  "candidates": [{"decision_id": "decision-1", "title": "Review the date", "decision_revision": 2,
                                  "dossier_id": "dossier-1", "dossier_title": "Opening date", "current_revision": 3,
                                  "pinned_revisions": [1], "sections": ["Evidence", "Uncertainty"],
                                  "flags": ["stale_dossier_pin"]}]}
        return impact, review

    def test_editorial_commands_default_to_readable_text_and_preserve_explicit_json(self):
        impact, review = self.editorial_results()
        for command, name, result, flags in (("decision-impact", "decision_impact", impact, ("--decision-id", "decision-1")),
                                            ("review", "editorial_review", review, ())):
            with self.subTest(command=command), patch.object(api, name, return_value=result) as report:
                for output_format in (None, "text", "md"):
                    format_flags = ("--format", output_format) if output_format else ()
                    status, output, errors = self.capture(command, "--project", "/synthetic", *flags, *format_flags)
                    self.assertEqual((status, errors), (0, ""))
                    for value in ("decision-1", "dossier-1", "Review the date", "Opening date", "older", "human review", "not semantic"):
                        self.assertIn(value, output)
                status, output, errors = self.capture(command, "--project", "/synthetic", *flags, "--format", "json")
                self.assertEqual((status, errors), (0, ""))
                self.assertEqual(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
                report.assert_called_with("/synthetic", *(flags[1:] if flags else ()))

    def test_editorial_text_bounds_candidates_and_escapes_untrusted_metadata(self):
        _, review = self.editorial_results()
        review["candidates"][0]["title"] = '[red]<script>title</script>\x1b[31m\u202e'
        review["candidates"] *= 100
        review["candidate_count"] = 100
        with patch.object(api, "editorial_review", return_value=review):
            status, output, errors = self.capture("review", "--project", "/synthetic", "--format", "md")
            self.assertEqual((status, errors), (0, ""))
            self.assertIn("&lt;script&gt;", output)
            self.assertNotIn("<script>", output)
            self.assertNotIn("\x1b", output)
            self.assertNotIn("\u202e", output)
            self.assertIn("50 further", output)
            self.assertIn("--format json", output)

    def test_empty_editorial_review_does_not_imply_semantic_approval(self):
        impact, review = self.editorial_results()
        impact.update(dossiers=[], unlinked=True)
        review.update(candidates=[], candidate_count=0)
        with patch.object(api, "editorial_review", return_value=review):
            _, output, _ = self.capture("review", "--project", "/synthetic")
            self.assertIn("No structural review candidates", output)
            self.assertIn("not semantic", output)
        with patch.object(api, "decision_impact", return_value=impact):
            _, output, _ = self.capture("decision-impact", "--project", "/synthetic", "--decision-id", "decision-1")
            self.assertIn("No explicitly linked dossiers", output)

    def test_editorial_commands_inspect_real_synthetic_links_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic editorial review")
            dossier = api.create_dossier(project, "Opening date", "## Evidence\nA dated register.")["dossier_id"]
            decision = api.record_decision(project, title="Keep the date", rationale="Use the dated record.",
                                           dossier_ids=[dossier])["decision_id"]
            loaded = api.get_record(project, "dossier", dossier)
            api.revise_record(project, "dossier", dossier, changes={"body": "## Evidence\nA reviewed register.\n## Uncertainty\nName missing."},
                              expected_snapshot=loaded["snapshot"], expected_revision=1,
                              change_kind="correction", reason="Review the source.")
            before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
            for command, flags in (("review", ()), ("decision-impact", ("--decision-id", decision))):
                status, output, errors = self.capture(command, "--project", str(project), *flags)
                self.assertEqual((status, errors), (0, ""))
                for value in (decision, dossier, "Opening date", "Evidence", "Uncertainty", "older"):
                    self.assertIn(value, output)
            self.assertEqual(before, {p: p.read_bytes() for p in project.rglob("*") if p.is_file()})
