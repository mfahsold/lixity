"""CI compatibility selection must exclude only tests needing real Poppler tools."""

import ast
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


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
            "scripts/run_browser_suites.py",
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
