"""Markdown projections shared by measured dossier evidence."""

from collections.abc import Iterable, Mapping

from ..format import num


def dossier_quote(
    text: str, *, label: str | None = None, matches: Iterable[tuple[int, int]] = (),
) -> str:
    """Quote every source line so that prose cannot become dossier structure."""
    segments: list[str] = []
    previous = 0
    for start, end in matches:
        if not previous <= start < end <= len(text):
            continue
        matched = text[start:end]
        # Keep unusual configured patterns literal when they cannot be marked
        # as one inline span. The complete source passage remains readable.
        if (matched != matched.strip() or "\n" in matched or "*" in matched
                or text[start - 1:start] == "*" or text[end:end + 1] == "*"):
            continue
        segments.extend((text[previous:start], f"**{matched}**"))
        previous = end
    segments.append(text[previous:])
    lines = [f"> **{label}**", ">"] if label else []
    lines.extend(f"> {line}" if line else ">" for line in "".join(segments).split("\n"))
    return "\n".join(lines)


def chapter_mention_table(
    counts: Iterable[tuple[int, int]], labels: Mapping[str, str], language: str,
) -> str:
    rows = [f"| {labels['research_chapter']} | {labels['research_dossier_character_mentions']} |", "| --- | ---: |"]
    rows.extend(f"| {num(chapter, language, 0)} | {num(mentions, language, 0)} |" for chapter, mentions in counts)
    return "\n".join(rows)


def name_mentions_summary(
    name: str, mentions: int, covered: int, chapters: int, labels: Mapping[str, str], language: str,
) -> str:
    key = "research_dossier_character_summary_one" if mentions == 1 else "research_dossier_character_summary"
    return labels[key].format(name=name, mentions=num(mentions, language, 0),
                              covered=num(covered, language, 0), chapters=num(chapters, language, 0))


def chapter_heading(chapter: int, title: str, labels: Mapping[str, str], language: str) -> str:
    label = labels["publication_chapter"].format(number=num(chapter, language, 0))
    title = " ".join(title.split())
    return f"{label} · {title}" if title and title.casefold() != label.casefold() else label


def chapter_line_range(start: int, end: int, labels: Mapping[str, str], language: str) -> str:
    key = "research_dossier_character_lines_one" if start == end else "research_dossier_character_lines"
    return labels[key].format(start=num(start, language, 0), end=num(end, language, 0))
