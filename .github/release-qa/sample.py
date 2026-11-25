#!/usr/bin/env python3
"""Exercise the packaged Lixity desktop UI through the Linux accessibility bus."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import pyatspi


DEFAULT_WAIT = 25
HOME = Path.home()
EVIDENCE = Path(os.environ["QA_OUTPUT"])


def descendants(node, depth=0):
    if node is None or depth > 32:
        return
    try:
        name = node.name or ""
        role = node.getRoleName()
        yield depth, role, name, node
        for index in range(node.childCount):
            yield from descendants(node.getChildAtIndex(index), depth + 1)
    except (LookupError, RuntimeError):
        return


def ui_tree():
    return list(descendants(pyatspi.Registry.getDesktop(0)))


def write_tree(stage, rows):
    (EVIDENCE / f"{stage}.json").write_text(
        json.dumps([[depth, role, name] for depth, role, name, _ in rows], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def screenshot(stage):
    subprocess.run(["xwd", "-root", "-silent", "-out", str(EVIDENCE / f"{stage}.xwd")], check=True)


def wait_labels(stage, *needles, enabled_button=None, timeout=DEFAULT_WAIT):
    end = time.monotonic() + timeout
    rows = []
    while time.monotonic() < end:
        rows = ui_tree()
        names = "\n".join(name for _, _, name, _ in rows)
        button_ready = enabled_button is None or any(
            role == "push button" and name == enabled_button
            and node.getState().contains(pyatspi.STATE_ENABLED)
            and node.getState().contains(pyatspi.STATE_SENSITIVE)
            for _, role, name, node in rows
        )
        if button_ready and all(needle.casefold() in names.casefold() for needle in needles):
            write_tree(stage, rows)
            time.sleep(2)
            screenshot(stage)
            print(json.dumps({"stage": stage, "visibleLabels": needles}, ensure_ascii=False), flush=True)
            return rows
        time.sleep(1)
    write_tree(stage, rows)
    screenshot(stage)
    raise AssertionError(f"Timed out waiting for {needles!r} at {stage}")


def click(label, rows):
    for _, role, name, node in rows:
        if name != label or role not in ("push button", "button", "page tab", "link", "toggle button"):
            continue
        try:
            action = node.queryAction()
            if action.nActions and action.doAction(0):
                return
        except (AttributeError, LookupError, NotImplementedError, RuntimeError):
            pass
        bounds = node.queryComponent().getExtents(pyatspi.DESKTOP_COORDS)
        x = bounds.x + bounds.width // 2
        y = bounds.y + bounds.height // 2
        subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"], check=True)
        return
    raise AssertionError(f"Could not locate the control {label!r}")


welcome = wait_labels("lixity-interactive-welcome", "Welcome to Lixity", "Try the example offline")
click("Try the example offline", welcome)
preview = wait_labels(
    "lixity-sample-preview", "Create project", enabled_button="Import and analyze manuscript",
)
root = HOME / "Lixity"
if list(root.rglob("manuscript.md")):
    raise AssertionError("Opening the sample preview already created a manuscript")
click("Import and analyze manuscript", preview)
wait_labels("lixity-sample-opened", "The Crate at Warehouse 4")
manuscripts = list(root.rglob("manuscript.md"))
if len(manuscripts) != 1:
    raise AssertionError(f"Expected one saved example manuscript, got {len(manuscripts)}")
saved = manuscripts[0].read_bytes()
expected = (Path(os.environ["QA_SCRIPTS"]).parents[1] / "samples" / "first-look.md").read_bytes()
if saved != expected:
    raise AssertionError("The saved manuscript bytes differ from the bundled offline sample")
print(json.dumps({"savedBytesMatch": True, "sha256": hashlib.sha256(saved).hexdigest()}), flush=True)
