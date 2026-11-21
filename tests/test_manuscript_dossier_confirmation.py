"""Accepted preview bindings and independent draft identities."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from urllib.parse import urlencode

import pytest
from support import LoopbackServer, make_handler

from lixity.research import api, dossiers
from lixity.research.repository import Repository, ResearchConflictError, ResearchError
from lixity.server.pdf_context import research_context_token

_MANUSCRIPT = (
    "## The coast\n\nAnna opened the gate.\n\n---\n\n"
    "Anna stepped into the courtyard. The rain stopped.\n\n---\n\nThe ferry left the harbor."
)


def _project(tmp_path: Path, text: str = _MANUSCRIPT) -> Path:
    api.init(tmp_path, title="Synthetic manuscript archive")
    manuscript = tmp_path / "novel.md"
    manuscript.write_text(text, encoding="utf-8")
    return manuscript


def _previews(root: Path, source: Path, **kwargs):
    report = api.manuscript_dossier_drafts(root, source, **kwargs)
    return {draft["id"]: draft for draft in report["drafts"]}


def test_duplicate_titles_do_not_merge_scenes_or_hide_the_register(tmp_path: Path) -> None:
    manuscript = _project(tmp_path)
    (tmp_path / "lixity.toml").write_text(
        '[scene_analysis.titles]\n"1:1" = "The gate"\n"1:2" = "The gate"\n', encoding="utf-8",
    )
    # A manual item and a legacy generated item with ambiguous label should
    # both leave the independent scene choices available.
    api.create_dossier(tmp_path, "Scene: unrelated notes", "Separate notes.")
    api.create_dossier(tmp_path, "Scene: The gate", "Older note without a specific scene position.",
                       tags=["manuscript-draft", "scene"])
    original = _previews(tmp_path, manuscript, kind="scene")
    assert set(original) == {"scenes:manuscript", "scene:1:1", "scene:1:2", "scene:1:3"}
    for identifier in ("scene:1:1", "scenes:manuscript", "scene:1:2"):
        api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id=identifier,
                                           preview_sha256=original[identifier]["preview_sha256"])
    assert set(_previews(tmp_path, manuscript, kind="scene")) == {"scene:1:3"}


def test_legacy_register_and_scene_scope_are_separate(tmp_path: Path) -> None:
    manuscript = _project(tmp_path)
    api.create_dossier(tmp_path, "Scene register (1 chapters, 3 scenes)", "Older register version.",
                       tags=["manuscript-draft", "scenes"])
    api.create_dossier(tmp_path, "Scene: The coast · 2", "Older second scene.",
                       tags=["manuscript-draft", "scene"])
    assert set(_previews(tmp_path, manuscript, kind="scene")) == {"scene:1:1", "scene:1:3"}


def test_named_manual_dossiers_hide_only_exact_typed_entity(tmp_path: Path) -> None:
    manuscript = _project(tmp_path, _MANUSCRIPT.replace("courtyard", "Anna"))
    (tmp_path / "lixity.toml").write_text('locations = ["Anna"]\n[characters.Anna]\naliases = []\n', encoding="utf-8")
    assert "location:anna" in _previews(tmp_path, manuscript, kind="location")
    api.create_dossier(tmp_path, "Location: Anna", "Named place.")
    api.create_dossier(tmp_path, "Character: Marianne", "Different character.")
    assert "character:anna" in _previews(tmp_path, manuscript, kind="character")
    assert "location:anna" not in _previews(tmp_path, manuscript, kind="location")


def test_legacy_name_id_is_only_accepted_when_unambiguous(tmp_path: Path) -> None:
    manuscript = _project(tmp_path, "## Die Küste\n\nSie fuhr nach Äber, drei Tage später nach Öber.")
    (tmp_path / "lixity.toml").write_text('locations = ["Äber", "Öber"]\n', encoding="utf-8")
    candidates = _previews(tmp_path, manuscript, kind="location")
    assert len(candidates) == 2
    assert {item["legacy_id"] for item in candidates.values()} == {"location:ber"}
    with pytest.raises(ResearchError, match="ambiguous"):
        api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id="location:ber")
    selected = candidates["location:%C3%A4ber"]
    receipt = api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id=selected["id"],
                                                preview_sha256=selected["preview_sha256"])
    assert receipt["draft"]["evidence_hints"]["location"] == "Äber"
    assert set(_previews(tmp_path, manuscript, kind="location")) == {"location:%C3%B6ber"}
    assert api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id="location:%C3%B6ber")["dossier_id"]


def test_changed_scene_at_same_position_is_not_the_saved_scene(tmp_path: Path) -> None:
    manuscript = _project(tmp_path)
    scene = _previews(tmp_path, manuscript, kind="scene")["scene:1:2"]
    api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id=scene["id"],
                                       preview_sha256=scene["preview_sha256"])
    (tmp_path / "lixity.toml").write_text('[scene_analysis.titles]\n"1:2"="Named later"\n', encoding="utf-8")
    assert scene["id"] not in _previews(tmp_path, manuscript, kind="scene")
    manuscript.write_text(_MANUSCRIPT.replace("The rain stopped.", "The gate rattled behind her."), encoding="utf-8")
    assert scene["id"] in _previews(tmp_path, manuscript, kind="scene")


def test_confirmation_checks_exact_content_source_and_settings(tmp_path: Path) -> None:
    manuscript = _project(tmp_path)
    other_source = tmp_path / "another.md"
    other_source.write_bytes(manuscript.read_bytes())
    repo = Repository(tmp_path)
    original = repo.snapshot()
    token = research_context_token(tmp_path)
    query = urlencode({"kind": "scene", "research_token": token})
    endpoint = "/api/research-dossier-from-manuscript"
    with LoopbackServer(make_handler(tmp_path, source_input=manuscript)) as server:
        status, report = server.request_json("/api/research/manuscript-dossier-drafts?" + query)
        assert status == 200
        assert report["project_id"] == original.project.id
        draft = next(item for item in report["drafts"] if item["id"] == "scene:1:2")
        binding = {"project_id": report["project_id"], "research_token": token, "draft_id": draft["id"]}
        assert server.request(endpoint, payload={**binding, "preview_sha256": None}).status == 400
        binding["preview_sha256"] = draft["preview_sha256"]
        assert server.request(endpoint, payload={**binding, "project_id": "different-project"}).status == 409
        assert server.request(endpoint, payload={**binding, "manuscript": str(other_source)}).status == 409
        manuscript.write_text(_MANUSCRIPT + "\n", encoding="utf-8")
        status, error = server.request_json(endpoint, payload=binding)
        assert status == 409 and error["code"] == "stale-draft"
        manuscript.write_text(_MANUSCRIPT, encoding="utf-8")
        config = tmp_path / "lixity.toml"
        config.write_text('[scene_analysis.titles]\n"1:2" = "Changed title"\n', encoding="utf-8")
        assert server.request(endpoint, payload=binding).status == 409
        assert repo.snapshot().digest == original.digest
        config.unlink()
        status, receipt = server.request_json(endpoint, payload=binding)
        assert status == 200 and receipt["draft"]["preview_sha256"] == draft["preview_sha256"]
        assert api.get_dossier(tmp_path, receipt["dossier_id"])["body"] == draft["body"]
        assert server.request(endpoint, payload=binding).status == 409
        status, direct = server.request_json(endpoint, payload={
            "draft_id": "scene:1:3", "research_token": token,
        })
        assert status == 200 and direct["draft"]["id"] == "scene:1:3"


def test_confirming_a_character_does_not_recompute_stale_scene_settings(tmp_path: Path) -> None:
    manuscript = _project(tmp_path)
    (tmp_path / "lixity.toml").write_text(
        '[characters.Anna]\naliases=[]\n[scene_analysis.groups.Dialog.targets]\nasl=[1,80]\n'
        '[scene_analysis.assignments]\n"9:1"="Dialog"\n', encoding="utf-8",
    )
    draft = _previews(tmp_path, manuscript, kind="character")["character:anna"]
    receipt = api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id=draft["id"],
                                                 preview_sha256=draft["preview_sha256"])
    assert receipt["draft"]["id"] == draft["id"]


def test_include_existing_links_current_revision_of_legacy_generated_character(tmp_path: Path) -> None:
    manuscript = _project(tmp_path)
    (tmp_path / "lixity.toml").write_text('[characters.Anna]\naliases=[]\n', encoding="utf-8")
    created = api.create_dossier(tmp_path, "Figur: Anna", "## Überblick\n\nAlte Notizen.",
                                 tags=["manuscript-draft", "character"])
    identifier = created["dossier_id"]
    api.revise_record(tmp_path, "dossier", identifier,
                      changes={"title": "Anna an der Küste", "body": "Meine aktuellen Notizen.", "tags": ["notes"]},
                      expected_snapshot=created["snapshot"], expected_revision=1,
                      change_kind="correction", reason="Clarify synthetic notes")
    repo = Repository(tmp_path)
    accepted = repo.snapshot()
    token = research_context_token(tmp_path)
    query = urlencode({"kind": "character", "research_token": token})
    url = "/api/research/manuscript-dossier-drafts?" + query
    with LoopbackServer(make_handler(tmp_path, source_input=manuscript, language="de")) as server:
        status, report = server.request_json(url)
        assert status == 200 and report["drafts"] == [] and report["skipped_existing"] == 1
        status, report = server.request_json(url + "&include_existing=1")
        assert status == 200 and report["skipped_existing"] == 0
        draft, = report["drafts"]
        assert draft["already_covered"] is True
        assert draft["existing_dossier"] == {"id": identifier, "title": "Anna an der Küste", "revision": 2,
                                             "project_id": accepted.project.id, "snapshot": accepted.digest}
        blocked = server.request("/api/research-dossier-from-manuscript", payload={
            "draft_id": draft["id"], "preview_sha256": draft["preview_sha256"], "research_token": token,
        })
        assert blocked.status == 409
    assert repo.snapshot().digest == accepted.digest
    assert api.get_dossier(tmp_path, identifier)["body"] == "Meine aktuellen Notizen."


def test_existing_manual_and_ambiguous_character_coverage_cannot_link(tmp_path: Path) -> None:
    manuscript = _project(tmp_path)
    (tmp_path / "lixity.toml").write_text('[characters.Anna]\naliases=[]\n', encoding="utf-8")
    api.create_dossier(tmp_path, "Character: Anna", "Authored notes only.", tags=["character"])
    covered = _previews(tmp_path, manuscript, kind="character", exclude_existing=False)["character:anna"]
    assert covered["already_covered"] is True
    assert "existing_dossier" not in covered
    api.create_dossier(tmp_path, "Figur: Anna", "A legacy generated body.", tags=["character", "manuscript-draft"])
    ambiguous = _previews(tmp_path, manuscript, kind="character", exclude_existing=False)["character:anna"]
    assert ambiguous["already_covered"] is True
    assert "existing_dossier" not in ambiguous
    assert ambiguous["preview_sha256"] == covered["preview_sha256"]


def test_concurrent_confirmations_can_commit_only_one_record(tmp_path: Path, monkeypatch) -> None:
    manuscript = _project(tmp_path)
    draft = _previews(tmp_path, manuscript, kind="scene")["scene:1:2"]
    barrier = Barrier(2, timeout=10)
    first_published = Event()
    commit = dossiers._commit_dossier

    def save_at_same_snapshot(*args, **kwargs):
        if barrier.wait():
            assert first_published.wait(10)
            return commit(*args, **kwargs)
        receipt = commit(*args, **kwargs)
        first_published.set()
        return receipt

    monkeypatch.setattr(dossiers, "_commit_dossier", save_at_same_snapshot)
    with ThreadPoolExecutor(2) as pool:
        operations = [pool.submit(api.create_dossier_from_manuscript, tmp_path, manuscript,
                                  draft_id=draft["id"], preview_sha256=draft["preview_sha256"]) for _ in range(2)]
        outcomes = [operation.exception(timeout=15) for operation in operations]
    assert outcomes.count(None) == 1
    assert any(isinstance(error, ResearchConflictError) for error in outcomes)
    assert len(api.list_dossiers(tmp_path)["dossiers"]) == 1
    with pytest.raises(ResearchConflictError, match="already exists"):
        api.create_dossier_from_manuscript(tmp_path, manuscript, draft_id=draft["id"])
