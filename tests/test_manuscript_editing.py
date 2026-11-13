"""Synthetic source fidelity, conflict and recovery contracts."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from lixity.manuscript_editing import EditConflict, ManuscriptStore


def store(tmp_path, content=b"# Chapter\n\nSynthetic prose.\n"):
    source = tmp_path / "book.md"
    source.write_bytes(content)
    return ManuscriptStore(tmp_path, source), source


def save(editor, opened, text, operation="a" * 32):
    return editor.save(opened["document"], opened["revision"], operation, text)


def test_noop_and_edit_preserve_bom_crlf(tmp_path):
    original = b"\xef\xbb\xbf# Chapter\r\n\r\nProse.\r\n"
    editor, source = store(tmp_path, original)
    opened = editor.open()
    save(editor, opened, opened["text"])
    assert source.read_bytes() == original
    result = save(editor, opened, opened["text"] + "More.\n", "b" * 32)
    assert source.read_bytes() == original + b"More.\r\n"
    assert result["revision"] != opened["revision"]


def test_conflict_keeps_external_source_and_recovers_draft_after_restart(tmp_path):
    editor, source = store(tmp_path)
    opened = editor.open()
    source.write_text("External version", encoding="utf-8")
    with pytest.raises(EditConflict):
        save(editor, opened, "My draft")
    restarted = ManuscriptStore(tmp_path, source)
    recovery = restarted.open()["recovery"]
    assert source.read_text() == "External version"
    assert restarted.recover(recovery[0]["id"])["text"] == "My draft"


def test_lost_ack_retry_and_reused_operation(tmp_path):
    editor, source = store(tmp_path)
    opened = editor.open()
    first = save(editor, opened, "Updated")
    assert save(editor, opened, "Updated") == first
    with pytest.raises(ValueError):
        save(editor, opened, "Different")
    assert source.read_text() == "Updated"


def test_failure_retains_original_and_pending_draft(tmp_path, monkeypatch):
    editor, source = store(tmp_path)
    opened = editor.open()
    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr("lixity.manuscript_editing.FileUtils.atomic_write_bytes_if_changed", fail)
    with pytest.raises(OSError):
        save(editor, opened, "Unsaved work")
    assert source.read_text() == opened["text"]
    pending = next(row for row in editor.open()["recovery"] if row["kind"] == "draft")
    assert editor.recover(pending["id"])["text"] == "Unsaved work"


@pytest.mark.parametrize("content", [b"bad\xff", b"one\r\ntwo\n", b"a\x00b"])
def test_unsupported_source_is_not_rewritten(tmp_path, content):
    editor, source = store(tmp_path, content)
    with pytest.raises(ValueError):
        editor.open()
    assert source.read_bytes() == content


def test_document_binding_and_recovery_path_validation(tmp_path):
    editor, source = store(tmp_path)
    opened = editor.open()
    with pytest.raises(ValueError):
        editor.save("wrong", opened["revision"], "a" * 32, "No")
    with pytest.raises(ValueError):
        editor.recover("../../book.md")
    assert source.read_text() == opened["text"]


def test_two_tabs_only_one_wins(tmp_path):
    editor, source = store(tmp_path)
    opened = editor.open()
    def attempt(number):
        try:
            save(editor, opened, str(number), str(number) * 32)
            return True
        except EditConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [1, 2])) == [False, True]
    assert source.read_text() in ("1", "2")


def test_original_version_recoverable_without_overwriting_current(tmp_path):
    editor, source = store(tmp_path)
    opened = editor.open()
    save(editor, opened, "New text")
    row = next(row for row in editor.open()["recovery"] if row["kind"] == "version")
    assert editor.recover(row["id"])["text"] == opened["text"]
    assert source.read_text() == "New text"


def test_large_manuscript_save_and_recovery(tmp_path):
    text = "Synthetic river morning words " * 75000
    editor, source = store(tmp_path, text.encode())
    opened = editor.open()
    save(editor, opened, text + "End.")
    assert source.read_text() == text + "End."
    version = next(row for row in editor.open()["recovery"] if row["kind"] == "version")
    assert editor.recover(version["id"])["text"] == text


def test_replacement_guard_preserves_late_external_change(tmp_path, monkeypatch):
    from lixity.io import FileUtils
    editor, source = store(tmp_path)
    opened = editor.open()
    original_write = FileUtils.atomic_write_bytes_if_changed
    def raced_write(*args, **kwargs):
        source.write_text("Late external edit")
        return original_write(*args, **kwargs)
    monkeypatch.setattr(FileUtils, "atomic_write_bytes_if_changed", raced_write)
    with pytest.raises(EditConflict):
        save(editor, opened, "My draft")
    assert source.read_text() == "Late external edit"


def test_recovery_directory_symlink_is_rejected(tmp_path):
    editor, _source = store(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / ".lixity").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(ValueError):
        save(editor, editor.open(), "Do not write")
    assert list(elsewhere.iterdir()) == []


def test_drafts_are_not_silently_evicted(tmp_path):
    editor, source = store(tmp_path)
    opened = editor.open()
    source.write_text("External")
    for number in range(8):
        with pytest.raises(EditConflict):
            save(editor, opened, f"Draft {number}", f"{number:032x}")
    with pytest.raises(ValueError, match="Eight recovery"):
        save(editor, opened, "Ninth", "f" * 32)
    assert len(editor.open()["recovery"]) == 8
    editor.discard("0" * 32)
    with pytest.raises(EditConflict):
        save(editor, opened, "Ninth", "f" * 32)


def test_recovery_is_bound_to_document_content_and_kind(tmp_path):
    import hashlib
    editor, _source = store(tmp_path, b"\xef\xbb\xbfOriginal\r\n")
    opened = editor.open()
    save(editor, opened, "Next\n")
    entry = next(row for row in editor.open()["recovery"] if row["kind"] == "version")
    recovered = editor.recover(entry["id"])
    assert recovered["document"] == opened["document"]
    assert recovered["revision"] == hashlib.sha256(b"\xef\xbb\xbfOriginal\r\n").hexdigest()
    assert recovered["kind"] == "version"
    assert recovered["id"] == entry["id"]
    assert recovered["text"] == "Original\n"


def test_missing_recovery_read_does_not_create_storage(tmp_path):
    editor, _source = store(tmp_path)
    with pytest.raises(ValueError, match="unavailable"):
        editor.recover("a" * 32)
    assert not editor.directory.exists()


def test_timeline_and_delta_record_revisions_on_save(tmp_path):
    initial = "## Chapter 1\n\nShe walked slowly down the quiet street. It was raining.\n"
    editor, _source = store(tmp_path, initial.encode("utf-8"))
    assert editor.timeline() == []
    pre_delta = editor.delta()
    assert pre_delta["has_baseline"] is False
    assert pre_delta["deltas"] is None
    assert pre_delta["current"]["words"] > 0

    opened = editor.open()
    updated = (
        "## Chapter 1\n\n"
        "She walked fast. \"Wait!\" he called.\n\n"
        "## Chapter 2\n\nNew scene begins here.\n"
    )
    saved = save(editor, opened, updated, "1" * 32)
    history = editor.timeline()
    assert len(history) == 2
    assert history[0]["revision"] == opened["revision"]
    assert history[1]["revision"] == saved["revision"]
    assert history[1]["parent_revision"] == opened["revision"]
    assert len(history[1]["chapter_metrics"]) == 2

    delta = editor.delta()
    assert delta["schema_version"] == "lixity-timeline/1"
    assert delta["has_baseline"] is True
    assert delta["revisions_count"] == 2
    assert delta["deltas"]["words"] == history[1]["words"] - history[0]["words"]
    assert delta["deltas"]["dialogue_ratio"] > 0
    assert len(delta["chapter_deltas"]) == 2


def test_timeline_sparse_empty_text_reports_null_metrics(tmp_path):
    editor, _source = store(tmp_path, b"Hello world.\n")
    opened = editor.open()
    save(editor, opened, "", "2" * 32)
    delta = editor.delta()
    assert delta["has_baseline"] is True
    assert delta["current"]["words"] == 0
    assert delta["current"]["asl"] is None
    assert delta["current"]["dialogue_ratio"] is None
    assert delta["deltas"]["asl"] is None
    assert delta["deltas"]["dialogue_ratio"] is None


def test_delta_rejects_invalid_revision_identifiers(tmp_path):
    editor, _source = store(tmp_path, b"Hello world.\n")
    with pytest.raises(ValueError, match="Invalid base"):
        editor.delta(base_revision="not-hex")
    with pytest.raises(ValueError, match="Invalid target"):
        editor.delta(target_revision="not-hex")


def test_editing_timeline_routes_registered():
    from lixity.server.handler import LixityServerHandler

    assert LixityServerHandler.GET_ROUTES["/api/manuscript-timeline"] == "_handle_editor_timeline"
    assert LixityServerHandler.GET_ROUTES["/api/manuscript-delta"] == "_handle_editor_delta"
