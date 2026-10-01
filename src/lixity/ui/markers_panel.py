"""Reusable editorial work-markers panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..markers import Marker
from ..style_profile import ChapterProfile
from .components import esc, help_term, label


def render_markers_panel(
    markers: Sequence[Marker] | None,
    chapters: Sequence[ChapterProfile],
    labels: Mapping[str, str] | None = None,
    controls: bool = False,
) -> str:
    """Renders the editor-visible work markers table panel."""
    if markers is None:
        return ""

    def L(key: str) -> str:
        return esc(label(labels, key))

    parts: list[str] = ['<section class="panel" id="markers">']
    parts.append(f"<h2>{help_term(labels, 'markers', L('markers'))}</h2>")
    if markers:
        parts.append('<div class="table-wrap">')
        parts.append("<table><thead><tr>")
        parts.append(
            f"<th>{L('status')}</th><th>{L('chapter')}</th>"
            f'<th class="num">{L("line")}</th><th>{L("notes")}</th>'
        )
        if controls:
            parts.append("<th></th>")
        parts.append("</tr></thead><tbody>")
        for m in markers:
            kind_label = label(labels, "marker_" + m.kind)
            note = esc(str(m.note or "")) or "–"
            marker_chapter = next(
                (c for c in chapters if c.start_line <= m.line <= c.end_line), None
            )
            chapter_cell = (
                f"{L('chapter')} {marker_chapter.num} · {esc(marker_chapter.title)}"
                if marker_chapter is not None
                else "–"
            )
            parts.append(
                f'<tr class="row-link" data-line="{m.line}" role="button" tabindex="0">'
                f'<td><span class="badge marker-{m.kind}">{esc(kind_label)}</span></td>'
                f"<td>{chapter_cell}</td>"
                f'<td class="num">{L("line")} {m.line}</td><td>{note}</td>'
            )
            if controls:
                parts.append(
                    f'<td><button class="ctl" data-marker-resolve="{esc(m.id, quote=True)}">'
                    f"{L('marker_resolve')}</button></td>"
                )
            parts.append("</tr>")
        parts.append("</tbody></table></div>")
    else:
        parts.append(f'<p class="hint">{L("markers_empty")}</p>')
    parts.append("</section>")
    return "".join(parts)
