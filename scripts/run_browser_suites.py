#!/usr/bin/env python3
"""Run the local browser regression suites with bounded parallel workers.

Every ``tests/browser/*.cjs`` file is an independent suite. ``--group fast``
runs the everyday core surfaces; ``--group full`` (the default) runs every
suite and belongs before a release. ``--area NAME`` runs the suites for one
surface (``analysis``, ``audio``, ``docs``, ``project``, ``research``, ``sharing``,
``tokens``), and
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
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = ROOT / "tests" / "browser"

# Everyday coverage for UI work; run every suite before a release.
GROUPS: dict[str, tuple[str, ...]] = {
    "fast": (
        "audio-permission.cjs",
        "audio-phonetics.cjs",
        "audio-export.cjs",
        "anchor-navigation.cjs",
        "analysis-navigation.cjs",
        "analysis-overview.cjs",
        "analysis-workflow.cjs",
        "warehouse-author.cjs",
        "layout.cjs",
        "reader-toolbar.cjs",
        "workbench.cjs",
        "workbench-transitions.cjs",
        "tooltips.cjs",
        "tooltips-dialog.cjs",
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

AUDIO_STUDIO_SUITES = (
    "audio-chapter-import.cjs",
    "audio-take.cjs",
    "audio-take-studio.cjs",
    "audio-phonetics.cjs",
    "audio-loading.cjs",
    "audio-microphone.cjs",
    "audio-permission.cjs",
    "audio-player.cjs",
    "audio-probe.cjs",
    "audio-references.cjs",
    "audio-recording-diagnostics.cjs",
    "audio-studio.cjs",
    "teleprompter-context.cjs",
    "teleprompter-plan.cjs",
    "teleprompter-scroll.cjs",
    "teleprompter-take.cjs",
    "audio-pronunciations.cjs",
    "audio-profile-delete.cjs",
)

# Surface areas for targeted runs (--area and --changed). Every suite belongs
# to at least one area; tests/test_ci_selection.py verifies complete coverage.
AREAS: dict[str, tuple[str, ...]] = {
    "audio": (
        *AUDIO_STUDIO_SUITES,
        "audio-export.cjs",
        "project-controls.cjs",
        "reader-audio.cjs",
        "settings.cjs",
        "typography-localization.cjs",
        "workbench.cjs",
    ),
    "sharing": (
        "reader-audio.cjs",
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
        "home-tour.cjs",
        "docs.cjs",
        "pages-analytics.cjs",
        "pages-language.cjs",
        "typography-localization.cjs",
        "visual-consistency.cjs",
    ),
    "tokens": (
        "docs.cjs",
        "layout.cjs",
        "reader-toolbar.cjs",
        "overlay-layout.cjs",
        "scroll-regions.cjs",
        "typography-localization.cjs",
        "visual-consistency.cjs",
    ),
    "analysis": (
        "warehouse-author.cjs",
        "manuscript-editor.cjs",
        "editor-features.cjs",
        "editor-navigation.cjs",
        "audio-export.cjs",
        "structural-coverage.cjs",
        "analysis-triage.cjs",
        "analysis-triage-layout.cjs",
        "analysis-evidence.cjs",
        "tense-thresholds.cjs",
        "linguistic-reference.cjs",
        "anchor-navigation.cjs",
        "analysis-narration.cjs",
        "analysis-navigation.cjs",
        "analysis-scope.cjs",
        "section-navigation.cjs",
        "analysis-overview.cjs",
        "analysis-workflow.cjs",
        "contextual-help.cjs",
        "dossier-return.cjs",
        "passage-research.cjs",
        "layout.cjs",
        "reader-toolbar.cjs",
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
        "tooltips-dialog.cjs",
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
        *AUDIO_STUDIO_SUITES,
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
        "warehouse-author.cjs",
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
        "research-tools.cjs",
        "decision-acknowledgement.cjs",
        "decision-review.cjs",
        "dossier-claims.cjs",
        "dossier-collections.cjs",
        "dossier-geography.cjs",
        "dossier-images.cjs",
        "dossier-return.cjs",
        "passage-research.cjs",
        "dossier-workflows.cjs",
        "markdown-editor.cjs",
        "command-palette.cjs",
        "list-filters.cjs",
        "manuscript-links-native.cjs",
        "manuscript-links.cjs",
        "research-chronology.cjs",
        "research-import.cjs",
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
    ("scripts/browser-vendor.json", ("full",)),
    ("src/lixity/config.py", ("full",)),
    ("src/lixity/server/desktop.py", ("full",)),
    ("src/lixity/ui/assets/desktop-bridge.js", ("full",)),
    ("desktop/src-tauri/src/lib.rs", ("full",)),
    ("desktop/src-tauri/src/sidecar.rs", ("full",)),
    ("docs/*", ("docs",)),
    ("scripts/stage_pages.py", ("docs",)),
    ("scripts/build_public_site.py", ("docs",)),
    ("scripts/capture_screenshots.cjs", ("docs",)),
    ("scripts/make_screenshots.py", ("docs",)),
    ("scripts/make_videos.py", ("docs",)),
    ("scripts/product_tour_capture.cjs", ("docs",)),
    ("scripts/product_tour_edit.py", ("docs",)),
    ("scripts/build_examples.py", ("docs", "sharing")),
    ("scripts/build_demo_audio.py", ("audio", "docs")),
    ("scripts/example_project.py", ("docs", "sharing", "research")),
    ("samples/first-look.md", ("docs", "sharing", "analysis", "research")),
    ("scripts/example_publications.py", ("docs", "sharing")),
    ("src/lixity/site_*.py", ("sharing",)),
    ("src/lixity/server/routes_site.py", ("sharing",)),
    ("src/lixity/ui/publication.py", ("sharing",)),
    ("src/lixity/ui/assets/read-only-site.js", ("sharing",)),
    ("src/lixity/ui/assets/reader-publication.*", ("sharing",)),
    ("src/lixity/ui/assets/reader-audio.js", ("sharing",)),
    ("src/lixity/speech*.py", ("audio",)),
    ("src/lixity/audio_audit.py", ("audio",)),
    ("src/lixity/audio_pcm.py", ("audio",)),
    ("src/lixity/server/routes_speech.py", ("audio",)),
    ("src/lixity/ui/assets/audio-*.js", ("audio",)),
    ("src/lixity/ui/assets/speech*.*", ("audio",)),
    ("src/lixity/ui/assets/teleprompter.*", ("audio",)),
    ("desktop/src-tauri/src/audio_capture.rs", ("audio",)),
    ("desktop/src-tauri/src/commands.rs", ("audio", "project", "sharing")),
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
    ("src/lixity/terms.py", ("research", "sharing")),
    ("src/lixity/dossier_draft_settings.py", ("research", "project")),
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
    ("src/lixity/ui/assets/analysis-passage-navigation.js", ("analysis", "sharing")),
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
    ("src/lixity/markdown_parser.py", ("full",)),
    ("src/lixity/workspace_labels.py", ("full",)),
    ("src/lixity/locales/*", ("full",)),
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

    Returns the fast group when no mapped path is present, and
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


def browser_environment() -> dict[str, str]:
    """Bound each suite's Node heap unless the caller already chose a limit."""
    environment = dict(os.environ)
    options = environment.get("NODE_OPTIONS", "")
    if not re.search(r"--max[-_]old[-_]space[-_]size(?:=|\s)", options):
        environment["NODE_OPTIONS"] = (options + " --max-old-space-size=2048").strip()
    return environment


class BrowserEvidence:
    """Persist bounded evidence from reviewed synthetic suites, never project trees.

    A killed runner leaves its last atomic snapshot with active/not-run states.
    Only failed processes retain PNGs, preserving the budget for failures. They
    are copied from temporary directories created for these subprocesses; suites
    that hardcode /tmp paths retain their logs but not those captures.
    """

    LOG_BYTES = 128 * 1024
    CAPTURE_BYTES = 2 * 1024 * 1024
    CAPTURE_COUNT = 4
    TOTAL_CAPTURE_BYTES = 64 * 1024 * 1024

    def __init__(self, directory: Path, names: list[str], jobs: int):
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        (directory / "logs").mkdir()
        (directory / "captures").mkdir()
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.capture_bytes = 0
        self.stopped = threading.Event()
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "status": "running",
            "started_at": self.timestamp(),
            "finished_at": None,
            "jobs": jobs,
            "full_matrix": os.environ.get("LIXITY_BROWSER_FULL") == "1",
            "preflight": {"status": "not_run"},
            "suites": [{"name": name, "status": "not_run"} for name in names],
            "limits": {
                "log_bytes_per_process": self.LOG_BYTES,
                "capture_bytes_per_file": self.CAPTURE_BYTES,
                "captures_per_suite": self.CAPTURE_COUNT,
                "capture_bytes_total": self.TOTAL_CAPTURE_BYTES,
                "capture_policy": "failed_processes_only",
            },
        }
        self.refresh()
        self.heartbeat = threading.Thread(target=self._heartbeat, daemon=True)
        self.heartbeat.start()

    @staticmethod
    def timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _write(self) -> None:
        statuses = [item["status"] for item in self.data["suites"]]
        self.data["counts"] = {
            "selected": len(statuses),
            "completed": statuses.count("passed") + statuses.count("failed"),
            **{status: statuses.count(status) for status in ("passed", "failed", "active", "not_run")},
        }
        self.data["seconds"] = round(time.monotonic() - self.started, 3)
        self.data["updated_at"] = self.timestamp()
        temporary = self.directory / "results.json.tmp"
        temporary.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.directory / "results.json")

    def refresh(self) -> None:
        with self.lock:
            self._write()

    def _heartbeat(self) -> None:
        while not self.stopped.wait(1):
            self.refresh()

    def finish(self, code: int) -> None:
        self.stopped.set()
        self.heartbeat.join()
        with self.lock:
            self.data["status"] = "failed" if code else "passed"
            self.data["finished_at"] = self.timestamp()
            self._write()

    def _captures(self, workspace: Path, name: str) -> tuple[list[str], bool]:
        kept: list[str] = []
        truncated = False
        # os.walk does not follow directory symlinks; validate each file too.
        for directory, children, files in os.walk(workspace, followlinks=False):
            children.sort()
            for filename in sorted(files):
                source = Path(directory) / filename
                if source.suffix.lower() != ".png" or source.is_symlink():
                    continue
                if not source.resolve().is_relative_to(workspace.resolve()):
                    continue
                size = source.stat().st_size
                if size > self.CAPTURE_BYTES:
                    truncated = True
                    continue
                with source.open("rb") as image:
                    if image.read(8) != b"\x89PNG\r\n\x1a\n":
                        continue
                if (len(kept) == self.CAPTURE_COUNT
                        or self.capture_bytes + size > self.TOTAL_CAPTURE_BYTES):
                    return kept, True
                target = Path("captures") / f"{name}-{len(kept) + 1}.png"
                shutil.copyfile(source, self.directory / target)
                self.capture_bytes += size
                kept.append(target.as_posix())
        return kept, truncated

    def _process(self, command: list[str], name: str, record: dict[str, Any]) -> tuple[float, int, str]:
        started = time.monotonic()
        log = Path("logs") / f"{name}.log"
        (self.directory / log).write_bytes(b"")
        with self.lock:
            record.update(status="active", started_at=self.timestamp(), log=log.as_posix())
            self._write()
        with tempfile.TemporaryDirectory(prefix="lixity-browser-run-") as directory:
            workspace = Path(directory)
            environment = {**browser_environment(), "TMPDIR": directory, "TMP": directory, "TEMP": directory,
                           "LIXITY_TEST_AUDIO_DIAGNOSTICS": "1"}
            tail = b""
            total = 0

            def retain(chunk: bytes) -> None:
                nonlocal tail, total
                total += len(chunk)
                tail = (tail + chunk)[-self.LOG_BYTES:]
                # Paths are useful as roles, not as local machine identifiers.
                clean = tail
                for path, label in ((directory, "<suite-temp>"), (str(ROOT), "<checkout>"),
                                    (str(Path.home()), "<home>")):
                    clean = clean.replace(path.encode(), label.encode())
                # A byte bound may split a multibyte character at either edge.
                (self.directory / log).write_bytes(
                    clean[-self.LOG_BYTES:].decode("utf-8", errors="ignore").encode("utf-8"),
                )

            try:
                with subprocess.Popen(  # noqa: S603 - reviewed local suites, fixed executable
                    command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                ) as process:
                    if process.stdout is None:
                        raise RuntimeError("Browser subprocess output pipe unavailable")
                    while chunk := process.stdout.read1(8192):
                        retain(chunk)
                    code = process.wait()
            except OSError as exc:
                retain(f"Cannot execute browser check: {exc}\n".encode())
                code = 2
            if not (self.directory / log).exists():
                (self.directory / log).write_bytes(b"")
            seconds = time.monotonic() - started
            with self.lock:
                captures, truncated = self._captures(workspace, name) if code else ([], False)
                record.update(
                    status="failed" if code else "passed", exit_code=code,
                    seconds=round(seconds, 3), finished_at=self.timestamp(),
                    log_truncated=total > self.LOG_BYTES, captures=captures,
                    captures_truncated=truncated,
                )
                self._write()
        return seconds, code, (self.directory / log).read_text(encoding="utf-8")

    def preflight(self, command: list[str]) -> int:
        _seconds, code, output = self._process(command, "harness", self.data["preflight"])
        if output:
            print(output.rstrip(), flush=True)
        return code

    def no_preflight(self) -> None:
        with self.lock:
            self.data["preflight"] = {
                "status": "not_required", "reason": "No support harness tests found.",
            }
            self._write()

    def run_suite(self, node: str, name: str, _capture: bool) -> tuple[str, float, int, str]:
        record = next(item for item in self.data["suites"] if item["name"] == name)
        seconds, code, output = self._process([node, str(SUITE_DIR / name)], name, record)
        return name, seconds, code, output


def run_suite(node: str, name: str, capture: bool) -> tuple[str, float, int, str]:
    """Run one suite; capture its output when suites share the terminal."""
    started = time.monotonic()
    result = subprocess.run(  # noqa: S603 - fixed node binary, local reviewed suites
        [node, str(SUITE_DIR / name)],
        cwd=ROOT,
        check=False,
        capture_output=capture,
        env=browser_environment(),
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


def report_durations(timings: list[tuple[str, float]], limit: int) -> None:
    """Expose measured bottlenecks without caching or changing test selection."""
    if not timings or limit == 0:
        return
    print("Slowest browser suites (wall time, including worker contention):", flush=True)
    for name, seconds in sorted(timings, key=lambda item: (-item[1], item[0]))[:limit]:
        print(f"  {seconds:.1f}s {name}", flush=True)


def diagnostic_counts(data: Any) -> dict[str, int]:
    """Validate the supported result contract before making summary claims."""
    if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1 or data.get("status") not in ("running", "passed", "failed")
            or type(data.get("full_matrix")) is not bool):
        raise ValueError("Unsupported browser result schema or run state")

    def duration(value: Any) -> None:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid browser duration")

    def process(record: Any, *, preflight: bool = False) -> None:
        allowed = ("not_run", "active", "passed", "failed") + (("not_required",) if preflight else ())
        if not isinstance(record, dict) or record.get("status") not in allowed:
            raise ValueError("Unknown browser process state")
        status = record["status"]
        if "seconds" in record:
            duration(record["seconds"])
        if status in ("passed", "failed"):
            duration(record["seconds"])
            code = record.get("exit_code")
            if type(code) is not int or (code == 0) != (status == "passed"):
                raise ValueError("Browser exit code contradicts process state")
        elif record.get("exit_code") is not None:
            raise ValueError("Unfinished browser process has an exit code")
        if status == "not_required" and (
            not isinstance(record.get("reason"), str) or not record["reason"].strip()
        ):
            raise ValueError("Missing reason for an unneeded preflight")

    duration(data["seconds"])
    process(data["preflight"], preflight=True)
    suites = data["suites"]
    if not isinstance(suites, list):
        raise ValueError("Browser suite records must be a list")
    names: set[str] = set()
    counts = dict.fromkeys(("passed", "failed", "active", "not_run"), 0)
    for suite in suites:
        process(suite)
        name = suite.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Missing or duplicate browser suite name")
        names.add(name)
        counts[suite["status"]] += 1
    counts.update(selected=len(suites), completed=counts["passed"] + counts["failed"])
    saved = data["counts"]
    if (not isinstance(saved, dict) or saved.keys() != counts.keys()
            or any(type(value) is not int or value < 0 for value in saved.values())
            or saved != counts):
        raise ValueError("Browser aggregate contradicts suite records")
    jobs = data["jobs"]
    if type(jobs) is not int or jobs < 0 or (bool(jobs) != bool(suites)):
        raise ValueError("Invalid browser worker count")
    if data["status"] == "passed" and (
        counts["passed"] != counts["selected"]
        or data["preflight"]["status"] not in ("passed", "not_required")
    ):
        raise ValueError("Passed browser run has incomplete or failed checks")
    return counts


def diagnostic_summary(directory: Path) -> str:
    """Render saved evidence even when the browser step failed or was terminated."""
    try:
        data = json.loads((directory / "results.json").read_text(encoding="utf-8"))
        counts = diagnostic_counts(data)
        lines = [
            "### Browser regression evidence", "",
            f"Runner state: **{data['status']}** (last saved snapshot; the job conclusion is authoritative).",
            f"{counts['completed']}/{counts['selected']} completed, "
            f"{counts['passed']} passed, {counts['failed']} failed, "
            f"{counts['active']} active, {counts['not_run']} not run in {data['seconds']:.1f}s.",
            f"{data['jobs']} workers; "
            f"{'full locale matrix' if data['full_matrix'] else 'everyday locale matrix'}; "
            f"harness: {data['preflight']['status']}.", "",
        ]
        for status, label in (("failed", "Failed suites"),
                              ("active", "Active in last saved snapshot"), ("not_run", "Not run")):
            items = [f"`{item['name']}`" + (f" (exit {item['exit_code']})" if status == "failed" else "")
                     for item in data["suites"] if item["status"] == status]
            if items:
                lines.append(f"{label}: " + ", ".join(items) + ".")
        completed = [item for item in data["suites"] if item["status"] in ("passed", "failed")]
        if completed:
            lines.extend(("", "Slowest completed suites (wall time, including worker contention):", ""))
            lines.extend(f"- {item['seconds']:.1f}s `{item['name']}`"
                         for item in sorted(completed,
                                            key=lambda item: (-item["seconds"], item["name"]))[:5])
        lines.extend(("", "The artifact contains bounded synthetic logs and owned PNG captures "
                      "from failed processes only. An interrupted run may have incomplete logs or captures."))
        return "\n".join(lines)
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return "Browser result manifest unavailable or invalid; inspect the job logs. Results are unknown."


_SLOW_SUITES_ORDER = (
    "settings.cjs",
    "visual-consistency.cjs",
    "scroll-regions.cjs",
    "research.cjs",
    "analysis-overview.cjs",
    "reader-toolbar.cjs",
    "analysis-navigation.cjs",
    "project-controls.cjs",
    "scenes.cjs",
    "docs.cjs",
    "manuscript-reader.cjs",
    "manuscript-links.cjs",
    "analysis-evidence.cjs",
)


# Full-matrix wall times from GitHub release runs 43936636750, 43955134184
# and 45481787784 (two workers per shard). Each weight is the slowest
# observation, rounded up.
_FULL_SUITE_SECONDS = {
    "analysis-evidence.cjs": 250,
    "analysis-narration.cjs": 87,
    "analysis-navigation.cjs": 131,
    "analysis-overview.cjs": 103,
    "analysis-scope.cjs": 15,
    "analysis-triage-layout.cjs": 6,
    "analysis-triage.cjs": 7,
    "analysis-workflow.cjs": 8,
    "anchor-navigation.cjs": 25,
    "audio-chapter-import.cjs": 6,
    "audio-export.cjs": 17,
    "audio-loading.cjs": 5,
    "audio-microphone.cjs": 5,
    "audio-permission.cjs": 12,
    "audio-phonetics.cjs": 11,
    "audio-player.cjs": 3,
    "audio-profile-delete.cjs": 4,
    "audio-pronunciations.cjs": 7,
    "audio-recording-diagnostics.cjs": 7,
    "audio-references.cjs": 52,
    "audio-studio.cjs": 23,
    "audio-take-studio.cjs": 6,
    "audio-take.cjs": 1,
    "claim-evidence-actions.cjs": 53,
    "command-palette.cjs": 1,
    "contextual-help.cjs": 110,
    "debug.cjs": 9,
    "decision-acknowledgement.cjs": 29,
    "decision-review.cjs": 44,
    "docs.cjs": 303,
    "dossier-claims.cjs": 49,
    "dossier-collections.cjs": 24,
    "dossier-document.cjs": 12,
    "dossier-geography.cjs": 31,
    "dossier-images.cjs": 31,
    "dossier-media.cjs": 6,
    "dossier-return.cjs": 42,
    "dossier-workflows.cjs": 42,
    "editor-features.cjs": 10,
    "editor-navigation.cjs": 4,
    "home-tour.cjs": 30,
    "layout.cjs": 63,
    "linguistic-reference.cjs": 67,
    "list-filters.cjs": 34,
    "manuscript-editor.cjs": 13,
    "manuscript-links-native.cjs": 12,
    "manuscript-links.cjs": 58,
    "manuscript-pdf.cjs": 36,
    "manuscript-reader.cjs": 62,
    "manuscript-search.cjs": 40,
    "manuscript-selection.cjs": 5,
    "markdown-editor.cjs": 1,
    "metric-overlays.cjs": 80,
    "minimal-workflows.cjs": 20,
    "nda-draft.cjs": 22,
    "overlay-layout.cjs": 25,
    "pages-analytics.cjs": 18,
    "pages-language.cjs": 15,
    "paragraph-feedback.cjs": 14,
    "passage-research.cjs": 60,
    "project-controls.cjs": 58,
    "project-history.cjs": 20,
    "project-structure.cjs": 24,
    "project-switch-native.cjs": 11,
    "publication-settings.cjs": 9,
    "read-only-site-data.cjs": 15,
    "read-only-site.cjs": 50,
    "reader-audio.cjs": 7,
    "reader-document.cjs": 4,
    "reader-feedback.cjs": 25,
    "reader-large.cjs": 15,
    "reader-publication-native.cjs": 22,
    "reader-publication.cjs": 18,
    "reader-toolbar.cjs": 49,
    "register-settings.cjs": 18,
    "research-chronology.cjs": 31,
    "research-import.cjs": 4,
    "research-navigation.cjs": 50,
    "research-presentation.cjs": 113,
    "research-selection.cjs": 29,
    "research-status.cjs": 4,
    "research-tools.cjs": 21,
    "research.cjs": 75,
    "scenes.cjs": 49,
    "scroll-regions.cjs": 89,
    "section-navigation.cjs": 98,
    "settings.cjs": 204,
    "setup-guide.cjs": 21,
    "site-preflight.cjs": 34,
    "site-publication-settings.cjs": 17,
    "structural-coverage.cjs": 6,
    "style-space.cjs": 52,
    "teleprompter-context.cjs": 4,
    "teleprompter-plan.cjs": 2,
    "teleprompter-scroll.cjs": 2,
    "teleprompter-take.cjs": 12,
    "tense-thresholds.cjs": 12,
    "tooltips-dialog.cjs": 2,
    "tooltips.cjs": 19,
    "typography-localization.cjs": 18,
    "ui-usability.cjs": 14,
    "visual-consistency.cjs": 357,
    "workbench-transitions.cjs": 21,
    "workbench.cjs": 20,
    "workspace-reader.cjs": 34,
}
# Round up the upper quartile so new suites receive a conservative estimate.
_UNMEASURED_SUITE_SECONDS = 49


def ordered_suites(names: list[str]) -> list[str]:
    """Order slowest known suites first to avoid tail-latency bottlenecks."""
    priority = {suite: idx for idx, suite in enumerate(_SLOW_SUITES_ORDER)}
    return sorted(names, key=lambda n: (priority.get(n, len(_SLOW_SUITES_ORDER)), n))


def estimate_suite_seconds(name: str) -> int:
    """Return the full-matrix scheduling weight in seconds."""
    return _FULL_SUITE_SECONDS.get(name, _UNMEASURED_SUITE_SECONDS)


def select_shard(names: list[str], spec: str) -> list[str]:
    """Assign the longest suites first to the shard with the least estimated work."""
    match = re.fullmatch(r"([1-9]\d*)/([1-9]\d*)", spec.strip())
    if match is None:
        raise ValueError("--shard must be INDEX/TOTAL (for example 1/4)")
    index, total = int(match.group(1)), int(match.group(2))
    if index > total:
        raise ValueError("--shard INDEX must be <= TOTAL")
    if index > len(names):
        return []

    active_shards = range(min(total, len(names)))
    shards: list[list[str]] = [[] for _ in active_shards]
    workloads = [0 for _ in active_shards]
    for name in sorted(names, key=lambda name: (-estimate_suite_seconds(name), name)):
        shard = min(active_shards, key=lambda i: (workloads[i], len(shards[i]), i))
        shards[shard].append(name)
        workloads[shard] += estimate_suite_seconds(name)
    return shards[index - 1]


def run_parallel(
    node: str, names: list[str], jobs: int, durations: int = 5,
    evidence: BrowserEvidence | None = None,
) -> int:
    """Queue independent suites in scheduled order and report atomically per suite."""
    print(f"Running {len(names)} suites with {jobs} parallel workers.", flush=True)
    started = time.monotonic()
    failures: list[tuple[str, int]] = []
    timings: list[tuple[str, float]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        execute = evidence.run_suite if evidence else run_suite
        futures = [pool.submit(execute, node, name, True) for name in names]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            name, seconds, code, output = future.result()
            timings.append((name, seconds))
            print(f"[{index}/{len(names)}] {name} ({seconds:.1f}s)", flush=True)
            if output.strip():
                print(output.rstrip(), flush=True)
            if code:
                failures.append((name, code))
                print(f"Failed: {name} (exit {code})", file=sys.stderr, flush=True)
    report_durations(timings, durations)
    report_summary(names, len(names), failures, time.monotonic() - started)
    if failures:
        failed = sorted(name for name, _ in failures)
        print(f"Rerun failed suites with: {shlex.join(['--only', *failed])}", file=sys.stderr, flush=True)
        print("Run the full suite again before a release.", file=sys.stderr, flush=True)
        return failures[0][1]
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
        default=min(8, max(2, (os.cpu_count() or 4) // 2)),
        metavar="N",
        help="Run N independent suites in parallel (default: cpu_count // 2, clamped to 2..8)",
    )
    parser.add_argument("--start", metavar="SUITE", help="Resume at this suite after a failure")
    parser.add_argument(
        "--shard", metavar="INDEX/TOTAL",
        help="Run duration-balanced shard INDEX of TOTAL (1-based, e.g. 1/4)",
    )
    parser.add_argument(
        "--durations", type=int, default=5, metavar="N",
        help="Report the N slowest completed suites (default: 5; 0 disables)",
    )
    parser.add_argument(
        "--diagnostics", type=Path, default=os.environ.get("LIXITY_BROWSER_DIAGNOSTICS"),
        metavar="NEW_DIR",
        help="Retain bounded synthetic logs, owned PNGs and incremental results in a new directory",
    )
    parser.add_argument(
        "--summary", type=Path, metavar="DIAGNOSTICS_DIR",
        help="Print a Markdown summary of saved diagnostics without starting suites",
    )
    arguments = parser.parse_args()
    if arguments.summary:
        print(diagnostic_summary(arguments.summary))
        return 0
    if arguments.durations < 0:
        parser.error("--durations must be nonnegative")

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
    if arguments.shard:
        try:
            names = select_shard(names, arguments.shard)
        except ValueError as exc:
            parser.error(str(exc))

    if arguments.list:
        print("\n".join(names))
        return 0

    evidence = None
    if arguments.diagnostics:
        try:
            evidence = BrowserEvidence(arguments.diagnostics, names,
                                       min(max(1, arguments.jobs), len(names)))
        except OSError as exc:
            parser.error(f"Cannot create new browser diagnostics directory: {exc}")

    node = shutil.which("node")
    if node is None:
        print("Node.js is required for the browser suites.", file=sys.stderr)
        if evidence:
            evidence.finish(2)
        return 2

    support_tests = sorted((SUITE_DIR / "support").glob("*.test.cjs"))
    if support_tests:
        command = [node, "--test", *(str(path) for path in support_tests)]
        if evidence:
            code = evidence.preflight(command)
        else:
            code = subprocess.run(  # noqa: S603 - fixed node binary and local harness tests
                command, cwd=ROOT, check=False,
            ).returncode
        if code:
            print("Browser harness checks failed; UI suites were not started.", file=sys.stderr)
            if evidence:
                evidence.finish(code)
            return code
    elif evidence:
        evidence.no_preflight()

    if arguments.jobs > 1:
        jobs = min(arguments.jobs, len(names))
        if jobs > 1:
            parallel_names = names if arguments.shard else ordered_suites(names)
            code = run_parallel(node, parallel_names, jobs, arguments.durations, evidence)
            if evidence:
                evidence.finish(code)
            return code

    started = time.monotonic()
    timings: list[tuple[str, float]] = []
    for index, name in enumerate(names, start=1):
        print(f"[{index}/{len(names)}] {name}", flush=True)
        execute = evidence.run_suite if evidence else run_suite
        _name, seconds, code, output = execute(node, name, False)
        if output.strip():
            print(output.rstrip(), flush=True)
        timings.append((name, seconds))
        if code:
            print(f"Failed: {name} (exit {code}, {seconds:.1f}s)", file=sys.stderr)
            report_durations(timings, arguments.durations)
            report_summary(names, index, [(name, code)], time.monotonic() - started)
            print(f"Resume after the fix with: --start {name}", file=sys.stderr)
            if evidence:
                evidence.finish(code)
            return code
        print(f"Passed: {name} ({seconds:.1f}s)", flush=True)
    report_durations(timings, arguments.durations)
    report_summary(names, len(names), [], time.monotonic() - started)
    if evidence:
        evidence.finish(0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
