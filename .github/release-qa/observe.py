"""Assert accessible labels in rendered WebKitGTK documents."""
import json
from pathlib import Path
import sys
import time

import pyatspi


def descendants(node, depth=0):
    if node is None or depth > 32:
        return
    try:
        yield depth, node.getRoleName(), node.name or ""
        for index in range(node.childCount):
            yield from descendants(node.getChildAtIndex(index), depth + 1)
    except (LookupError, RuntimeError):
        return


evidence, *labels = sys.argv[1:]
end = time.monotonic() + 55
while True:
    rows = list(descendants(pyatspi.Registry.getDesktop(0)))
    Path(evidence).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    names = "\n".join(name for _, _, name in rows).casefold()
    missing = [label for label in labels if label.casefold() not in names]
    if not missing:
        print(json.dumps({"rendered": labels}, ensure_ascii=False))
        break
    if time.monotonic() >= end:
        raise SystemExit(f"Missing rendered labels: {missing!r}")
    time.sleep(1)
