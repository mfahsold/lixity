"""
tests/test_markers.py
=====================
Tests for the editor-visible work markers: parse, add, resolve, update,
idempotency, sanitising and the agent facade wrappers.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity import api  # noqa: E402
from lixity.markers import (  # noqa: E402
    add_marker,
    count_markers,
    list_markers,
    marker_id,
    resolve_marker,
    update_marker,
)

SAMPLE = (
    "## Kapitel 1\n\n"
    "Ich trinke Kaffee. Ich gehe zum Fenster.\n\n"
    "Ich trinke Tee. Ich sehe den Regen.\n"
)


class TestMarkerParsing(unittest.TestCase):
    def test_list_markers_finds_anchors(self):
        text, marker = add_marker(SAMPLE, "pruefen", "Tempus prüfen", 5)
        found = list_markers(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, marker.id)
        self.assertEqual(found[0].kind, "pruefen")
        self.assertEqual(found[0].note, "Tempus prüfen")
        self.assertEqual(found[0].line, 5)

    def test_marker_line_is_inserted_above_anchor(self):
        text, marker = add_marker(SAMPLE, "todo", "", 5)
        lines = text.splitlines()
        self.assertIn(marker.render(), lines[4])  # 0-based line 4 = 1-based line 5

    def test_count_markers(self):
        text, _ = add_marker(SAMPLE, "pruefen", "", 5)
        text, _ = add_marker(text, "todo", "", 7)
        self.assertEqual(count_markers(text), 2)


class TestMarkerLifecycle(unittest.TestCase):
    def test_add_is_idempotent(self):
        once, marker = add_marker(SAMPLE, "pruefen", "Notiz", 5)
        twice, marker2 = add_marker(once, "pruefen", "Notiz", 5)
        self.assertEqual(once, twice)
        self.assertEqual(marker.id, marker2.id)
        self.assertEqual(count_markers(twice), 1)

    def test_ids_are_deterministic(self):
        self.assertEqual(marker_id("pruefen", "x", 5), marker_id("pruefen", "x", 5))
        self.assertNotEqual(marker_id("pruefen", "x", 5), marker_id("pruefen", "y", 5))

    def test_resolve_removes_only_that_marker(self):
        text, marker = add_marker(SAMPLE, "pruefen", "", 5)
        text, other = add_marker(text, "todo", "", 7)
        resolved = resolve_marker(text, marker.id)
        found = list_markers(resolved)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, other.id)

    def test_update_changes_note_and_kind_but_keeps_id(self):
        text, marker = add_marker(SAMPLE, "pruefen", "alt", 5)
        updated, changed = update_marker(text, marker.id, kind="sachcheck", note="neu")
        self.assertIsNotNone(changed)
        if changed is None:
            self.fail("update_marker returned None")
        self.assertEqual(changed.id, marker.id)
        self.assertEqual(changed.kind, "sachcheck")
        self.assertEqual(changed.note, "neu")
        found = list_markers(updated)
        self.assertEqual(found[0].kind, "sachcheck")

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            add_marker(SAMPLE, "quatsch", "", 5)

    def test_note_cannot_break_the_comment(self):
        text, marker = add_marker(SAMPLE, "todo", "böse --> Notiz", 5)
        self.assertEqual(marker.note, "böse -> Notiz")
        self.assertEqual(list_markers(text)[0].note, "böse -> Notiz")

    def test_prose_is_untouched(self):
        text, _ = add_marker(SAMPLE, "pruefen", "", 5)
        self.assertIn("Ich trinke Kaffee. Ich gehe zum Fenster.", text)
        resolved = resolve_marker(text, list_markers(text)[0].id)
        self.assertEqual(resolved, SAMPLE)


class TestMarkerFacade(unittest.TestCase):
    def test_api_markers_and_add_resolve(self):
        listed = api.markers(SAMPLE)
        self.assertEqual(listed, [])
        new_text, marker = api.add_marker(SAMPLE, "todo", "Noch was", 5)
        self.assertEqual(api.markers(new_text)[0]["id"], marker["id"])
        resolved = api.resolve_marker(new_text, marker["id"])
        self.assertEqual(api.markers(resolved), [])
        self.assertEqual(resolved, SAMPLE)


if __name__ == "__main__":
    unittest.main()
