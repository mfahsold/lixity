"""Project structure inspection observes metadata without reorganizing sources."""

import importlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.portability


def inspect(project, **kwargs):
    assert importlib.util.find_spec("lixity.project_structure") is not None, "Project structure inspection is missing"
    return importlib.import_module("lixity.project_structure").inspect_project(project, **kwargs)


def roles(result):
    return {role["role"]: role for role in result["roles"]}


def codes(result):
    return {issue["code"] for issue in result["issues"]}


def symlink(path, target, *, directory=False):
    try:
        path.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")


def test_empty_project_reports_unassigned_roles_without_creating_layout(tmp_path):
    result = inspect(tmp_path)
    assert result["schema_version"] == "lixity-project-structure/1"
    assert result["ok"] is True and result["has_errors"] is False
    assert result["root"] == str(tmp_path.resolve())
    assert roles(result)["manuscript"]["state"] == "unassigned"
    assert roles(result)["submissions"] == {"role": "submissions", "path": None, "state": "unassigned"}
    assert roles(result)["research"]["state"] == "missing"
    assert roles(result)["outputs"]["path"] == "exports"
    assert roles(result)["output_archive"]["path"] == "exports/archive"
    assert result["artifacts"] == [] and result["truncated"] is False
    assert list(tmp_path.iterdir()) == []


def test_configured_source_and_outputs_are_read_only_metadata(tmp_path, monkeypatch):
    from lixity.io import FileUtils

    source = tmp_path / "draft.md"
    source.write_bytes(b"\xffSynthetic manuscript bytes must not be decoded.")
    (tmp_path / "lixity.toml").write_text('manuscript = "draft.md"\n')
    (tmp_path / "research").mkdir()
    archive = tmp_path / "exports" / "archive"
    archive.mkdir(parents=True)
    artifact = tmp_path / "exports" / "draft_report.md"
    artifact.write_text("Synthetic generated output.")
    before = {str(path.relative_to(tmp_path)): (path.stat().st_mtime_ns, path.read_bytes())
              for path in tmp_path.rglob("*") if path.is_file()}
    original = FileUtils.read_file

    def read_config_only(path, *args, **kwargs):
        assert Path(path) != source, "Structure inspection must not read manuscript bytes"
        assert "research" not in Path(path).relative_to(tmp_path).parts
        return original(path, *args, **kwargs)

    monkeypatch.setattr(FileUtils, "read_file", read_config_only)
    result = inspect(tmp_path)
    assert roles(result)["manuscript"] == {
        "role": "manuscript", "path": "draft.md", "state": "available",
        "selection": "configured", "configured_path": "draft.md",
    }
    assert all(roles(result)[name]["state"] == "available" for name in ("research", "outputs", "output_archive"))
    assert result["artifacts"] == [{"name": artifact.name, "path": "exports/draft_report.md",
                                    "size_bytes": artifact.stat().st_size,
                                    "provenance": "unknown", "downloadable": True}]
    after = {str(path.relative_to(tmp_path)): (path.stat().st_mtime_ns, path.read_bytes())
             for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


def test_selected_source_discloses_configured_mismatch(tmp_path):
    (tmp_path / "lixity.toml").write_text('manuscript = "draft.md"\n')
    (tmp_path / "draft.md").write_text("Configured synthetic source.")
    selected = tmp_path / "revision.md"
    selected.write_text("Selected synthetic source.")
    result = inspect(tmp_path, selected_manuscript=selected)
    assert roles(result)["manuscript"]["path"] == "revision.md"
    assert roles(result)["manuscript"]["configured_path"] == "draft.md"
    assert roles(result)["manuscript"]["selection"] == "selected"
    assert "manuscript-selection-mismatch" in codes(result)


def test_missing_configured_source_does_not_fall_back_to_another_manuscript(tmp_path):
    (tmp_path / "lixity.toml").write_text('manuscript = "missing.md"\n')
    (tmp_path / "manuscript.md").write_text("Another synthetic source.")
    result = inspect(tmp_path)
    assert roles(result)["manuscript"]["path"] == "missing.md"
    assert roles(result)["manuscript"]["state"] == "missing"
    assert "manuscript-missing" in codes(result) and result["has_errors"] is True


def test_selected_source_does_not_hide_a_missing_configured_reference(tmp_path):
    (tmp_path / "lixity.toml").write_text('manuscript = "missing.md"\n')
    selected = tmp_path / "selected.md"
    selected.write_text("Synthetic selection.")
    result = inspect(tmp_path, selected_manuscript=selected)
    assert roles(result)["manuscript"]["state"] == "available"
    assert {"code": "manuscript-missing", "severity": "error", "path": "missing.md"} in result["issues"]


def test_absolute_configured_path_cannot_become_a_valid_candidate(tmp_path):
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source.")
    (tmp_path / "lixity.toml").write_text(f"manuscript = {json.dumps(str(source))}\n")
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "report.txt").write_text("Synthetic output.")
    result = inspect(tmp_path)
    assert roles(result)["manuscript"]["state"] == "unsafe"
    assert roles(result)["manuscript"]["path"] is None
    assert result["artifacts"][0]["downloadable"] is False


def test_escaping_selected_source_cannot_leave_downloads_enabled(tmp_path):
    (tmp_path / "exports").mkdir()
    (tmp_path / "exports" / "report.txt").write_text("Synthetic output.")
    outside = tmp_path.parent / f"{tmp_path.name}-external.md"
    outside.write_text("Synthetic unrelated source.")
    result = inspect(tmp_path, selected_manuscript=outside)
    assert roles(result)["manuscript"]["state"] == "unsafe"
    assert result["artifacts"][0]["downloadable"] is False
    assert str(outside) not in json.dumps(result)


@pytest.mark.parametrize("text,code", [
    ('manuscript = [', "invalid-config"),
    ('manuscript = 42\n', "manuscript-invalid"),
    ('manuscript = "../outside.md"\n', "manuscript-unsafe"),
])
def test_invalid_configuration_never_looks_like_automatic_discovery(tmp_path, text, code):
    (tmp_path / "lixity.toml").write_text(text)
    (tmp_path / "manuscript.md").write_text("Synthetic source.")
    result = inspect(tmp_path)
    assert code in codes(result)
    assert roles(result)["manuscript"]["state"] in {"invalid", "unsafe"}
    assert result["has_errors"] is True


def test_discovery_uses_shared_conventions_and_reports_ambiguity(tmp_path):
    (tmp_path / "NDA.md").write_text("Synthetic unrelated data.")
    (tmp_path / "a.md").write_text("Synthetic A.")
    first = inspect(tmp_path)
    assert roles(first)["manuscript"]["path"] == "a.md"
    assert roles(first)["manuscript"]["selection"] == "discovered"
    (tmp_path / "b.md").write_text("Synthetic B.")
    ambiguous = inspect(tmp_path)
    assert roles(ambiguous)["manuscript"]["state"] == "ambiguous"
    assert "manuscript-ambiguous" in codes(ambiguous)


def test_ancestor_configuration_does_not_change_project_selection(tmp_path):
    (tmp_path / "lixity.toml").write_text('manuscript = "outside.md"\n')
    child = tmp_path / "child"
    child.mkdir()
    (child / "manuscript.md").write_text("Synthetic child.")
    result = inspect(child)
    assert roles(result)["manuscript"]["path"] == "manuscript.md"
    assert roles(result)["manuscript"]["configured_path"] is None


def test_safe_stable_output_symlink_is_downloadable_but_source_alias_is_not(tmp_path):
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source.")
    exports = tmp_path / "exports"
    exports.mkdir()
    version = exports / "report_2026-10-22.md"
    version.write_text("Synthetic output.")
    symlink(exports / "report.md", version.name)
    symlink(exports / "source.md", source)
    result = inspect(tmp_path)
    items = {item["name"]: item for item in result["artifacts"]}
    assert items["report.md"]["downloadable"] is True
    assert items["source.md"]["downloadable"] is False
    assert "output-source-alias" in codes(result)


def test_output_hardlinks_to_source_and_configuration_are_not_downloadable(tmp_path):
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source.")
    config = tmp_path / "lixity.toml"
    config.write_text('title = "Synthetic project"\n')
    exports = tmp_path / "exports"
    exports.mkdir()
    try:
        os.link(source, exports / "source.md")
        os.link(config, exports / "settings.txt")
    except OSError as exc:
        pytest.skip(f"Hard links unavailable: {exc}")
    result = inspect(tmp_path)
    assert not any(item["downloadable"] for item in result["artifacts"])
    assert {"output-source-alias", "output-config-alias"} <= codes(result)


def test_broken_and_escaping_output_links_are_reported_without_external_paths(tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("Synthetic external data.")
    symlink(exports / "escape.txt", outside)
    symlink(exports / "broken.txt", "absent.txt")
    result = inspect(tmp_path)
    assert not any(item["downloadable"] for item in result["artifacts"])
    assert {"artifact-symlink-broken", "artifact-path-escape"} <= codes(result)
    assert str(outside) not in json.dumps(result)


@pytest.mark.parametrize("name", ["research", "exports"])
def test_role_files_are_explicit_errors(tmp_path, name):
    (tmp_path / name).write_text("Synthetic wrong node.")
    result = inspect(tmp_path)
    assert "role-not-directory" in codes(result) and result["has_errors"] is True


def test_symlinked_role_directory_is_not_traversed(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "private.txt").write_text("Synthetic unrelated file.")
    symlink(tmp_path / "exports", elsewhere, directory=True)
    result = inspect(tmp_path)
    assert roles(result)["outputs"]["state"] == "unsafe"
    assert result["artifacts"] == [] and "role-symlink" in codes(result)


def test_symlinked_configuration_is_not_read_or_followed(tmp_path, monkeypatch):
    from lixity.io import FileUtils

    outside = tmp_path.parent / f"{tmp_path.name}-settings.toml"
    outside.write_text('title = "Synthetic external settings"\n')
    symlink(tmp_path / "lixity.toml", outside)

    def forbidden(*args, **kwargs):
        pytest.fail("Unsafe configuration must not be read")

    monkeypatch.setattr(FileUtils, "read_file", forbidden)
    result = inspect(tmp_path)
    assert "unsafe-config" in codes(result)
    assert roles(result)["manuscript"]["state"] == "unsafe"
    assert str(outside) not in json.dumps(result)


def test_source_metadata_failure_stays_unreadable(tmp_path, monkeypatch):
    source = tmp_path / "selected.md"
    source.write_text("Synthetic source.")
    original = Path.stat

    def stat(path, *args, **kwargs):
        if path == source:
            raise PermissionError("Synthetic source metadata denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    result = inspect(tmp_path, selected_manuscript=source)
    assert roles(result)["manuscript"]["state"] == "unreadable"
    assert "manuscript-unreadable" in codes(result) and result["has_errors"] is True


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX special file")
def test_special_output_nodes_are_metadata_only_and_never_downloadable(tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    os.mkfifo(exports / "synthetic.fifo")
    result = inspect(tmp_path)
    assert result["artifacts"][0]["downloadable"] is False
    assert "artifact-not-file" in codes(result)


def test_oversized_config_is_unknown_and_selected_source_still_appears(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    monkeypatch.setattr(module, "MAX_CONFIG_BYTES", 16)
    (tmp_path / "lixity.toml").write_text('title = "Synthetic title longer than inspection limit"\n')
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source.")
    unknown = inspect(tmp_path)
    assert roles(unknown)["manuscript"]["state"] == "unknown"
    assert "config-too-large" in codes(unknown) and unknown["truncated"] is True
    selected = inspect(tmp_path, selected_manuscript=source)
    assert roles(selected)["manuscript"]["state"] == "available"


@pytest.mark.parametrize("configured", [False, True])
def test_inspection_bounds_config_reads_and_reuses_the_mapping(tmp_path, monkeypatch, configured):
    from lixity import workspace

    module = importlib.import_module("lixity.project_structure")
    (tmp_path / "manuscript.md").write_text("Synthetic source.")
    (tmp_path / "lixity.toml").write_text('manuscript = "manuscript.md"\n' if configured else 'title = "Synthetic"\n')
    original = module.read_explicit_project_config

    def bounded(root, **kwargs):
        assert kwargs.get("maximum_bytes") == module.MAX_CONFIG_BYTES
        return original(root, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("Workspace selection must reuse the bounded configuration mapping")

    monkeypatch.setattr(module, "read_explicit_project_config", bounded)
    monkeypatch.setattr(workspace, "read_explicit_project_config", forbidden)
    result = inspect(tmp_path)
    assert roles(result)["manuscript"]["state"] == "available"


@pytest.mark.parametrize("selected", [False, True])
def test_config_growth_after_preflight_stays_unknown_and_bounded(tmp_path, monkeypatch, selected):
    module = importlib.import_module("lixity.project_structure")
    monkeypatch.setattr(module, "MAX_CONFIG_BYTES", 64)
    config = tmp_path / "lixity.toml"
    config.write_text('title = "Before"\n')
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source.")
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "report.txt").write_text("Synthetic output.")
    original = module.read_explicit_project_config

    def grow(root, **kwargs):
        config.write_text('title = "' + "x" * 128 + '"\n')
        return original(root, **kwargs)

    monkeypatch.setattr(module, "read_explicit_project_config", grow)
    result = inspect(tmp_path, selected_manuscript=source if selected else None)
    assert roles(result)["manuscript"]["state"] == ("available" if selected else "unknown")
    assert "config-too-large" in codes(result)
    assert result["truncated"] is True and result["has_errors"] is False
    assert result["artifacts"][0]["downloadable"] is False


def test_output_inventory_has_bounded_display_and_scan(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    monkeypatch.setattr(module, "MAX_ARTIFACTS", 2)
    monkeypatch.setattr(module, "MAX_SCANNED_ENTRIES", 4)
    exports = tmp_path / "exports"
    exports.mkdir()
    for index in range(10):
        (exports / f"report-{index}.txt").write_text("Synthetic output.")
    result = inspect(tmp_path)
    assert len(result["artifacts"]) == 2
    assert result["truncated"] is True and "inventory-truncated" in codes(result)


def test_bounded_discovery_reports_unknown_but_keeps_known_convention(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    monkeypatch.setattr(module, "MAX_SCANNED_ENTRIES", 3)
    for index in range(5):
        (tmp_path / f"unclassified-{index}.txt").write_text("Synthetic unrelated data.")
    result = inspect(tmp_path)
    assert roles(result)["manuscript"]["state"] == "unknown"
    assert "discovery-truncated" in codes(result) and result["truncated"] is True
    (tmp_path / "manuscript.md").write_text("Synthetic conventional source.")
    assert roles(inspect(tmp_path))["manuscript"]["state"] == "available"


def test_fallback_discovery_does_not_repeat_an_unbounded_directory_listing(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    (tmp_path / "draft.md").write_text("Synthetic source.")
    original = os.listdir

    def forbidden(path):
        if Path(path) == tmp_path:
            pytest.fail("Bounded discovery must reuse its captured directory entries")
        return original(path)

    monkeypatch.setattr(os, "listdir", forbidden)
    assert roles(module.inspect_project(tmp_path))["manuscript"]["path"] == "draft.md"


def test_per_artifact_guard_with_selected_source_does_not_discover_or_list_directories(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic selected source.")
    exports = tmp_path / "exports"
    exports.mkdir()
    target = exports / "report.txt"
    target.write_text("Synthetic output.")

    def forbidden(*args, **kwargs):
        pytest.fail("Per-file guard must not discover or scan directories")

    monkeypatch.setattr(module, "discover", forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    assert module.project_artifact_path(tmp_path, target.name, selected_manuscript=source) == target.resolve()


@pytest.mark.parametrize("name", ["../manuscript.md", "archive/report.txt", "archive\\report.txt", "", "."])
def test_per_artifact_guard_rejects_nonflat_names(tmp_path, name):
    module = importlib.import_module("lixity.project_structure")
    with pytest.raises(ValueError):
        module.project_artifact_path(tmp_path, name)


def test_per_artifact_guard_protects_both_selected_and_configured_sources(tmp_path):
    module = importlib.import_module("lixity.project_structure")
    configured = tmp_path / "configured.md"
    selected = tmp_path / "selected.md"
    configured.write_text("Synthetic configured source.")
    selected.write_text("Synthetic selected source.")
    (tmp_path / "lixity.toml").write_text('manuscript = "configured.md"\n')
    exports = tmp_path / "exports"
    exports.mkdir()
    try:
        os.link(configured, exports / "configured.txt")
        os.link(selected, exports / "selected.txt")
    except OSError as exc:
        pytest.skip(f"Hard links unavailable: {exc}")
    for name in ("configured.txt", "selected.txt"):
        with pytest.raises(ValueError):
            module.project_artifact_path(tmp_path, name, selected_manuscript=selected)
    result = inspect(tmp_path, selected_manuscript=selected)
    assert not any(item["downloadable"] for item in result["artifacts"])


@pytest.mark.parametrize("source_name", ["manuscript.md", "draft.md"])
def test_per_artifact_guard_protects_the_discovered_source(tmp_path, source_name):
    module = importlib.import_module("lixity.project_structure")
    source = tmp_path / source_name
    source.write_text("Synthetic discovered source.")
    exports = tmp_path / "exports"
    exports.mkdir()
    try:
        os.link(source, exports / "alias.txt")
    except OSError as exc:
        pytest.skip(f"Hard links unavailable: {exc}")
    assert inspect(tmp_path)["artifacts"][0]["downloadable"] is False
    with pytest.raises(ValueError):
        module.project_artifact_path(tmp_path, "alias.txt")


def test_unknown_or_ambiguous_source_selection_blocks_artifact_eligibility(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "report.txt").write_text("Synthetic generated output.")
    (tmp_path / "a.md").write_text("Synthetic candidate A.")
    (tmp_path / "b.md").write_text("Synthetic candidate B.")
    assert inspect(tmp_path)["artifacts"][0]["downloadable"] is False
    with pytest.raises(ValueError):
        module.project_artifact_path(tmp_path, "report.txt")
    monkeypatch.setattr(module, "MAX_SCANNED_ENTRIES", 2)
    assert roles(inspect(tmp_path))["manuscript"]["state"] == "unknown"
    with pytest.raises(ValueError):
        module.project_artifact_path(tmp_path, "report.txt")


def test_failed_source_discovery_keeps_overview_and_download_eligibility_aligned(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "report.txt").write_text("Synthetic output.")
    original = os.scandir

    def scandir(path):
        if Path(path) == tmp_path:
            raise PermissionError("Synthetic root discovery denied")
        return original(path)

    monkeypatch.setattr(os, "scandir", scandir)
    result = inspect(tmp_path)
    assert roles(result)["manuscript"]["state"] == "unreadable"
    assert roles(result)["manuscript"]["path"] is None
    assert result["artifacts"][0]["downloadable"] is False
    with pytest.raises(ValueError):
        module.project_artifact_path(tmp_path, "report.txt")


def test_known_unreadable_source_still_protects_aliases_without_blocking_other_outputs(tmp_path, monkeypatch):
    module = importlib.import_module("lixity.project_structure")
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source.")
    exports = tmp_path / "exports"
    exports.mkdir()
    report = exports / "report.txt"
    report.write_text("Synthetic generated output.")
    try:
        os.link(source, exports / "alias.txt")
    except OSError as exc:
        pytest.skip(f"Hard links unavailable: {exc}")
    original = os.access

    def access(path, mode, **kwargs):
        return False if Path(path) == source else original(path, mode, **kwargs)

    monkeypatch.setattr(os, "access", access)
    result = inspect(tmp_path)
    assert roles(result)["manuscript"]["state"] == "unreadable"
    assert roles(result)["manuscript"]["path"] == "manuscript.md"
    items = {item["name"]: item for item in result["artifacts"]}
    assert items["report.txt"]["downloadable"] is True
    assert items["alias.txt"]["downloadable"] is False
    assert module.project_artifact_path(tmp_path, "report.txt") == report.resolve()
    with pytest.raises(ValueError):
        module.project_artifact_path(tmp_path, "alias.txt")


def test_unreadable_inventory_is_not_reported_as_empty_healthy(tmp_path, monkeypatch):
    exports = tmp_path / "exports"
    exports.mkdir()
    original = os.scandir

    def scandir(path):
        if Path(path) == exports:
            raise PermissionError("Synthetic denied directory")
        return original(path)

    monkeypatch.setattr(os, "scandir", scandir)
    result = inspect(tmp_path)
    assert roles(result)["outputs"]["state"] == "unreadable"
    assert result["has_errors"] is True and "role-unreadable" in codes(result)


@pytest.mark.skipif(os.name == "nt", reason="POSIX undecodable byte filenames")
def test_undecodable_output_name_keeps_json_serializable(tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    descriptor = os.open(os.fsencode(exports) + b"/synthetic-\xff.txt", os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(descriptor)
    result = inspect(tmp_path)
    json.dumps(result, ensure_ascii=False).encode("utf-8")
    assert "artifact-name-invalid" in codes(result)
