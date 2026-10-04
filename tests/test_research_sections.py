"""Dossier section edits preserve unrelated text and reject ambiguous headings."""

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lixity.research import api, cli
from lixity.research.repository import ResearchError


class TestResearchSections(unittest.TestCase):
    def test_fenced_and_indented_headings_are_data_not_boundaries(self):
        body = (
            "Preamble.\n\n## Target\n\nBefore.\n```markdown\n## Fake\n```\n"
            "~~~text\n# Also fake\n~~~\n    # Indented code\nAfter.\n\n## Next\n\nKeep.\n"
        )
        sections = api.extract_sections(body)
        self.assertEqual(list(sections), ["Overview", "Target", "Next"])
        self.assertIn("## Fake", sections["Target"])
        updated = api.update_section(body, "Target", "Replacement.")
        self.assertEqual(updated, "Preamble.\n\n## Target\n\nReplacement.\n\n## Next\n\nKeep.\n")

    def test_longer_backtick_fence_and_unclosed_fence_do_not_split(self):
        body = "## Target\n\n````md\n```\n## Code\n````\n\n## Next\n\n```\n## Still code\n"
        self.assertEqual(list(api.extract_sections(body)), ["Target", "Next"])
        self.assertTrue(api.update_section(body, "Target", "Replacement").endswith("## Next\n\n```\n## Still code\n"))

    def test_duplicate_titles_are_not_silently_overwritten_or_updated(self):
        body = "## Repeat\n\nFirst.\n\n## repeat\n\nSecond.\n"
        sections = api.extract_sections(body)
        self.assertIn("First.", sections["Repeat"])
        self.assertIn("Second.", sections["Repeat"])
        with self.assertRaisesRegex(ResearchError, "ambiguous"):
            api.update_section(body, "REPEAT", "Replacement")

    def test_update_preserves_crlf_heading_and_unrelated_bytes(self):
        prefix = "Preamble  \r\n\r\n  ## Target ##\r\n"
        suffix = "## Next\r\n\r\n  Keep indentation.  \r\n\r\n"
        body = prefix + "\r\nOld.\r\n\r\n" + suffix
        self.assertEqual(api.update_section(body, "Target", "  New line.  \nSecond line."),
                         prefix + "\r\n  New line.  \r\nSecond line.\r\n\r\n" + suffix)

    def test_nested_children_belong_to_the_replaced_section(self):
        body = "# Book\n\n## Target\n\nOld.\n\n### Child\n\nChild text.\n\n## Next\n\nKeep."
        self.assertEqual(api.update_section(body, "Target", "New."),
                         "# Book\n\n## Target\n\nNew.\n\n## Next\n\nKeep.")
        deep = "##### Target\n\nOld.\n\n###### Child\n\nChild.\n\n##### Next\n\nKeep."
        self.assertIn("Next", api.extract_sections(deep))
        self.assertEqual(api.update_section(deep, "Target", "New."),
                         "##### Target\n\nNew.\n\n##### Next\n\nKeep.")

    def test_parent_section_read_and_unchanged_update_preserve_nested_content(self):
        for newline in ("\n", "\r\n"):
            body = newline.join((
                "# Book", "", "## Target", "", "Parent notes.", "",
                "### Child", "", "Child text.", "", "```markdown",
                "## Fenced example", "", "Example text.", "```", "",
                "#### Grandchild", "", "Nested notes.", "", "## Next", "", "Keep.",
            ))
            with self.subTest(newline=newline), tempfile.TemporaryDirectory() as td:
                project = Path(td) / "project"
                api.init(project, title="Synthetic section archive")
                identifier = api.create_dossier(project, "Synthetic", body)["dossier_id"]
                original_snapshot = api.get_dossier(project, identifier)["snapshot"]
                parent = api.get_dossier(project, identifier, section="Target")
                expected = body.split("## Target" + newline, 1)[1].split("## Next", 1)[0].strip()
                self.assertEqual(parent["content"], expected)
                self.assertIn("Child text.", parent["content"])
                self.assertIn("## Fenced example", parent["content"])
                self.assertIn("Nested notes.", parent["content"])
                self.assertNotIn("Keep.", parent["content"])
                self.assertEqual(api.update_section(body, "Target", parent["content"]), body)
                child = api.get_dossier(project, identifier, section="Child")
                self.assertIn("Nested notes.", child["content"])
                self.assertNotIn("Keep.", child["content"])
                sections = api.extract_sections(body)
                self.assertEqual(sections["Target"], "Parent notes.")
                self.assertNotIn("Nested notes.", sections["Child"])
                self.assertEqual(api.get_dossier(project, identifier)["snapshot"], original_snapshot)

    def test_missing_section_append_and_plain_text_overview_stay_supported(self):
        body = "Existing.\r\n"
        self.assertEqual(api.extract_sections(body), {"Overview": "Existing."})
        appended = api.update_section(body, "New", "Added.")
        self.assertTrue(appended.startswith(body))
        self.assertIn("## New\r\n\r\nAdded.\r\n", appended)
        for title in ("", "Two\nheadings", "Two\rheadings"):
            with self.subTest(title=title), self.assertRaises(ResearchError):
                api.update_section(body, title, "Content")

    def test_empty_section_and_unterminated_heading_remain_valid(self):
        self.assertEqual(api.update_section("## Target\n## Next\n\nKeep.", "Target", "New."),
                         "## Target\nNew.\n## Next\n\nKeep.")
        self.assertEqual(api.update_section("## Target", "Target", "New."), "## Target\nNew.")
        body = "## Target\n\n  Existing.  \n\n## Next\n\nKeep."
        self.assertEqual(api.update_section(body, "Target", "  Existing.  "), body)

    def test_duplicate_section_read_fails_but_full_dossier_remains_available(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic section archive")
            dossier = api.create_dossier(project, "Synthetic", "## Repeat\n\nFirst.\n\n## Repeat\n\nSecond.")
            identifier = dossier["dossier_id"]
            with self.assertRaisesRegex(ResearchError, "ambiguous"):
                api.get_dossier(project, identifier, section="repeat")
            full = api.get_dossier(project, identifier)
            self.assertIn("First.", full["section_map"]["Repeat"])
            self.assertIn("Second.", full["section_map"]["Repeat"])
            self.assertEqual(full["revision"], 1)

    def test_section_read_uses_the_same_unicode_case_matching_as_update(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic section archive")
            body = "## Straße\n\nNotes."
            identifier = api.create_dossier(project, "Synthetic", body)["dossier_id"]
            section = api.get_dossier(project, identifier, section="STRASSE")
            self.assertEqual(section["section"], "Straße")
            self.assertEqual(section["content"], "Notes.")
            self.assertEqual(api.update_section(body, "STRASSE", section["content"]), body)

    def test_large_dossier_cli_section_update_preserves_other_sections(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic large dossier")
            prefix = "# Archive\n\n" + "Synthetic archived notes. " * 5000 + "\n\n## Target\n\n"
            suffix = "\n\n## Next\n\nUntouched final notes.  \n"
            dossier = api.create_dossier(project, "Synthetic", prefix + "Old." + suffix)
            current = api.get_dossier(project, dossier["dossier_id"])
            parser = argparse.ArgumentParser()
            cli.configure(parser)
            args = parser.parse_args([
                "dossier", "--project", str(project), "--dossier-id", dossier["dossier_id"],
                "--update", "--section", "Target", "--file", "New.",
                "--expected-snapshot", current["snapshot"], "--expected-revision", "1",
                "--change-kind", "correction", "--reason", "Synthetic section update",
            ])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.run(args), 0)
            updated = json.loads(output.getvalue())
            self.assertEqual(updated["record"]["body"], prefix + "New." + suffix)
            self.assertEqual(api.get_record(project, "dossier", dossier["dossier_id"], revision=1)["record"]["body"],
                             prefix + "Old." + suffix)
