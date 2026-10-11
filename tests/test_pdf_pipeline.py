"""Shared in-memory PDF composition and selected-workspace download tokens."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from lixity.cli import main
from lixity.config import load_project_config
from lixity.style_fingerprint import FingerprintThresholds
from tests.test_pdf_export import CHOSEN, needs_fonts


class PdfPipelineTest(unittest.TestCase):
    @needs_fonts
    def test_composition_matches_existing_cli_layouts_without_writing_files(self):
        from lixity.pdf_export import compose_pdf

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manuscript = root / "synthetic.md"
            manuscript.write_text(
                "# Heading title\n\n## Über den Fluss\n\nÄÖÜ äöü ß und eine Tür.\n",
                encoding="utf-8",
            )
            (root / "lixity.toml").write_text('title = "Configured title"\nlanguage = "de"\n')
            for layout in ("book", "sheet", "report"):
                with self.subTest(layout=layout):
                    target = root / f"cli-{layout}.pdf"
                    self.assertEqual(main([
                        "pdf", str(manuscript), "--layout", layout, "--author", "Synthetic Author",
                        "--serif-font", CHOSEN.serif, "--bold-font", CHOSEN.serif_bold,
                        "--mono-font", CHOSEN.mono, "-o", str(target),
                    ]), 0)
                    before = {path.name: path.read_bytes() for path in root.iterdir()}
                    data = compose_pdf(
                        manuscript.read_text(encoding="utf-8"), manuscript=str(manuscript),
                        layout=layout, language="de", project_config=load_project_config(root),
                        author="Synthetic Author", choice=CHOSEN,
                    )
                    self.assertEqual(data, target.read_bytes())
                    self.assertEqual(before, {path.name: path.read_bytes() for path in root.iterdir()})

    def test_pdf_title_preserves_project_heading_and_filename_precedence(self):
        from lixity.pdf_export import pdf_title

        text = "# Manuscript title\n\nA synthetic paragraph."
        self.assertEqual(pdf_title("draft.md", text, {"title": " Project title "}), "Project title")
        self.assertEqual(pdf_title("draft.md", text, {}), "Manuscript title")
        self.assertEqual(pdf_title("draft.md", "A synthetic paragraph.", {}), "draft")

    @needs_fonts
    def test_download_composition_rejects_heading_only_text_without_changing_cli_semantics(self):
        from lixity.pdf_export import compose_pdf

        text = "# Synthetic title\n\n## Synthetic chapter\n"
        self.assertTrue(compose_pdf(text, manuscript="draft.md", layout="book", choice=CHOSEN))
        with self.assertRaisesRegex(ValueError, "prose"):
            compose_pdf(text, manuscript="draft.md", layout="book", choice=CHOSEN, require_prose=True)


class ManuscriptPdfTokenTest(unittest.TestCase):
    def test_token_changes_with_selected_context_without_exposing_paths(self):
        from lixity.server.pdf_context import manuscript_pdf_token

        options = {
            "project_root": "/synthetic-project", "language": "en", "title": "Synthetic title",
            "thresholds": FingerprintThresholds(),
        }
        token = manuscript_pdf_token("/synthetic-project/manuscript.md", **options)
        self.assertRegex(token, r"^[0-9a-f]{64}$")
        self.assertEqual(token, manuscript_pdf_token("/synthetic-project/manuscript.md", **options))
        for changed in (
            {"project_root": "/other-project"}, {"language": "de"}, {"title": "Another title"},
            {"thresholds": replace(options["thresholds"], z_mild=3.0)},
        ):
            with self.subTest(changed=changed):
                self.assertNotEqual(token, manuscript_pdf_token(
                    "/synthetic-project/manuscript.md", **(options | changed),
                ))
        self.assertNotEqual(token, manuscript_pdf_token("/synthetic-project/other.md", **options))
        self.assertEqual(manuscript_pdf_token(None, **options), "")
