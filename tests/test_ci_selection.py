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
            for cls in (node for node in module.body if isinstance(node, ast.ClassDef)):
                for method in (node for node in cls.body if isinstance(node, ast.FunctionDef)):
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
                        expected.add(f"tests/{path.name}::{cls.name}::{method.name}")
        self.assertTrue(expected, "No real Poppler prerequisites found")
        with tempfile.TemporaryDirectory() as cache:
            result = subprocess.run(  # noqa: S603 - fixed interpreter and pytest arguments
                [sys.executable, "-m", "pytest", "--collect-only", "-q", "-W", "error",
                 "--strict-markers", "-m", "native_pdf", "-p", "no:asyncio",
                 "-o", f"cache_dir={cache}"],
                cwd=root, capture_output=True, text=True, timeout=60, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        collected = {line for line in result.stdout.splitlines() if line.startswith("tests/")}
        self.assertEqual(collected, expected)
