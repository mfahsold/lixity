"""Local-image controls expose explicit native capability and shared bounds."""

import html
import json
import re
import unittest

from lixity.research.limits import (
    MAX_IMAGE_ALT_CHARS,
    MAX_IMAGE_BYTES,
    MAX_IMAGE_CAPTION_CHARS,
    MAX_IMAGE_PIXELS,
    MAX_SOURCE_CONTEXT_CHARS,
)
from lixity.ui.dashboard import render_dashboard


class TestDossierImageControls(unittest.TestCase):
    def test_attachment_gate_requires_an_explicit_write_service(self):
        for controls, actions, expected in (
            (False, ("research-dossier-image",), "false"),
            (True, None, "false"),
            (True, ("analyze", "research-image-ingest"), "false"),
            (True, ("research-dossier-image",), "true"),
        ):
            with self.subTest(controls=controls, actions=actions):
                page = render_dashboard([], [], controls=controls, enabled_actions=actions)
                self.assertIn(f'data-dossier-image-capable="{expected}"', page)

    def test_browser_preflight_bounds_come_from_shared_policy(self):
        page = render_dashboard([], [], controls=True, enabled_actions=("research-dossier-image",))
        match = re.search(r'data-image-limits="([^"]+)"', page)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(json.loads(html.unescape(match.group(1))), {
            "bytes": MAX_IMAGE_BYTES, "pixels": MAX_IMAGE_PIXELS,
            "alt": MAX_IMAGE_ALT_CHARS, "caption": MAX_IMAGE_CAPTION_CHARS,
            "note": MAX_SOURCE_CONTEXT_CHARS, "url": MAX_SOURCE_CONTEXT_CHARS,
        })
        self.assertIn("window.LixityDossierImages", page)
        self.assertNotIn('<script src="', page, "The exported report remains self-contained")
