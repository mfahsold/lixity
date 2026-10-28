"""Compare German quotation cues with locally supplied REDEWIEDERGABE TEI.

Only consensus samples marked fictional are included. This evaluates the
production quotation and word patterns on flattened XML text; it does not run
the manuscript Markdown pipeline or equate quotations with direct speech.
No source text is emitted or retained by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from lixity.language import compile_pattern, compile_word_pattern, get_language_profile

_NS = "{http://www.tei-c.org/ns/1.0}"


def extract(body: ElementTree.Element) -> tuple[str, list[bool], list[bool]]:
    """Flatten element text and inherited annotations using Unicode codepoint offsets."""
    parts: list[str] = []
    direct: list[bool] = []
    ambiguous: list[bool] = []

    def visit(node: ElementTree.Element, in_speech: bool, uncertain: bool) -> None:
        if node.tag == _NS + "said":
            mode = node.get("mode", "").split()
            media = node.get("content", "").split()
            if "direct" in mode:
                if mode == ["direct"] and media == ["speech"]:
                    in_speech = True
                elif len(mode) != 1 or len(media) != 1:
                    uncertain = True
            if "direct" in mode and node.get("border") == "yes":
                uncertain = True

        def append(value: str | None) -> None:
            if value:
                parts.append(value)
                direct.extend([in_speech] * len(value))
                ambiguous.extend([uncertain] * len(value))

        append(node.text)
        for child in node:
            visit(child, in_speech, uncertain)
            append(child.tail)

    visit(body, False, False)
    return "".join(parts), direct, ambiguous


def evaluate(directory: Path) -> dict[str, object]:
    profile = get_language_profile("de")
    words = compile_word_pattern(profile.word_regex)
    quotes = compile_pattern(profile.dialogue_regex)
    if words.groups != 0 or quotes.groups != 1:
        raise ValueError("Expected an uncaptured word pattern and one quotation capture group")
    totals: Counter[str] = Counter()
    digest = hashlib.sha256()
    paths = sorted(directory.glob("*.xml"))
    if not paths:
        raise ValueError("No TEI XML files in the supplied directory")
    for path in paths:
        raw = path.read_bytes()
        # Corpus XML does not use DTDs. Reject them before parsing to rule out
        # entity expansion when the supplied data is untrusted.
        contents = raw.decode("utf-8-sig")
        if "<!doctype" in contents.casefold():
            raise ValueError(f"DTD is not supported: {path.name}")
        root = ElementTree.fromstring(contents)  # noqa: S314 - UTF-8 DTDs rejected above
        text_node = root.find(_NS + "text")
        if text_node is None:
            raise ValueError(f"Missing TEI text in {path.name}")
        fictional = text_node.find("./" + _NS + "fs/" + _NS + 'f[@name="fictional"]')
        if fictional is None or fictional.text not in ("yes", "no"):
            raise ValueError(f"Missing fictional status in {path.name}")
        if fictional.text == "no":
            continue
        body = text_node.find(_NS + "body")
        if body is None:
            raise ValueError(f"Missing TEI body in {path.name}")
        digest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        totals["files"] += 1
        text, gold, ambiguous = extract(body)
        predicted = bytearray(len(text))
        for match in quotes.finditer(text):
            start, end = match.span(1)
            predicted[start:end] = b"\1" * (end - start)
        for match in words.finditer(text):
            start, end = match.span()
            if any(ambiguous[start:end]):
                totals["excluded_ambiguous"] += 1
                continue
            reference = set(gold[start:end])
            hypothesis = set(predicted[start:end])
            if len(reference) != 1 or len(hypothesis) != 1:
                totals["excluded_boundary"] += 1
                continue
            ref, pred = next(iter(reference)), next(iter(hypothesis))
            totals["tp" if ref and pred else "fp" if pred else "fn" if ref else "tn"] += 1

    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    return {
        "source_sha256": digest.hexdigest(),
        **{key: totals[key] for key in ("files", "tp", "fp", "fn", "tn",
                                          "excluded_ambiguous", "excluded_boundary")},
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Local data/main/xml directory")
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("Expected a directory of TEI XML files")
    print(json.dumps(evaluate(args.directory), indent=2))


if __name__ == "__main__":
    main()
