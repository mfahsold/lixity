"""Join source presentation to unchanged analysis owners without copying prose."""

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ..manuscript_document import BlockKind, _protected_source, manuscript_blocks
from ..markdown_parser import _without_comments
from ..models import CorpusConfig
from ..style_profile import ParagraphProfile


@dataclass(frozen=True)
class ReaderBlock:
    """One source-ordered block or reference to an existing ``p-N`` owner.

    ``profile_index`` is the original input index, never a presentation index.
    Profile text is exact and must not receive inline Markdown normalization.
    Other blocks have no measurements or claim-writing capability. All text is
    data to escape at the HTML boundary, including HTML and TeX-looking input.
    """

    kind: BlockKind | Literal["profile"]
    text: str
    start_line: int
    end_line: int
    level: int = 3
    profile_index: int | None = None
    is_chapter: bool = False


def reader_blocks(
    text: str, config: CorpusConfig, paragraphs: Sequence[ParagraphProfile],
) -> list[ReaderBlock]:
    """Interleave structure around each exact profile once, joined by source span.

    One profile may own several presentation blocks, such as consecutive ordered
    list items. Its single existing DOM owner takes precedence over those blocks.
    A partially owned block keeps uncovered source lines as literal paragraphs;
    it never repeats the profile or silently discards the remaining source.
    Overlapping profile owners are ambiguous and fail explicitly. Presentation
    boundaries and indices cannot expand statistical or research-anchor coverage.
    """
    owners = sorted(enumerate(paragraphs), key=lambda item: item[1].start_line)
    previous_end = 0
    result: list[ReaderBlock] = []
    for index, profile in owners:
        if profile.start_line < 1 or profile.end_line < profile.start_line:
            raise ValueError("Invalid paragraph profile source span")
        if profile.start_line <= previous_end:
            raise ValueError("Overlapping paragraph profile source spans")
        previous_end = profile.end_line
        result.append(ReaderBlock(
            "profile", profile.text, profile.start_line, profile.end_line, profile_index=index,
        ))
    starts = [profile.start_line for _, profile in owners]
    ends = [profile.end_line for _, profile in owners]
    literal_lines: list[str] | None = None

    def retain_literal(first: int, last: int) -> None:
        nonlocal literal_lines
        if first > last:
            return
        if literal_lines is None:
            protected, sentinel, _literal = _protected_source(text)
            literal_lines = _without_comments(protected).replace(sentinel, "<").splitlines()
        while first <= last and not literal_lines[first - 1].strip():
            first += 1
        while last >= first and not literal_lines[last - 1].strip():
            last -= 1
        if first <= last:
            result.append(ReaderBlock(
                "paragraph", "\n".join(literal_lines[first - 1:last]), first, last,
            ))

    for block in manuscript_blocks(text, config):
        first = bisect_left(ends, block.start_line)
        last = bisect_right(starts, block.end_line)
        if first == last:
            result.append(ReaderBlock(
                block.kind, block.text, block.start_line, block.end_line,
                level=block.level, is_chapter=block.is_chapter,
            ))
            continue
        cursor = block.start_line
        for _, owner in owners[first:last]:
            retain_literal(cursor, owner.start_line - 1)
            cursor = max(cursor, owner.end_line + 1)
        retain_literal(cursor, block.end_line)
    return sorted(result, key=lambda block: block.start_line)
