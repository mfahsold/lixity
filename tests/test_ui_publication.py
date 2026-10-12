"""Publication controls use explicit project data and the shared Settings form."""

from html.parser import HTMLParser
from pathlib import Path

from lixity.ui import render_dashboard


class Controls(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: dict[str, dict[str, str | None]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        identifier = values.get("id")
        if identifier:
            self.elements[identifier] = {**values, "tag": tag}


def test_publication_fields_are_collapsed_escaped_and_context_bound() -> None:
    html = render_dashboard(
        [], [], controls=True, author_setting_enabled=True,
        publication={"enabled": True, "publisher_name": 'Synthetic <script>alert(1)</script>',
                     "publisher_address": "Synthetic street\nSynthetic town", "year": "2026"},
        publication_error='<img src=x onerror="alert(1)">', project_token="a" * 64,
    )
    parsed = Controls()
    parsed.feed(html)
    assert "open" not in parsed.elements["settings-publication"]
    assert parsed.elements["settings-form"]["data-project-token"] == "a" * 64
    assert parsed.elements["set-publication-enabled"]["type"] == "checkbox"
    assert "checked" in parsed.elements["set-publication-enabled"]
    assert parsed.elements["set-publication-publisher_name"]["value"] == 'Synthetic <script>alert(1)</script>'
    assert "disabled" not in parsed.elements["set-publication-publisher_name"]
    assert "Synthetic &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert '<img src=x onerror="alert(1)">' not in html
    assert parsed.elements["publication-settings-error"]["role"] == "alert"


def test_publication_without_explicit_root_is_disabled_with_no_inferred_data() -> None:
    html = render_dashboard([], [], controls=True)
    parsed = Controls()
    parsed.feed(html)
    fields = {key: value for key, value in parsed.elements.items() if key.startswith("set-publication-")}
    assert len(fields) == 12
    assert all("disabled" in value for value in fields.values())
    assert "checked" not in fields["set-publication-enabled"]
    assert fields["set-publication-publisher_name"]["value"] == ""
    assert fields["set-publication-isbn_print"]["value"] == ""


def test_canonical_tokens_are_inlined_before_component_styles() -> None:
    html = render_dashboard([], [])
    assert html.index("--status-success-fg:") < html.index(".research-badge.badge-success")
    assert "var(--status-warning-fg)" in html
    assert "design-tokens.css" not in html, "Standalone output must not request a stylesheet"


def test_pages_stages_the_packaged_canonical_tokens(tmp_path: Path) -> None:
    from scripts.stage_pages import stage

    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "pages"
    stage(root / "docs", output)
    assert (output / "assets/design-tokens.css").read_bytes() == (
        root / "src/lixity/ui/assets/design-tokens.css"
    ).read_bytes()
    assert '@import url("./design-tokens.css")' in (output / "assets/site.css").read_text()
