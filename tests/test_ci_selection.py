"""CI test scopes retain their intended platform and browser coverage."""

import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestNativePdfSelection(unittest.TestCase):
    def test_native_marker_matches_real_poppler_prerequisites(self):
        root = Path(__file__).resolve().parents[1]
        expected = set()
        for path in (root / "tests").glob("test_*.py"):
            module = ast.parse(path.read_text(encoding="utf-8"))
            functions = [(node.name, node) for node in module.body if isinstance(node, ast.FunctionDef)]
            functions.extend(
                (f"{cls.name}::{node.name}", node)
                for cls in module.body if isinstance(cls, ast.ClassDef)
                for node in cls.body if isinstance(node, ast.FunctionDef)
            )
            for name, method in functions:
                needs_poppler = any(
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "which"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value in {"pdftotext", "pdftoppm", "pdfinfo"}
                    for decorator in method.decorator_list
                    for node in ast.walk(decorator)
                )
                if needs_poppler:
                    expected.add(f"tests/{path.name}::{name}")
        self.assertTrue(expected, "No real Poppler prerequisites found")
        with tempfile.TemporaryDirectory() as cache:
            result = subprocess.run(  # noqa: S603 - fixed interpreter and pytest arguments
                [sys.executable, "-m", "pytest", "--collect-only", "-q", "-W", "error",
                 "--strict-markers", "-m", "native_pdf", "-p", "no:asyncio",
                 "-o", f"cache_dir={cache}"],
                cwd=root, capture_output=True, text=True, timeout=60, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        collected = {line.partition("[")[0] for line in result.stdout.splitlines()
                     if line.startswith("tests/")}
        self.assertEqual(collected, expected)


class TestNativeSuiteSelection(unittest.TestCase):
    def test_full_scope_covers_packaged_lifecycle_research_dossiers_and_settings(self):
        from scripts.run_native_tests import full_native_tests, native_pytest_args

        selected = full_native_tests()
        self.assertEqual(selected, sorted(set(selected)))
        self.assertTrue({
            "test_dossier_analysis_refresh.py",
            "test_dossier_draft_settings.py",
            "test_manuscript_dossier_confirmation.py",
            "test_manuscript_dossier_drafts.py",
            "test_manuscript_terms.py",
            "test_project_settings_write.py",
            "test_research_manuscript_links.py",
            "test_server_project_author.py",
            "test_server_startup.py",
            "test_service_native.py",
        } <= {path.name for path in selected})
        self.assertEqual(native_pytest_args("portability"), ["tests", "-m", "portability"])

    def test_incomplete_full_scope_fails_without_falling_back(self):
        from scripts.run_native_tests import native_pytest_args

        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(
            ValueError, r"Missing native test scope entries: .*test_project_settings_write\.py",
        ):
            native_pytest_args("full", Path(directory))


class TestBrowserSuiteSelection(unittest.TestCase):
    """Every browser suite belongs to an area, and --changed falls back safely."""

    def test_areas_and_groups_cover_every_suite_without_stale_names(self):
        from scripts.run_browser_suites import AREAS, GROUPS, suite_names

        actual = set(suite_names())
        self.assertGreaterEqual(len(actual), 20)
        for group, members in GROUPS.items():
            unknown = sorted(set(members) - actual)
            self.assertEqual(unknown, [], f"Unknown suites in group {group}: {unknown}")
        covered: set[str] = set()
        for area, members in AREAS.items():
            unknown = sorted(set(members) - actual)
            self.assertEqual(unknown, [], f"Unknown suites in area {area}: {unknown}")
            covered.update(members)
        unassigned = sorted(actual - covered)
        self.assertEqual(unassigned, [], f"Suites missing from AREAS: {unassigned}")

    def test_changed_mapping_selects_the_affected_area_and_falls_back_to_full(self):
        from scripts.run_browser_suites import AREAS, GROUPS, suite_names, suites_for_paths

        all_suites = suite_names()
        self.assertEqual(
            suites_for_paths(["docs/index.html"]),
            [name for name in all_suites if name in AREAS["docs"]],
        )
        self.assertEqual(
            suites_for_paths(["src/lixity/ui/assets/research-lists.js"]),
            [name for name in all_suites if name in AREAS["research"]],
        )
        self.assertEqual(
            suites_for_paths(["src/lixity/analyzer.py"]),
            [name for name in all_suites if name in GROUPS["fast"]],
        )
        # Shared foundations and unmapped UI files must run the full set.
        self.assertEqual(suites_for_paths(["src/lixity/ui/dashboard.py"]), all_suites)
        self.assertEqual(suites_for_paths(["src/lixity/ui/new_panel.py"]), all_suites)
        self.assertEqual(suites_for_paths(["tests/browser/docs.cjs"]), ["docs.cjs"])

    def test_reading_website_changes_select_their_native_and_public_journeys(self):
        from scripts.run_browser_suites import AREAS, suite_names, suites_for_paths

        expected = [name for name in suite_names() if name in AREAS["sharing"]]
        self.assertIn("reader-publication-native.cjs", expected)
        self.assertIn("site-publication-settings.cjs", expected)
        self.assertIn("docs.cjs", expected)
        self.assertNotIn("style-space.cjs", expected)
        for path in (
            "src/lixity/site_export.py", "src/lixity/site_contracts.py",
            "src/lixity/site_publications.py", "src/lixity/server/routes_site.py",
            "src/lixity/ui/publication.py", "src/lixity/ui/assets/read-only-site.js",
            "src/lixity/ui/assets/reader-publication.css",
        ):
            with self.subTest(path=path):
                self.assertEqual(suites_for_paths([path]), expected)

    def test_project_overview_changes_select_the_project_journeys(self):
        from scripts.run_browser_suites import AREAS, suite_names, suites_for_paths

        expected = [name for name in suite_names() if name in AREAS["project"]]
        self.assertIn("project-structure.cjs", expected)
        for path in (
            "src/lixity/project_structure.py", "src/lixity/ui/project_overview.py",
            "src/lixity/ui/assets/project-overview.js", "src/lixity/ui/assets/project-overview.css",
        ):
            with self.subTest(path=path):
                self.assertEqual(suites_for_paths([path]), expected)
        self.assertEqual(suites_for_paths(["tests/browser/project-structure.cjs"]), ["project-structure.cjs"])

    def test_shared_dossier_backends_and_demo_build_inputs_select_their_workflows(self):
        from scripts.run_browser_suites import AREAS, suite_names, suites_for_paths

        for path, areas, related in (
            ("src/lixity/terms.py", ("research", "sharing"), {"research-tools.cjs", "read-only-site.cjs"}),
            ("src/lixity/dossier_draft_settings.py", ("research", "project"), {"dossier-workflows.cjs", "settings.cjs"}),
            ("scripts/build_examples.py", ("docs", "sharing"), {"docs.cjs", "read-only-site.cjs"}),
            ("scripts/example_project.py", ("docs", "sharing", "research"),
             {"docs.cjs", "reader-publication.cjs", "warehouse-author.cjs"}),
            ("samples/first-look.md", ("docs", "sharing", "analysis", "research"),
             {"warehouse-author.cjs", "analysis-workflow.cjs", "docs.cjs"}),
            ("scripts/example_publications.py", ("docs", "sharing"), {"docs.cjs", "reader-publication.cjs"}),
        ):
            with self.subTest(path=path):
                expected = {suite for area in areas for suite in AREAS[area]}
                selected = suites_for_paths([path])
                self.assertTrue(related <= expected, "The listed areas must cover the affected workflows")
                self.assertEqual(selected, [name for name in suite_names() if name in expected])

    def test_shared_browser_support_and_runner_changes_select_every_suite(self):
        from scripts.run_browser_suites import suite_names, suites_for_paths

        expected = suite_names()
        for path in (
            "tests/browser/support/native-server.cjs",
            "tests/browser/support/analysis-controls.cjs",
            "tests/browser/support/python-fixture.test.cjs",
            "tests/browser/support/docs.cjs",
            "tests/browser/deleted-suite.cjs",
            "scripts/browser_tools.cjs",
            "scripts/browser-vendor.json",
            "scripts/run_browser_suites.py",
            "src/lixity/markdown_parser.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(suites_for_paths([path]), expected)

    def test_invalid_changed_base_fails_before_listing_or_running_suites(self):
        from scripts.run_browser_suites import changed_git_paths

        missing = "__lixity_missing_browser_selection_base__"
        with self.assertRaisesRegex(RuntimeError, "git diff failed"):
            changed_git_paths(missing)
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(  # noqa: S603 - fixed interpreter and local CLI
            [sys.executable, "scripts/run_browser_suites.py", "--changed", missing, "--list"],
            cwd=root, capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Cannot determine browser changes", result.stderr)
        self.assertNotIn(".cjs", result.stdout)

    def test_parallel_failure_retry_includes_every_failed_suite(self):
        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO

        from scripts.run_browser_suites import run_parallel

        def synthetic_suite(_node, name, _capture):
            return name, 0.0, 0 if name == "b.cjs" else 1, ""

        output, errors = StringIO(), StringIO()
        with patch("scripts.run_browser_suites.run_suite", side_effect=synthetic_suite), \
             redirect_stdout(output), redirect_stderr(errors):
            self.assertNotEqual(run_parallel("node", ["a.cjs", "b.cjs", "c.cjs"], 2), 0)
        self.assertIn("--only a.cjs c.cjs", errors.getvalue())
        self.assertNotIn("--start", errors.getvalue())
