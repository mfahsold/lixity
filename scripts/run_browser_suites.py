#!/usr/bin/env python3
"""Run the local browser regression suites with bounded parallel workers.

Every ``tests/browser/*.cjs`` file is an independent suite. ``--group fast``
runs the everyday core surfaces; ``--group full`` (the default) runs every
suite and belongs before a release. ``--area NAME`` runs the suites for one
surface (``docs``, ``research``, ``analysis``, ``project``, ``sharing``, ``tokens``), and
``--changed`` maps changed git paths to the affected areas (falling back to the
full set when a shared renderer or unknown UI path changed). ``--jobs N`` runs
N independent suites in parallel and keeps the machine reasonably busy; the
suites do not share state. Playwright and Chromium are optional developer
tools; ``tests/browser/README.md`` documents installation and environment
overrides. The same script backs the manual ``browser`` workflow dispatch, so
local and CI runs stay aligned.
"""

import argparse
import concurrent.futures
import fnmatch
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "tests" / "browser"

# Everyday coverage for UI work; run every suite before a release.
GROUPS: dict[str, tuple[str, ...]] = {
    "fast": (
        "anchor-navigation.cjs",
        "analysis-navigation.cjs",
        "analysis-overview.cjs",
        "layout.cjs",
        "workbench.cjs",
        "workbench-transitions.cjs",
        "tooltips.cjs",
        "overlay-layout.cjs",
        "minimal-workflows.cjs",
        "project-controls.cjs",
        "research.cjs",
        "scenes.cjs",
        "scroll-regions.cjs",
        "settings.cjs",
        "ui-usability.cjs",
        "visual-consistency.cjs",
    ),
}

# Surface areas for targeted runs (--area and --changed). Every suite belongs
# to at least one area; tests/test_ci_selection.py verifies complete coverage.
AREAS: dict[str, tuple[str, ...]] = {
    "sharing": (
        "site-preflight.cjs",
        "dossier-media.cjs",
        "read-only-site.cjs",
        "read-only-site-data.cjs",
        "reader-publication.cjs",
        "reader-publication-native.cjs",
        "site-publication-settings.cjs",
        "docs.cjs",
    ),
    "docs": (
        "docs.cjs",
        "pages-analytics.cjs",
        "typography-localization.cjs",
        "visual-consistency.cjs",
    ),
    "tokens": (
        "docs.cjs",
        "layout.cjs",
        "overlay-layout.cjs",
        "scroll-regions.cjs",
        "typography-localization.cjs",
        "visual-consistency.cjs",
    ),
    "analysis": (
        "analysis-triage.cjs",
        "analysis-triage-layout.cjs",
        "analysis-evidence.cjs",
        "linguistic-reference.cjs",
        "anchor-navigation.cjs",
        "analysis-narration.cjs",
        "analysis-navigation.cjs",
        "analysis-scope.cjs",
        "section-navigation.cjs",
        "analysis-overview.cjs",
        "contextual-help.cjs",
        "dossier-return.cjs",
        "passage-research.cjs",
        "layout.cjs",
        "overlay-layout.cjs",
        "manuscript-pdf.cjs",
        "manuscript-reader.cjs",
        "reader-document.cjs",
        "reader-feedback.cjs",
        "metric-overlays.cjs",
        "reader-large.cjs",
        "manuscript-selection.cjs",
        "manuscript-search.cjs",
        "workbench.cjs",
        "workbench-transitions.cjs",
        "tooltips.cjs",
        "minimal-workflows.cjs",
        "paragraph-feedback.cjs",
        "scenes.cjs",
        "scroll-regions.cjs",
        "style-space.cjs",
        "typography-localization.cjs",
        "ui-usability.cjs",
        "visual-consistency.cjs",
    ),
    "project": (
        "audio-profile-delete.cjs",
        "read-only-site.cjs",
        "overlay-layout.cjs",
        "debug.cjs",
        "nda-draft.cjs",
        "project-controls.cjs",
        "project-history.cjs",
        "project-structure.cjs",
        "project-switch-native.cjs",
        "publication-settings.cjs",
        "register-settings.cjs",
        "site-publication-settings.cjs",
        "settings.cjs",
        "setup-guide.cjs",
        "ui-usability.cjs",
        "visual-consistency.cjs",
    ),
    "research": (
        "dossier-document.cjs",
        "read-only-site-data.cjs",
        "reader-publication.cjs",
        "reader-publication-native.cjs",
        "research-presentation.cjs",
        "section-navigation.cjs",
        "anchor-navigation.cjs",
        "claim-evidence-actions.cjs",
        "contextual-help.cjs",
        "overlay-layout.cjs",
        "research-navigation.cjs",
        "decision-acknowledgement.cjs",
        "decision-review.cjs",
        "dossier-claims.cjs",
        "dossier-geography.cjs",
        "dossier-images.cjs",
        "dossier-return.cjs",
        "passage-research.cjs",
        "dossier-workflows.cjs",
        "list-filters.cjs",
        "manuscript-links-native.cjs",
        "manuscript-links.cjs",
        "research-chronology.cjs",
        "research-selection.cjs",
        "research-status.cjs",
        "research.cjs",
        "typography-localization.cjs",
        "workspace-reader.cjs",
    ),
}

# Path patterns -> area names; "full" forces the complete suite set when a
# shared foundation changed. Unmatched UI paths also fall back to "full".
PATH_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("scripts/run_browser_suites.py", ("full",)),
    ("scripts/browser_tools.cjs", ("full",)),
    ("docs/*", ("docs",)),
    ("scripts/stage_pages.py", ("docs",)),
    ("src/lixity/site_*.py", ("sharing",)),
    ("src/lixity/server/routes_site.py", ("sharing",)),
    ("src/lixity/ui/publication.py", ("sharing",)),
    ("src/lixity/ui/assets/read-only-site.js", ("sharing",)),
    ("src/lixity/ui/assets/reader-publication.*", ("sharing",)),
    ("src/lixity/ui/assets/design-tokens.css", ("tokens",)),
    ("src/lixity/ui/assets/components.css", ("tokens", "analysis", "project")),
    ("src/lixity/ui/assets/research*", ("research",)),
    ("src/lixity/ui/assets/zotero-results.js", ("research",)),
    ("src/lixity/ui/assets/dossier-images.*", ("research",)),
    ("src/lixity/ui/assets/dossier-geography.*", ("research",)),
    ("src/lixity/ui/assets/workspace-reader.*", ("research",)),
    ("src/lixity/ui/assets/manuscript-links.*", ("research",)),
    ("src/lixity/ui/research_panel.py", ("research",)),
    ("src/lixity/research/*", ("research",)),
    ("src/lixity/server/routes_research.py", ("research",)),
    ("src/lixity/server/routes_manuscript_research.py", ("research",)),
    ("src/lixity/ui/assets/project-ui.js", ("project",)),
    ("src/lixity/ui/assets/project-overview.*", ("project",)),
    ("src/lixity/ui/project_overview.py", ("project",)),
    ("src/lixity/project_structure.py", ("project",)),
    ("src/lixity/ui/modals.py", ("project", "research")),
    ("src/lixity/ui/settings.py", ("project",)),
    ("src/lixity/ui/assets/register-settings.js", ("project",)),
    ("src/lixity/ui/assets/site-publication-settings.js", ("project", "sharing")),
    ("src/lixity/server/routes_project.py", ("project",)),
    ("src/lixity/server/routes_nda.py", ("project",)),
    ("src/lixity/ui/assets/interactions.js", ("full",)),
    ("src/lixity/ui/assets/style-space.js", ("analysis",)),
    ("src/lixity/ui/assets/analysis-scope.*", ("analysis",)),
    ("src/lixity/ui/assets/analysis-evidence.*", ("analysis",)),
    ("src/lixity/ui/assets/section-navigation.*", ("analysis", "research")),
    ("src/lixity/ui/assets/decision-review.css", ("research",)),
    ("src/lixity/ui/assets/tooltips.js", ("full",)),
    ("src/lixity/ui/dimensions.py", ("analysis",)),
    ("src/lixity/ui/heatmap.py", ("analysis",)),
    ("src/lixity/ui/narration.py", ("analysis",)),
    ("src/lixity/ui/structural.py", ("analysis",)),
    ("src/lixity/server/routes_pdf.py", ("analysis",)),
    ("src/lixity/server/routes_markers.py", ("analysis",)),
    ("src/lixity/ui/assets/component-layer.js", ("full",)),
    ("src/lixity/ui/assets/dashboard.*", ("full",)),
    ("src/lixity/ui/dashboard.py", ("full",)),
    ("src/lixity/ui/components.py", ("full",)),
    ("src/lixity/workspace_labels.py", ("full",)),
)


def suite_names() -> list[str]:
    """Return every registered browser suite in deterministic order."""
    return [path.name for path in sorted(SUITE_DIR.glob("*.cjs"))]


def changed_git_paths(base: str | None = None) -> list[str]:
    """Return repo-relative paths modified in the working tree or since ``base``."""
    commands = (
        [["git", "diff", "--name-only", base, "HEAD"]]
        if base
        else [
            ["git", "diff", "--name-only"],
            ["git", "diff", "--cached", "--name-only"],
            ["git", "ls-files", "--others", "--exclude-standard"],
        ]
    )
    found: set[str] = set()
    for command in commands:
        result = subprocess.run(  # noqa: S603 - fixed git arguments
            command, cwd=ROOT, check=False, capture_output=True, text=True
        )
        if result.returncode:
            detail = result.stderr.strip() or f"exit {result.returncode}"
            raise RuntimeError(f"git {command[1]} failed: {detail}")
        found.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(found)


def suites_for_paths(paths: list[str], available: list[str] | None = None) -> list[str]:
    """Map repo-relative paths to the browser suites they can affect.

    Returns the fast group when no UI/docs/server/research path is present, and
    the full set when a shared foundation or an unmapped UI path changed.
    """
    names = available if available is not None else suite_names()
    known = set(names)
    selected: set[str] = set()
    relevant = False
    for raw in paths:
        path = raw.strip().lstrip("./")
        if not path:
            continue
        if path.startswith("tests/browser/") and path.endswith(".cjs"):
            relevant = True
            candidate = Path(path).name
            if path != f"tests/browser/{candidate}" or candidate not in known:
                return list(names)
            selected.add(candidate)
            continue
        matched = False
        for pattern, areas in PATH_RULES:
            if fnmatch.fnmatch(path, pattern):
                relevant = True
                matched = True
                if "full" in areas:
                    return list(names)
                for area in areas:
                    selected.update(AREAS[area])
        if not matched and path.startswith(
            ("src/lixity/ui/", "src/lixity/server/", "tests/browser/")
        ):
            return list(names)
    if not relevant:
        selected.update(GROUPS["fast"])
    return [name for name in names if name in selected]


def run_suite(node: str, name: str, capture: bool) -> tuple[str, float, int, str]:
    """Run one suite; capture its output when suites share the terminal."""
    started = time.monotonic()
    result = subprocess.run(  # noqa: S603 - fixed node binary, local reviewed suites
        [node, str(SUITE_DIR / name)],
        cwd=ROOT,
        check=False,
        capture_output=capture,
        text=True,
    )
    output = ((result.stdout or "") + (result.stderr or "")) if capture else ""
    return name, time.monotonic() - started, result.returncode, output


def report_summary(
    names: list[str], completed: int, failures: list[tuple[str, int]], seconds: float
) -> None:
    """Leave counts and every failed suite visible after the individual logs."""
    stream = sys.stderr if failures else sys.stdout
    print(
        f"Browser suite summary: {completed}/{len(names)} completed, "
        f"{completed - len(failures)} passed, {len(failures)} failed, "
        f"{len(names) - completed} not run in {seconds:.1f}s.",
        file=stream,
        flush=True,
    )
    if failures:
        print("Failed suites:", file=stream, flush=True)
        for name, code in sorted(failures):
            print(f"  {name} (exit {code})", file=stream, flush=True)


def run_parallel(node: str, names: list[str], jobs: int) -> int:
    """Run independent suites in parallel and report atomically per suite."""
    print(f"Running {len(names)} suites with {jobs} parallel workers.", flush=True)
    started = time.monotonic()
    failures: list[tuple[str, int]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_suite, node, name, True) for name in names]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            name, seconds, code, output = future.result()
            print(f"[{index}/{len(names)}] {name} ({seconds:.1f}s)", flush=True)
            if output.strip():
                print(output.rstrip(), flush=True)
            if code:
                failures.append((name, code))
                print(f"Failed: {name} (exit {code})", file=sys.stderr, flush=True)
    report_summary(names, len(names), failures, time.monotonic() - started)
    if failures:
        name, code = failures[0]
        print(f"Resume after the fix with: --start {name}", file=sys.stderr, flush=True)
        return code
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List suite filenames and exit")
    parser.add_argument("--only", nargs="+", metavar="SUITE", help="Run only these suites")
    parser.add_argument(
        "--area",
        nargs="+",
        choices=tuple(sorted(AREAS)),
        metavar="AREA",
        help="Run the suites for one or more surface areas: " + ", ".join(sorted(AREAS)),
    )
    parser.add_argument(
        "--changed",
        nargs="?",
        const="",
        default=None,
        metavar="BASE",
        help="Select suites from git changes (working tree, or diff from BASE to HEAD)",
    )
    parser.add_argument(
        "--group",
        choices=("fast", "full"),
        default="full",
        help="Run the everyday fast group or every suite (default: full)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        metavar="N",
        help="Run N independent suites in parallel (default: 1)",
    )
    parser.add_argument("--start", metavar="SUITE", help="Resume at this suite after a failure")
    arguments = parser.parse_args()

    names = suite_names()
    if not names:
        print("No browser suites found under tests/browser/.", file=sys.stderr)
        return 2

    def normalize(value: str) -> str:
        return value if value.endswith(".cjs") else value + ".cjs"

    if arguments.only:
        requested = {normalize(value) for value in arguments.only}
        unknown = sorted(requested - set(names))
        if unknown:
            parser.error("Unknown suites: " + ", ".join(unknown))
        names = [name for name in names if name in requested]
    elif arguments.area:
        selected: set[str] = set()
        for area in arguments.area:
            selected.update(AREAS[area])
        names = [name for name in names if name in selected]
    elif arguments.changed is not None:
        try:
            paths = changed_git_paths(arguments.changed or None)
        except (OSError, RuntimeError) as exc:
            parser.error(f"Cannot determine browser changes: {exc}")
        names = suites_for_paths(paths, names)
    else:
        if arguments.group == "fast":
            fast = set(GROUPS["fast"])
            unknown = sorted(fast - set(names))
            if unknown:
                parser.error("Unknown suites in group fast: " + ", ".join(unknown))
            names = [name for name in names if name in fast]
    if arguments.start:
        start = normalize(arguments.start)
        if start not in names:
            parser.error(f"Unknown suite: {start}")
        names = names[names.index(start) :]

    if arguments.list:
        print("\n".join(names))
        return 0

    node = shutil.which("node")
    if node is None:
        print("Node.js is required for the browser suites.", file=sys.stderr)
        return 2

    support_tests = sorted((SUITE_DIR / "support").glob("*.test.cjs"))
    if support_tests:
        result = subprocess.run(  # noqa: S603 - fixed node binary and local harness tests
            [node, "--test", *(str(path) for path in support_tests)], cwd=ROOT, check=False,
        )
        if result.returncode:
            print("Browser harness checks failed; UI suites were not started.", file=sys.stderr)
            return result.returncode

    if arguments.jobs > 1:
        jobs = min(arguments.jobs, len(names))
        if jobs > 1:
            return run_parallel(node, names, jobs)

    started = time.monotonic()
    for index, name in enumerate(names, start=1):
        print(f"[{index}/{len(names)}] {name}", flush=True)
        _name, seconds, code, _output = run_suite(node, name, False)
        if code:
            print(f"Failed: {name} (exit {code}, {seconds:.1f}s)", file=sys.stderr)
            report_summary(names, index, [(name, code)], time.monotonic() - started)
            print(f"Resume after the fix with: --start {name}", file=sys.stderr)
            return code
        print(f"Passed: {name} ({seconds:.1f}s)", flush=True)
    report_summary(names, len(names), [], time.monotonic() - started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
