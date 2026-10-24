"""Synthetic regressions for shared token, prose and paragraph contracts."""

import unittest
from unittest.mock import patch

from lixity.analyzer import CorpusAnalyzer
from lixity.dialogue import dialogue_report
from lixity.language import compile_word_pattern, get_language_profile
from lixity.markdown_parser import parse_markdown_blocks, split_chapters
from lixity.models import CorpusConfig
from lixity.motifs import motif_report
from lixity.pacing import pacing_report
from lixity.scenes import scene_report
from lixity.style_profile import ParagraphProfiler
from lixity.syllables import count_syllables

SCENE_DIVIDERS = ("---", "***", "___", "•••", "# # #", "###", "* * *")


class TestWordContract(unittest.TestCase):
    def test_five_profiles_keep_either_apostrophe_inside_words(self):
        cases = (
            ("l'homme", ["l'homme"]),
            ("l’homme", ["l’homme"]),
            ("l'’homme", ["l", "homme"]),
            ("l’'homme", ["l", "homme"]),
            ("porte-monnaie 42 café", ["porte", "monnaie", "café"]),
        )
        for language in ("fr", "es", "it", "pt", "nl"):
            words = compile_word_pattern(get_language_profile(language).word_regex)
            for text, expected in cases:
                with self.subTest(language=language, text=text):
                    self.assertEqual(words.findall(text), expected)

    def test_apostrophe_token_counts_agree_across_analysis_surfaces(self):
        for language in ("fr", "es", "it", "pt", "nl"):
            for apostrophe in ("'", "’"):
                body = f"L{apostrophe}homme arrive. L{apostrophe}homme part."
                text = f"## Main\n\n{body}"
                with self.subTest(language=language, apostrophe=apostrophe):
                    config = CorpusConfig(language=language)
                    metrics = CorpusAnalyzer(config).analyze_text(text)
                    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
                        parse_markdown_blocks(text, config)
                    )
                    self.assertEqual(metrics.tokens, 4)
                    self.assertEqual(metrics.asl, 2.0)
                    self.assertEqual(metrics.chapters[0].words, 4)
                    self.assertEqual(paragraphs[0].words, 4)
                    self.assertEqual(chapters[0].words, 4)
                    self.assertEqual(paragraphs[0].text, body)
                    self.assertEqual(paragraphs[0].start_line, 3)
                    self.assertEqual(dialogue_report(text, config).words, 4)
                    self.assertEqual(pacing_report(text, config).chapter_list[0].words, 4)
                    self.assertEqual(scene_report(text, config)["items"][0]["words"], 4)
                    self.assertEqual(sum(n for _, n in motif_report(text, config=config).top_words), 4)

    def test_first_person_elisions_accept_both_apostrophes_without_merging_starters(self):
        for language, straight in (
            ("en", "I'm here. I'm here."),
            ("fr", "J'aime marcher. J'aime marcher."),
        ):
            cases = ((straight, 0.0), (straight.replace("'", "’"), 0.0),
                     (straight.replace("'", "’", 1), 1.0))
            for body, entropy in cases:
                with self.subTest(language=language, body=body):
                    metrics = CorpusAnalyzer(CorpusConfig(language=language)).analyze_text(
                        f"## Main\n\n{body}"
                    )
                    self.assertEqual(metrics.first_person_start_rate, 100.0)
                    self.assertEqual(metrics.chapters[0].first_person_start_rate, 100.0)
                    self.assertEqual(metrics.start_entropy, entropy)
                    self.assertEqual(metrics.chapters[0].start_entropy, entropy)

    def test_configured_word_flags_agree_across_analysis_surfaces(self):
        text = '## Main\n\nDoor door. "Window window."'
        for pattern, expected in ((r"\b[A-Z][a-z]+\b", 2),
                                  (r"(?i)\b[A-Z][a-z]+\b", 4),
                                  (r"\b(?i:[a-z]+)\b", 4)):
            with self.subTest(pattern=pattern):
                config = CorpusConfig(language="en", word_regex=pattern,
                                      filter_verbs_regex=r"\bdoor\b")
                metrics = CorpusAnalyzer(config).analyze_text(text)
                paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
                    parse_markdown_blocks(text, config)
                )
                self.assertEqual(metrics.tokens, expected)
                self.assertEqual(metrics.chapters[0].words, expected)
                self.assertEqual(paragraphs[0].words, expected)
                self.assertEqual(chapters[0].words, expected)
                self.assertEqual(dialogue_report(text, config).words, expected)
                self.assertEqual(pacing_report(text, config).chapter_list[0].words, expected)
                self.assertEqual(scene_report(text, config)["items"][0]["words"], expected)
                self.assertEqual(sum(n for _, n in motif_report(text, config=config).top_words),
                                 expected)
                # Cue patterns retain their separate case-insensitive contract.
                self.assertEqual(metrics.filter_density, 2000 / expected)

    def test_unicode_words_and_markdown_emphasis_keep_whole_tokens(self):
        for language in ("en", "de"):
            config = CorpusConfig(language=language)
            plain = "Café naïve façade. bright word."
            marked = "Café naïve façade. _bright_ **word**."
            with self.subTest(language=language):
                analyzer = CorpusAnalyzer(config)
                baseline = analyzer.analyze_text("## Main\n\n" + plain)
                metrics = analyzer.analyze_text("## Main\n\n" + marked)
                paragraphs, _ = ParagraphProfiler(config).profile_blocks(
                    parse_markdown_blocks("## Main\n\n" + marked, config)
                )
                self.assertEqual(metrics.tokens, 5)
                self.assertEqual(metrics.vocab_types, 5)
                self.assertEqual(metrics.asl, baseline.asl)
                self.assertEqual(metrics.asw, baseline.asw)
                self.assertEqual(paragraphs[0].words, 5)
                words = dict(motif_report("## Main\n\n" + marked, config=config).top_words)
                self.assertEqual(words.get("café"), 1)
                self.assertEqual(words.get("naïve"), 1)
                self.assertEqual(words.get("façade"), 1)


class TestParagraphContract(unittest.TestCase):
    def test_inline_counting_keeps_display_text_and_saved_paragraph_identity(self):
        from lixity.pipeline import paragraph_identity

        text = '## Main\n\nMara reads [the letter](https://example.org/Mara) beside `Mara`.\n'
        config = CorpusConfig(language="en")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text, config))
        self.assertEqual(paragraphs[0].text,
                         'Mara reads [the letter](https://example.org/Mara) beside `Mara`.')
        self.assertEqual(paragraph_identity(paragraphs[0]), {
            "start_line": 3, "end_line": 3,
            "paragraph_sha256": "83ac24212cd02c2b14d4d4d5ffe4f33752df2281645423f00afca884c40418dd",
        })
        self.assertEqual(paragraphs[0].words, 5)
        self.assertEqual(chapters[0].words, 5)
        self.assertEqual(CorpusAnalyzer(config).analyze_text(text).tokens, 5)
        self.assertEqual(dialogue_report(text, config).words, 5)
        self.assertEqual(scene_report(text, config)["items"][0]["words"], 5)

    def test_lf_and_crlf_share_paragraph_counts_and_original_line_anchors(self):
        text = ('## Main\n\n<!-- hidden\ncomment -->\n\n'
                '"Door opens."\nA window closes.\n \t\n"River flows."\n')
        config = CorpusConfig(language="en")
        for value in (text, text.replace("\n", "\r\n")):
            with self.subTest(crlf="\r" in value):
                metrics = CorpusAnalyzer(config).analyze_text(value)
                dialogue = dialogue_report(value, config)
                paragraphs, _ = ParagraphProfiler(config).profile_blocks(
                    parse_markdown_blocks(value, config)
                )
                self.assertEqual(metrics.total_paragraphs, 2)
                self.assertEqual(metrics.avg_paragraph_len, 3.5)
                self.assertEqual(dialogue.chapters[0].paragraphs, 2)
                self.assertEqual([(p.start_line, p.end_line) for p in paragraphs],
                                 [(6, 7), (9, 9)])

    def test_short_paragraph_threshold_is_inclusive_without_eight_word_exception(self):
        for threshold in (7, 8, 9, 25):
            config = CorpusConfig(language="en", min_paragraph_length_for_oneliner=threshold)
            for length in (7, 8, 9, threshold, threshold + 1):
                with self.subTest(threshold=threshold, length=length):
                    text = "## Main\n\n" + " ".join(["word"] * length) + "."
                    metrics = CorpusAnalyzer(config).analyze_text(text)
                    self.assertEqual(metrics.single_line_paragraphs, int(length <= threshold))


class TestProseScope(unittest.TestCase):
    def test_inline_counting_uses_nfc_and_preserves_literal_punctuation_around_markup(self):
        from lixity.markdown_parser import counting_inline_text

        cases = (
            ("  Café naïve façade — 😀.  ", "Café naïve façade — 😀."),
            ("e\u0301lan 日本語 العربية", "élan 日本語 العربية"),
            ("An (aside), a closing ] and ! remain.", "An (aside), a closing ] and ! remain."),
            ("snake_case and _bright_ **words**.", "snake_case and bright words."),
            ("Before <!-- hidden --> after.", "Before  after."),
            ("First line.\r\nSecond line.", "First line.\r\nSecond line."),
            (" \t\n", ""),
            (r"Literal \[bracket] and \! remain.", "Literal [bracket] and ! remain."),
            ("Read [the *letter*](https://example.org/hidden).", "Read the letter."),
            ("Before ![portrait](image.png) after.", "Before   after."),
            ("Before `hidden words` after.", "Before   after."),
            ("Words[^note] remain.", "Words remain."),
            ("An [unclosed label stays literal.", "An [unclosed label stays literal."),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(counting_inline_text(text), expected)
        from lixity.markdown_parser import strip_inline_markup

        self.assertEqual(strip_inline_markup("e\u0301lan 日本語 العربية"), "e\u0301lan 日本語 العربية")

    def test_malformed_inline_syntax_has_bounded_scan_work_and_stays_literal(self):
        from lixity import markdown_parser

        class ReadBudget(str):
            reads = 0

            def __getitem__(self, key):
                self.reads += 1
                if self.reads > 40 * len(self):
                    raise AssertionError("Malformed prose caused repeated suffix scans")
                return super().__getitem__(key)

        brackets = "[" * 1024 + " ordinary prose."
        # Instrument character access after the existing reference-definition
        # pass; bound work, not wall-clock time or a particular data structure.
        with patch.object(markdown_parser, "_LINK_DEFINITION") as definitions:
            definitions.sub.side_effect = lambda _replacement, text: ReadBudget(text)
            self.assertEqual(markdown_parser.counting_inline_text(brackets), brackets)
        backticks = " ".join("`" * width for width in range(1, 121)) + " ordinary prose."
        self.assertEqual(markdown_parser.counting_inline_text(backticks), backticks)
        nested = "Mara"
        for _ in range(1000):
            nested = f"[{nested}](destination)"
        self.assertEqual(markdown_parser.counting_inline_text(nested), "Mara")

    def test_inline_only_manuscripts_keep_anchors_and_render_without_fabricated_signals(self):
        from lixity import api

        for body in ('![Mara](portrait.png)', '`Mara`'):
            with self.subTest(body=body):
                text = f"## Main\n\n{body}\n"
                metrics = api.analyze(text, project_config={})["metrics"]
                self.assertEqual(metrics["tokens"], 0)
                self.assertEqual(metrics["chapters"][0]["words"], 0)
                self.assertIsNone(metrics["chapters"][0]["hd_d"])
                self.assertEqual(metrics["chapters"][0]["style_se"], {})
                html = api.dashboard(text, project_config={"characters": {"Mara": {"pov_in_chapters": [1]}}})
                self.assertIn('id="ch-1"', html)
                self.assertIn('id="p-0"', html)
                self.assertIn('Declared POV chapters', html)

    def test_inline_only_chapters_keep_numbers_when_counting_excludes_their_content(self):
        from lixity.characters import presence_report
        from lixity.registers import resolve_chapter_registers

        text = ('## Image\n\n![Mara](portrait.png)\n\n'
                '## Code\n\n`Mara`\n\n## Real\n\nMara opens the door.\n')
        config = CorpusConfig(language="en")
        self.assertEqual([(n, title) for n, title, _ in split_chapters(text, config)],
                         [(1, "Image"), (2, "Code"), (3, "Real")])
        metrics = CorpusAnalyzer(config).analyze_text(text)
        self.assertEqual([(c.num, c.title, c.words) for c in metrics.chapters],
                         [(1, "Image", 0), (2, "Code", 0), (3, "Real", 4)])
        self.assertEqual(resolve_chapter_registers(metrics.chapters, {"3": "voice"}), {3: "voice"})
        self.assertEqual(scene_report(text, config),
                         scene_report(text, config, _premeasured_chapters=metrics.chapters))
        self.assertEqual(presence_report(text, ["Mara"], config)["figures"][0]["chapters_present"], [3])
        paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text, config))
        self.assertEqual([(p.chapter_num, p.words) for p in paragraphs], [(1, 0), (2, 0), (3, 4)])

    def test_nested_and_escaped_links_use_visible_labels_only(self):
        from lixity.characters import presence_report

        text = ('## Main\n\n[Mara [Quinn]](https://example.org/map_(Mara)) '
                r'and [Mara \[Quinn\]](https://example.org/Mara).' '\n')
        config = CorpusConfig(language="en")
        self.assertEqual(CorpusAnalyzer(config).analyze_text(text).tokens, 5)
        self.assertEqual(presence_report(text, ["Mara"], config)["figures"][0]["mentions"], 2)
        nested = "Mara"
        for _ in range(20):
            nested = f"[{nested}](https://example.org/Mara)"
        self.assertEqual(presence_report("## Main\n\n" + nested, ["Mara"], config)["figures"][0]["mentions"], 1)

    def test_code_is_excluded_and_visible_front_matter_stays_global(self):
        config = CorpusConfig(language="en")
        text = ('# Book title\n\nAuthor metadata.\n\n## Main\n\n'
                'Door opens.\n\n> "Window closes."\n\n'
                '```text\n## Fake chapter\n"Hidden code speaks."\n---\n```\n\n'
                '   ~~~~text\nAnother hidden example.\n   ~~~~\n\n'
                '    Indented hidden code.\n\n'
                '### Detail\n\n_River_ flows.\n\n<!-- Hidden comment. -->\n\n'
                '## Anmerkungen und Literaturverzeichnis\n\nExcluded appendix.')
        metrics = CorpusAnalyzer(config).analyze_text(text)
        dialogue = dialogue_report(text, config)
        pacing = pacing_report(text, config)
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
            parse_markdown_blocks(text, config)
        )
        self.assertEqual([title for _, title, _ in split_chapters(text, config)], ["Main"])
        self.assertEqual(metrics.tokens, 8)
        self.assertEqual(metrics.chapters[0].words, 6)
        self.assertEqual(dialogue.words, 6)
        self.assertEqual(dialogue.dialogue_words, 2)
        self.assertEqual(pacing.chapter_list[0].words, 6)
        self.assertEqual(pacing.explicit_scene_breaks, 0)
        self.assertEqual(scene_report(text, config)["items"][0]["words"], 6)
        self.assertEqual(sum(n for _, n in motif_report(text, config=config).top_words), 6)
        # Paragraph profiles intentionally omit quoted blocks, retaining source anchors.
        self.assertEqual([p.words for p in paragraphs], [2, 2])
        self.assertEqual([p.start_line for p in paragraphs], [7, 25])
        self.assertEqual(chapters[0].words, 4)
        # The legacy whitespace counter is a distinct raw-cleaned measurement.
        self.assertGreater(metrics.clean_words, metrics.tokens)

    def test_leading_yaml_metadata_is_excluded_without_moving_anchors(self):
        config = CorpusConfig(language="en")
        text = '---\ntitle: "Hidden metadata."\n## Fake heading\n---\n## Main\n\nDoor opens.'
        for value in (text, text.replace("\n", "\r\n")):
            with self.subTest(crlf="\r" in value):
                metrics = CorpusAnalyzer(config).analyze_text(value)
                paragraphs, _ = ParagraphProfiler(config).profile_blocks(
                    parse_markdown_blocks(value, config)
                )
                self.assertEqual(metrics.tokens, 2)
                self.assertEqual([c.title for c in metrics.chapters], ["Main"])
                self.assertEqual([p.start_line for p in paragraphs], [7])

    def test_commented_dividers_and_fences_do_not_create_scenes(self):
        config = CorpusConfig(language="en")
        text = ('## Main\n\nDoor opens.\n\n<!--\n---\n```text\n-->\n\n'
                'Window closes.\n\n---\n\nRiver flows.')
        pacing = pacing_report(text, config)
        scenes = scene_report(text, config)
        self.assertEqual(pacing.explicit_scene_breaks, 1)
        self.assertEqual(scenes["explicit_scene_breaks"], 1)
        self.assertEqual([s.words for s in pacing.chapter_list[0].scene_list], [4, 2])

    def test_leading_scene_dividers_are_not_yaml_metadata(self):
        config = CorpusConfig(language="en")
        for opening in ("Door opens.", "Time: morning."):
            with self.subTest(opening=opening):
                text = f'## Main\n\n---\n\n{opening}\n\n---\n\nWindow closes.'
                metrics = CorpusAnalyzer(config).analyze_text(text)
                pacing = pacing_report(text, config)
                self.assertEqual(metrics.tokens, 4)
                self.assertEqual(metrics.chapters[0].words, 4)
                self.assertEqual(pacing.chapter_list[0].words, 4)
                self.assertEqual([s.words for s in pacing.chapter_list[0].scene_list], [2, 2])

    def test_yaml_is_document_metadata_for_an_implicit_chapter(self):
        config = CorpusConfig(language="en")
        text = '---\ntitle: "Hidden metadata."\n---\n\nDoor opens.'
        metrics = CorpusAnalyzer(config).analyze_text(text)
        self.assertEqual(metrics.tokens, 2)
        self.assertEqual(metrics.chapters[0].words, 2)

    def test_leading_indented_code_stays_code_in_chapter_reports(self):
        cases = (
            ("", CorpusConfig(language="en")),
            ("## Main\n \t\n", CorpusConfig(language="en")),
            ("CHAPTER Main\n \t\n", CorpusConfig(
                language="en", chapter_regex=r"(?m)^CHAPTER\s+[^\r\n]+$")),
        )
        for heading, config in cases:
            for indent in ("    ", "\t"):
                text = f"{heading}{indent}Hidden code.\n \t\nWindow opens."
                for value in (text, text.replace("\n", "\r\n")):
                    with self.subTest(heading=heading, indent=indent, crlf="\r" in value):
                        metrics = CorpusAnalyzer(config).analyze_text(value)
                        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
                            parse_markdown_blocks(value, config)
                        )
                        self.assertEqual(metrics.tokens, 2)
                        self.assertEqual([chapter.words for chapter in metrics.chapters], [2])
                        self.assertEqual(dialogue_report(value, config).words, 2)
                        self.assertEqual(pacing_report(value, config).chapter_list[0].words, 2)
                        self.assertEqual(scene_report(value, config)["items"][0]["words"], 2)
                        self.assertEqual(sum(n for _, n in motif_report(value, config=config).top_words), 2)
                        self.assertEqual([paragraph.words for paragraph in paragraphs], [2])
                        self.assertEqual([paragraph.start_line for paragraph in paragraphs],
                                         [5 if heading else 3])
                        self.assertEqual([chapter.words for chapter in chapters], [2])
                        self.assertTrue(split_chapters(value, config)[0][2].startswith(indent))

    def test_indented_code_only_chapter_does_not_shift_real_chapter_anchors(self):
        config = CorpusConfig(language="en")
        for indent in ("    ", "\t"):
            text = f"## Code only\n\n{indent}Hidden code.\n\n## Real\n\nDoor opens."
            for value in (text, text.replace("\n", "\r\n")):
                with self.subTest(indent=indent, crlf="\r" in value):
                    metrics = CorpusAnalyzer(config).analyze_text(value)
                    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
                        parse_markdown_blocks(value, config)
                    )
                    self.assertEqual(metrics.tokens, 2)
                    self.assertEqual([(chapter.num, chapter.title, chapter.words)
                                      for chapter in metrics.chapters], [(1, "Real", 2)])
                    self.assertEqual([title for _, title, _ in split_chapters(value, config)], ["Real"])
                    self.assertEqual([(chapter.num, chapter.title) for chapter in chapters], [(1, "Real")])
                    self.assertEqual([paragraph.start_line for paragraph in paragraphs], [7])
                    self.assertEqual([chapter.chapter_num for chapter in pacing_report(value, config).chapter_list], [1])

    def test_indented_code_dividers_do_not_create_scenes(self):
        config = CorpusConfig(language="en")
        for indent in ("    ", "\t"):
            for divider in SCENE_DIVIDERS:
                text = (f"## Main\n\nDoor opens.\n\n{indent}First code line.\n"
                        f"{indent}{divider}\n{indent}Last code line.\n\nWindow closes.")
                for value in (text, text.replace("\n", "\r\n")):
                    with self.subTest(indent=indent, divider=divider, crlf="\r" in value):
                        pacing = pacing_report(value, config)
                        scenes = scene_report(value, config)
                        paragraphs, _ = ParagraphProfiler(config).profile_blocks(
                            parse_markdown_blocks(value, config)
                        )
                        self.assertEqual(CorpusAnalyzer(config).analyze_text(value).tokens, 4)
                        self.assertEqual(pacing.explicit_scene_breaks, 0)
                        self.assertTrue(pacing.scenes_are_chapters)
                        self.assertEqual([scene.words for scene in pacing.chapter_list[0].scene_list], [4])
                        self.assertEqual(scenes["explicit_scene_breaks"], 0)
                        self.assertEqual([scene["words"] for scene in scenes["items"]], [4])
                        self.assertEqual([paragraph.start_line for paragraph in paragraphs], [3, 9])

    def test_all_scene_dividers_stay_outside_prose_paragraphs(self):
        config = CorpusConfig(language="en")
        for divider in SCENE_DIVIDERS:
            for indent in ("", "   "):
                for separator in ("\n", "\n\n"):
                    for opening in ("Door opens.", "- Door opens."):
                        text = f"## Main\n\n{opening}{separator}{indent}{divider}{separator}Window closes."
                        for value in (text, text.replace("\n", "\r\n")):
                            with self.subTest(divider=divider, indent=indent, separator=separator,
                                              opening=opening, crlf="\r" in value):
                                metrics = CorpusAnalyzer(config).analyze_text(value)
                                dialogue = dialogue_report(value, config)
                                blocks = parse_markdown_blocks(value, config)
                                self.assertEqual(metrics.tokens, 4)
                                self.assertEqual(metrics.total_paragraphs, 2)
                                self.assertEqual(metrics.avg_paragraph_len, 2)
                                self.assertEqual(dialogue.chapters[0].paragraphs, 2)
                                self.assertEqual([block["type"] for block in blocks].count("divider"), 1)
                                self.assertEqual(pacing_report(value, config).explicit_scene_breaks, 1)

    def test_fenced_scene_dividers_remain_code(self):
        config = CorpusConfig(language="en")
        for marker in ("```", "~~~"):
            for divider in SCENE_DIVIDERS:
                text = (f"## Main\n\nDoor opens.\n\n{marker}text\nHidden code.\n"
                        f"{divider}\n{marker}\n\nWindow closes.")
                for value in (text, text.replace("\n", "\r\n")):
                    with self.subTest(marker=marker, divider=divider, crlf="\r" in value):
                        metrics = CorpusAnalyzer(config).analyze_text(value)
                        self.assertEqual(metrics.tokens, 4)
                        self.assertEqual(metrics.total_paragraphs, 2)
                        self.assertEqual(dialogue_report(value, config).chapters[0].paragraphs, 2)
                        self.assertEqual(pacing_report(value, config).explicit_scene_breaks, 0)
                        self.assertEqual([block["type"] for block in parse_markdown_blocks(value, config)].count("code"), 1)

    def test_nonprose_preface_keeps_code_boundaries_and_visible_text(self):
        code_prefixes = ("```text\nHidden code.\n```\n\n",
                         "~~~text\nHidden code.\n~~~\n\n",
                         "    Hidden code.\n\n", "\tHidden code.\n\n")
        headings = (("## Main", CorpusConfig(language="en")),
                    ("CHAPTER Main", CorpusConfig(language="en", chapter_regex=r"(?m)^CHAPTER\s+")))
        for prefix in code_prefixes:
            for preface in ("", "Visible preface.\n\n"):
                for heading, config in headings:
                    text = f"{prefix}{preface}{heading}\n\nDoor opens."
                    for value in (text, text.replace("\n", "\r\n")):
                        with self.subTest(prefix=prefix, preface=preface, heading=heading, crlf="\r" in value):
                            metrics = CorpusAnalyzer(config).analyze_text(value)
                            expected = [(1, "", 2), (2, "Main", 2)] if preface else [(1, "Main", 2)]
                            self.assertEqual(metrics.tokens, 4 if preface else 2)
                            self.assertEqual([(chapter.num, chapter.title, chapter.words)
                                              for chapter in metrics.chapters], expected)
                            self.assertEqual(dialogue_report(value, config).words, metrics.tokens)
                            self.assertEqual([chapter.words for chapter in pacing_report(value, config).chapter_list],
                                             [words for _, _, words in expected])
                            paragraphs, chapters = ParagraphProfiler(config).profile_blocks(
                                parse_markdown_blocks(value, config)
                            )
                            self.assertEqual([(chapter.num, chapter.title, chapter.words) for chapter in chapters],
                                             [expected[-1]])
                            prose_line = value.splitlines().index("Door opens.") + 1
                            self.assertEqual([paragraph.start_line for paragraph in paragraphs], [prose_line])
                            if preface:
                                self.assertTrue(split_chapters(value, config)[0][2].startswith(prefix.splitlines()[0]))

    def test_prose_first_preface_retains_legacy_title_fallback(self):
        config = CorpusConfig(language="en")
        text = "Plain heading\n\nVisible preface.\n\n## Main\n\nDoor opens."
        for value in (text, text.replace("\n", "\r\n")):
            with self.subTest(crlf="\r" in value):
                metrics = CorpusAnalyzer(config).analyze_text(value)
                self.assertEqual(metrics.tokens, 6)
                self.assertEqual([(chapter.num, chapter.title, chapter.words) for chapter in metrics.chapters],
                                 [(1, "Plain heading", 2), (2, "Main", 2)])


class TestSyllableReuse(unittest.TestCase):
    def test_syllables_are_frequency_weighted_per_request_with_equal_values(self):
        text = "## Main\n\nDoor door café. Window window façade. Door door café."
        for language in ("en", "de"):
            with self.subTest(language=language):
                analyzer = CorpusAnalyzer(CorpusConfig(language=language))
                calls = []

                def measured(word, measured_calls=calls, measured_language=language):
                    measured_calls.append(word)
                    return count_syllables(word, measured_language)

                with patch.object(analyzer, "count_syllables", side_effect=measured):
                    first = analyzer.analyze_text(text)
                    first_calls = list(calls)
                    calls.clear()
                    second = analyzer.analyze_text("## Main\n\nRiver river.")
                tokens = ["Door", "door", "café", "Window", "window", "façade",
                          "Door", "door", "café"]
                self.assertEqual(first.asw, sum(count_syllables(t, language) for t in tokens) / 9)
                self.assertEqual(set(first_calls), {"door", "café", "window", "façade"})
                self.assertEqual(len(first_calls), 4)
                self.assertEqual(calls, ["river"])
                self.assertEqual(second.asw, count_syllables("river", language))
