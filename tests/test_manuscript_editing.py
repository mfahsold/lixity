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


def test_delta_uses_current_source_after_reverting_to_recorded_content(tmp_path):
    initial = "## Chapter\n\nThe river was quiet.\n"
    editor, _source = store(tmp_path, initial.encode())
    opened = editor.open()
    changed = save(editor, opened, initial + "The bird sang.\n")
    history = editor.timeline()
    reverted = save(editor, changed, initial, "b" * 32)

    delta = editor.delta()
    assert delta["current"]["revision"] == reverted["revision"] == opened["revision"]
    assert delta["current"] == history[0]
    assert delta["has_baseline"] is False
    assert delta["deltas"] is None
    assert editor.timeline() == history
    reviewed = editor.delta(base_revision=changed["revision"])
    assert reviewed["deltas"]["words"] == -3
    assert reviewed["current"] == history[0]
    assert reviewed["base"] == history[1]


@pytest.mark.parametrize("with_history", [False, True])
def test_delta_observes_external_current_without_recording_it(tmp_path, with_history):
    import hashlib

    editor, source = store(tmp_path)
    if with_history:
        save(editor, editor.open(), "A saved synthetic paragraph.\n")
    history = editor.timeline()
    external = b"The river was quiet.\n"
    source.write_bytes(external)

    delta = editor.delta()
    assert delta["current"]["revision"] == hashlib.sha256(external).hexdigest()
    assert delta["current"]["words"] == 4
    assert delta["current"]["created_at"] is None
    assert delta["has_baseline"] is False
    assert delta["deltas"] is None
    assert editor.timeline() == history
    assert editor.directory.exists() is with_history


def test_delta_binds_current_metrics_and_digest_to_one_source_read(tmp_path, monkeypatch):
    import hashlib

    original = b"The river was quiet.\n"
    editor, source = store(tmp_path, original)
    read = editor._read

    def changed_after_read():
        captured = read()
        source.write_bytes(b"External replacement after the captured snapshot.\n")
        return captured

    monkeypatch.setattr(editor, "_read", changed_after_read)
    delta = editor.delta()
    assert delta["current"]["words"] == 4
    assert delta["current"]["revision"] == hashlib.sha256(original).hexdigest()


def test_explicit_delta_uses_retained_target_without_reading_current_source(tmp_path):
    editor, source = store(tmp_path, b"The river was quiet.\n")
    opened = editor.open()
    saved = save(editor, opened, "The bird sang.\n")
    source.unlink()

    historical = editor.delta(base_revision=opened["revision"], target_revision=saved["revision"])
    assert historical["current"]["revision"] == saved["revision"]
    assert historical["deltas"]["words"] == -1
    with pytest.raises(FileNotFoundError):
        editor.delta()


def test_delta_resolves_retained_revisions_outside_the_timeline_window(tmp_path):
    editor, _source = store(tmp_path)
    opened = editor.open()
    current = opened
    first = None
    for number in range(102):
        current = save(editor, current, f"Version {number} has synthetic prose.\n", f"{number:032x}")
        if number == 0:
            first = editor.timeline()[1]
    assert first is not None
    reverted = save(editor, current, opened["text"], "f" * 32)
    history = editor.timeline(limit=100)
    assert len(history) == 100
    assert opened["revision"] not in {row["revision"] for row in history}

    delta = editor.delta()
    assert delta["revisions_count"] == 100
    assert delta["current"]["revision"] == reverted["revision"] == opened["revision"]
    assert delta["has_baseline"] is False
    reviewed = editor.delta(base_revision=first["revision"], target_revision=opened["revision"])
    assert reviewed["base"] == first
    assert reviewed["deltas"]["words"] == -3
    assert editor.timeline(limit=100) == history


@pytest.mark.parametrize("with_history", [False, True])
@pytest.mark.parametrize("parameter, error", [("base_revision", "Base"), ("target_revision", "Target")])
def test_delta_rejects_unrecorded_explicit_revisions(tmp_path, with_history, parameter, error):
    editor, _source = store(tmp_path)
    if with_history:
        save(editor, editor.open(), "A saved synthetic paragraph.\n")
    with pytest.raises(ValueError, match=error + " revision not found"):
        editor.delta(**{parameter: "f" * 64})


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


def test_save_analyzes_snapshots_outside_write_lock_and_skips_reanalysis_on_aba(tmp_path, monkeypatch):
    import threading

    from lixity.manuscript_editing import SOURCE_WRITE_LOCK

    initial = "## Chapter 1\n\nThe river was quiet.\n"
    updated = "## Chapter 1\n\nThe river was loud and fast.\n"
    editor, _source = store(tmp_path, initial.encode("utf-8"))
    opened = editor.open()

    calls: list[tuple[str, bool]] = []
    orig_analyze = editor.analyze_snapshot

    def spy_analyze(text: str):
        # Verify SOURCE_WRITE_LOCK is NOT held by this thread during analysis
        acquired_by_other = [False]

        def probe():
            got = SOURCE_WRITE_LOCK.acquire(blocking=False)
            if got:
                SOURCE_WRITE_LOCK.release()
            acquired_by_other[0] = got

        t = threading.Thread(target=probe)
        t.start()
        t.join()
        calls.append((text, acquired_by_other[0]))
        return orig_analyze(text)

    monkeypatch.setattr(editor, "analyze_snapshot", spy_analyze)

    saved_b = save(editor, opened, updated, "1" * 32)
    assert len(calls) == 2
    assert all(lock_free for _, lock_free in calls)

    calls.clear()
    reverted_a = save(editor, saved_b, initial, "2" * 32)
    assert reverted_a["revision"] == opened["revision"]
    assert calls == []
    assert [row["revision"] for row in editor.timeline()] == [opened["revision"], saved_b["revision"]]


def test_snapshot_matches_full_pipeline_and_unknown_semantics(tmp_path):
    from lixity.analyzer import CorpusAnalyzer
    from lixity.dialogue import dialogue_report
    from lixity.manuscript_editing import analyze_manuscript_snapshot
    from lixity.models import CorpusConfig
    from lixity.pacing import pacing_report

    text = (
        "## Chapter 1\n\n"
        "She said that the train had already departed. "
        "\"Wait!\" he called across the platform.\n\n"
        "---\n\n"
        "It was a very quiet and very long day in the old house by the hill "
        "where they had been waiting for the letter to arrive.\n\n"
        "## Chapter 2\n\n"
        "Rain fell softly.\n"
    )
    cfg = CorpusConfig(language="en")
    metrics = CorpusAnalyzer(cfg, sample_text=text).analyze_text(text)
    pacing = pacing_report(text, cfg)
    dialogue = dialogue_report(text, cfg)
    snap = analyze_manuscript_snapshot(text, language="en")

    assert snap["words"] == metrics.clean_words
    assert snap["sentences"] == metrics.total_sentences
    assert snap["asl"] == round(float(metrics.asl), 3)
    assert snap["asl_cv"] == round(float(metrics.sentence_cv), 4)
    assert snap["dialogue_ratio"] == round(float(metrics.dialog_ratio), 3)
    assert snap["mattr"] == (round(float(metrics.mattr), 4) if metrics.mattr is not None else None)
    assert snap["length_entropy"] == round(float(pacing.rhythm_profile["length_entropy"]), 4)
    assert snap["sticky_pct"] == round(float(pacing.sticky_sentence_pct), 2)
    assert snap["indirect_speech_per_1000"] == round(float(dialogue.indirect_speech_per_1000), 2)
    assert snap["flags_count"] is None
    assert len(snap["chapter_metrics"]) == 2

    # Generic language lacks indirect speech and function-word lexicons -> None, not 0.0
    generic_snap = analyze_manuscript_snapshot(text, language="generic")
    assert generic_snap["words"] > 0
    assert generic_snap["indirect_speech_per_1000"] is None
    assert generic_snap["sticky_pct"] is None
    assert generic_snap["flags_count"] is None


def test_flags_count_migration_from_not_null_zero_to_nullable(tmp_path):
    import sqlite3
    from contextlib import closing

    initial = "## Chapter 1\n\nThe river was quiet.\n"
    updated = "## Chapter 1\n\nThe river was loud.\n"
    ms_path = tmp_path / "book.md"
    ms_path.write_text(initial, encoding="utf-8")
    db_dir = tmp_path / ".lixity" / "editing"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "recovery.sqlite3"
    editor = ManuscriptStore(tmp_path, ms_path)

    with closing(sqlite3.connect(db_path)) as db:
        db.execute(
            "CREATE TABLE manuscript_revisions ("
            "document TEXT NOT NULL, revision TEXT NOT NULL, parent_revision TEXT, "
            "created_at REAL NOT NULL, words INTEGER NOT NULL, sentences INTEGER NOT NULL, "
            "asl REAL, asl_cv REAL, dialogue_ratio REAL, mattr REAL, "
            "length_entropy REAL, sticky_pct REAL, indirect_speech_per_1000 REAL, "
            "flags_count INTEGER NOT NULL DEFAULT 0, chapter_metrics TEXT NOT NULL DEFAULT '[]', "
            "PRIMARY KEY(document, revision))"
        )
        db.execute(
            "INSERT INTO manuscript_revisions "
            "(document, revision, parent_revision, created_at, words, sentences, flags_count, chapter_metrics) "
            "VALUES (?, ?, NULL, 1000.0, 4, 1, 0, '[]')",
            (editor.document, "0" * 64),
        )
        db.commit()

    opened = editor.open()
    save(editor, opened, updated, "a" * 32)
    history = editor.timeline()
    assert all(row["flags_count"] is None for row in history)
    delta = editor.delta()
    assert delta["current"]["flags_count"] is None
    assert delta["deltas"]["flags_count"] is None
