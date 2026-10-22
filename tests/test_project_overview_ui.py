"""Native project inspection stays separate from settings and embedding fallbacks."""

import pytest

from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS


@pytest.mark.parametrize("locale", ("en", "de", "fr", "es", "it", "pt", "nl"))
def test_native_overview_precedes_settings_and_replaces_the_generated_file_list(locale):
    rendered = render_dashboard([], [], controls=True, language_key=locale,
        labels=WORKSPACE_LABELS[locale], project_overview_enabled=True, project_token="a" * 64,
        artifacts=[{"name": "Synthetic.pdf", "href": "/artifact/Synthetic.pdf", "size_kb": 1}])
    assert rendered.index('id="project-overview"') < rendered.index('id="settings-form"')
    assert 'id="project-overview-status" role="status"' in rendered
    assert 'id="project-overview-refresh"' in rendered
    assert WORKSPACE_LABELS[locale]["project_structure_title"] in rendered
    assert '<div class="artifacts">' not in rendered
    assert "Synthetic.pdf" not in rendered


def test_embedding_keeps_the_existing_generated_file_fallback_without_overview_capability():
    rendered = render_dashboard([], [], controls=True,
        artifacts=[{"name": "Synthetic.pdf", "href": "/artifact/Synthetic.pdf", "size_kb": 1}])
    assert 'id="project-overview"' not in rendered
    assert '<div class="artifacts">' in rendered
    assert 'href="/artifact/Synthetic.pdf"' in rendered


@pytest.mark.parametrize("options", [{"controls": False}, {"controls": True, "read_only": True}])
def test_overview_cannot_expose_project_paths_in_static_or_read_only_documents(options):
    rendered = render_dashboard([], [], project_overview_enabled=True, project_token="a" * 64, **options)
    assert 'id="project-overview"' not in rendered
    assert 'id="project-overview-label-keys"' not in rendered


def test_structure_role_state_and_issue_labels_cover_every_supported_locale():
    from lixity.workspace_labels import (
        PROJECT_STRUCTURE_ISSUE_LABELS,
        PROJECT_STRUCTURE_ROLE_LABELS,
        PROJECT_STRUCTURE_STATE_LABELS,
    )

    assert set(PROJECT_STRUCTURE_ROLE_LABELS) == {
        "manuscript", "research", "outputs", "output_archive", "submissions",
    }
    assert set(PROJECT_STRUCTURE_STATE_LABELS) == {
        "available", "missing", "unassigned", "invalid", "ambiguous", "unreadable", "unsafe", "unknown",
    }
    assert PROJECT_STRUCTURE_ISSUE_LABELS["output-source-alias"] == PROJECT_STRUCTURE_ISSUE_LABELS["output-config-alias"]
    assert PROJECT_STRUCTURE_ISSUE_LABELS["config-too-large"] == PROJECT_STRUCTURE_ISSUE_LABELS["discovery-truncated"]
    for labels in WORKSPACE_LABELS.values():
        for key in [*PROJECT_STRUCTURE_ROLE_LABELS.values(), *PROJECT_STRUCTURE_STATE_LABELS.values(),
                    *PROJECT_STRUCTURE_ISSUE_LABELS.values()]:
            assert labels[key] and not labels[key].startswith("project_structure_")


@pytest.mark.parametrize("research_token,expected", [("a" * 64, "true"), ("b" * 64, "false"), ("", "false")])
def test_overview_dossier_navigation_requires_the_same_selected_archive(research_token, expected):
    rendered = render_dashboard([], [], controls=True, project_overview_enabled=True,
        site_publication_context_token="a" * 64, research_context_token=research_token)
    assert f'data-research-navigation="{expected}"' in rendered
