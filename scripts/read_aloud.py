"""Run the shared Qwen read-aloud CLI from the source checkout."""
from __future__ import annotations

import sys

from lixity.cli import main as cli_main


def main() -> int:
    """Forward every option to the maintained read-aloud command."""
    return cli_main(["read-aloud", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
