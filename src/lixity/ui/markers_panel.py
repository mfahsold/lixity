"""Reusable editorial work-markers panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..markers import Marker
from ..style_profile import ChapterProfile
from .components import badge, empty_state, esc, label, panel_label, panel_start, table_wrap_start


def render_markers_panel(
    markers: Sequence[Marker] | None,
    chapters: Sequence[ChapterProfile],
    labels: Mapping[str, str] | None = None,
    controls: bool = False,
) -> str:
    """Renders the editor-visible work markers table panel."""
    if markers is None:
        return ""

    L = panel_label(labels)

    parts: list[str] = [panel_start("markers", labels, "markers", help_key="markers")]
    if markers:
        parts.append(table_wrap_start(label(labels, "markers")))
        parts.append("<thead><tr>")
        parts.append(
            f"<th scope=\"col\">{L('status')}</th><th scope=\"col\">{L('chapter')}</th>"
            f'<th scope="col" class="num">{L("line")}</th><th scope="col">{L("notes")}</th>'
        )
        if controls:
            parts.append(f'<th scope="col"><span class="sr-only">{L("actions")}</span></th>')
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
                f'<tr class="row-link" data-line="{m.line}">'
                f'<td>{badge(kind_label, variant="", css_class=f"marker-{m.kind}")}</td>'
                f"<td>{chapter_cell}</td>"
                f'<td class="num"><button type="button" class="ctl ctl-sm" data-line="{m.line}">'
                f'{L("line")} {m.line}</button></td><td>{note}</td>'
            )
            if controls:
                parts.append(
                    f'<td><button type="button" class="ctl" data-marker-resolve="{esc(m.id, quote=True)}">'
                    f"{L('marker_resolve')}</button></td>"
                )
            parts.append("</tr>")
        parts.append("</tbody></table></div>")
    else:
        parts.append(empty_state(L("markers_empty")))
    parts.append("</section>")
    return "".join(parts)
