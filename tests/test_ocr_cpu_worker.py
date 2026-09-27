"""The optional CPU adapter strips model layout tokens without changing prose."""
import runpy
import unittest
from pathlib import Path


class TestCPUWorker(unittest.TestCase):
    def test_layout_blocks_are_plain_text_and_unknown_tokens_fail(self):
        namespace = runpy.run_path(str(Path(__file__).parents[1]/'scripts/ocr_unlimited_cpu_worker.py'))
        parse = namespace['extract_blocks']
        blocks = parse('<|det|>title [1, 2, 3, 4]<|/det|>A title\n<|det|>text [4,5,6,7]<|/det|>A paragraph.', 2)
        self.assertEqual(blocks, [{'page_number':2,'text':'A title'}, {'page_number':2,'text':'A paragraph.'}])
        with self.assertRaises(ValueError):
            parse('<|unknown|>Unexpected model output', 1)
