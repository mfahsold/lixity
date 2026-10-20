"""Research CLI mechanics and explicit synthetic revision setup shared by tests."""

import argparse
import contextlib
import io
from functools import cache
from pathlib import Path
from typing import Any

from lixity.research import api, cli


@cache
def research_parser() -> argparse.ArgumentParser:
    """Reuse the command definitions; each parse still returns a fresh namespace."""
    parser = argparse.ArgumentParser()
    cli.configure(parser)
    return parser


def parse_research_args(*arguments: str) -> argparse.Namespace:
    return research_parser().parse_args(arguments)


def capture_research(*arguments: str) -> tuple[int, str, str]:
    """Run the real CLI dispatcher and retain its exact stdout and stderr."""
    output, errors = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = cli.run(parse_research_args(*arguments))
    return status, output.getvalue(), errors.getvalue()


def retained_files(project: Path) -> dict[str, bytes]:
    """Snapshot archive bytes with portable POSIX relative-path keys."""
    return {path.relative_to(project).as_posix(): path.read_bytes()
            for path in (project / "research").rglob("*") if path.is_file()}


def revise_record(
    project: str | Path, kind: str, identifier: str, changes: dict[str, Any], *,
    change_kind: str = "correction", reason: str = "Synthetic reviewed revision.",
    actor: str = "local-author",
) -> dict[str, Any]:
    """Create setup revisions from one explicit current-record read."""
    current = api.get_record(project, kind, identifier)
    return api.revise_record(
        project, kind, identifier, changes=changes,
        expected_snapshot=current["snapshot"], expected_revision=current["record"]["revision"],
        change_kind=change_kind, reason=reason, actor=actor,
    )
