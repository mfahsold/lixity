"""Synthetic source fidelity, conflict and recovery contracts."""
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import closing
from hashlib import sha256
from threading import Event

import pytest

from lixity.manuscript_editing import EditConflict, ManuscriptStore, analyze_manuscript_snapshot


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


@pytest.mark.parametrize("interruption", ["after_replace", "before_receipt"])
def test_interrupted_save_retry_records_exact_revision_pair(tmp_path, monkeypatch, interruption):
    from lixity.io import FileUtils

    original = b"\xef\xbb\xbf## Chapter\r\n\r\nThe gate shut.\r\n"
    editor, source = store(tmp_path, original)
    opened = editor.open()
    updated = opened["text"] + "The keeper turned quickly.\n"
    expected = original + b"The keeper turned quickly.\r\n"
    write = FileUtils.atomic_write_bytes_if_changed
    insert_snapshot = editor._insert_revision_snapshot

    def interrupted_write(*args, **kwargs):
        write(*args, **kwargs)
        raise OSError("interrupted after replacement")

    def interrupted_receipt(*args, **kwargs):
        insert_snapshot(*args, **kwargs)
        raise OSError("interrupted before receipt")

    with monkeypatch.context() as patch:
        if interruption == "after_replace":
            patch.setattr(FileUtils, "atomic_write_bytes_if_changed", interrupted_write)
        else:
            patch.setattr(editor, "_insert_revision_snapshot", interrupted_receipt)
        with pytest.raises(OSError, match="interrupted"):
            save(editor, opened, updated)

    assert source.read_bytes() == expected
    restarted = ManuscriptStore(tmp_path, source)
    assert restarted.recover("a" * 32)["text"] == updated
    assert restarted.recover(opened["revision"])["text"] == opened["text"]
    assert restarted.timeline() == []
    with pytest.raises(ValueError, match="reused"):
        save(restarted, {**opened, "revision": "0" * 64}, updated)
    result = save(restarted, opened, updated)
    assert source.read_bytes() == expected
    assert save(restarted, opened, updated) == result
    base, target = restarted.timeline()
    assert base["revision"] == opened["revision"]
    assert target["parent_revision"] == base["revision"]
    assert target["revision"] == result["revision"] == sha256(expected).hexdigest()
    assert base["created_at"] < target["created_at"]
    assert base["words"] == 3
    assert target["words"] == 7
    assert restarted.delta()["deltas"]["words"] == 4


def test_v2_pending_draft_retry_preserves_recovery_without_inventing_a_base(tmp_path):
    import sqlite3

    editor, source = store(tmp_path)
    opened = editor.open()
    updated = b"The keeper turned.\n"
    editor.directory.mkdir(parents=True)
    with closing(sqlite3.connect(editor.directory / "recovery.sqlite3")) as db, db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA user_version=2")
        db.execute(
            "CREATE TABLE recovery (document TEXT, id TEXT, kind TEXT, "
            "content BLOB, created REAL, PRIMARY KEY(document,id))"
        )
        db.executemany(
            "INSERT INTO recovery VALUES (?,?,?,?,?)",
            [
                (editor.document, opened["revision"], "version", source.read_bytes(), 1000.0),
                (editor.document, "a" * 32, "draft", updated, 1000.0),
            ],
        )
    source.write_bytes(updated)

    assert editor.recover("a" * 32)["text"] == updated.decode()
    with closing(sqlite3.connect(editor.directory / "recovery.sqlite3")) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    result = save(editor, opened, updated.decode())
    assert save(editor, opened, updated.decode()) == result
    assert editor.recover(opened["revision"])["text"] == opened["text"]
    assert source.read_bytes() == updated
    target, = editor.timeline()
    assert target["revision"] == result["revision"]
    assert target["parent_revision"] is None
    assert editor.delta()["has_baseline"] is False


@pytest.mark.parametrize("discard_base", [False, True])
def test_pending_base_is_retained_within_version_limit_until_explicitly_discarded(
    tmp_path, monkeypatch, discard_base,
):
    from lixity.io import FileUtils

    editor, source = store(tmp_path)
    opened = editor.open()
    updated = "A new draft.\n"
    write = FileUtils.atomic_write_bytes_if_changed

    def interrupted_write(*args, **kwargs):
        write(*args, **kwargs)
        raise OSError("interrupted after replacement")

    with monkeypatch.context() as patch:
        patch.setattr(FileUtils, "atomic_write_bytes_if_changed", interrupted_write)
        with pytest.raises(OSError, match="interrupted"):
            save(editor, opened, updated)

    # Subsequent edits measure an external branch while the earlier draft waits.
    source.write_bytes(b"An external branch.\n")
    for index in range(21):
        save(editor, editor.open(), f"A subsequent change {index}.\n", f"{index:032x}")
    versions = {row["id"] for row in editor.open()["recovery"] if row["kind"] == "version"}
    assert len(versions) == 20
    assert opened["revision"] in versions
    assert editor.recover(opened["revision"])["text"] == opened["text"]
    if discard_base:
        editor.discard(opened["revision"])

    source.write_bytes(updated.encode())
    result = save(editor, opened, updated)
    snapshots = {item["revision"]: item for item in editor.timeline()}
    target = snapshots[result["revision"]]
    if discard_base:
        assert target["parent_revision"] is None
        assert opened["revision"] not in snapshots
    else:
        assert target["parent_revision"] == opened["revision"]
        assert snapshots[opened["revision"]]["words"] == 2


def test_retry_that_replaces_the_source_uses_the_successful_save_time(tmp_path, monkeypatch):
    from lixity.io import FileUtils

    editor, source = store(tmp_path)
    opened = editor.open()
    original = source.read_bytes()
    now = 1000.0
    monkeypatch.setattr("lixity.manuscript_editing.time.time", lambda: now)

    def interrupted_write(*args, **kwargs):
        raise OSError("interrupted before replacement")

    with monkeypatch.context() as patch:
        patch.setattr(FileUtils, "atomic_write_bytes_if_changed", interrupted_write)
        with pytest.raises(OSError, match="interrupted"):
            save(editor, opened, "Later recovered draft.\n")

    now = 1001.0
    save(editor, opened, "Another successful save.\n", "b" * 32)
    source.write_bytes(original)
    now = 1002.0
    result = save(editor, opened, "Later recovered draft.\n")

    assert editor.timeline()[-1]["revision"] == result["revision"]
    assert editor.delta()["has_baseline"] is True


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


def test_pending_save_orders_writes_and_discards_without_blocking_readers(tmp_path, monkeypatch):
    editor, source = store(tmp_path)
    opened = editor.open()
    other = ManuscriptStore(tmp_path, source)
    measuring = Event()
    release = Event()
    measure = editor._measure_snapshot

    def held_measurement(*args):
        measuring.set()
        assert release.wait(timeout=5)
        return measure(*args)

    monkeypatch.setattr(editor, "_measure_snapshot", held_measurement)
    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(save, editor, opened, "First accepted edit.\n")
        try:
            assert measuring.wait(timeout=5)
            mid_save = pool.submit(other.open).result(timeout=2)
            assert mid_save["text"] == "First accepted edit.\n"
            second = pool.submit(save, other, mid_save, "Second accepted edit.\n", "b" * 32)
            discard = pool.submit(other.discard, "a" * 32)
            with pytest.raises(TimeoutError):
                second.result(timeout=0.1)
            with pytest.raises(TimeoutError):
                discard.result(timeout=0.1)
        finally:
            release.set()
        first_result = first.result(timeout=5)
        second_result = second.result(timeout=5)
        discard.result(timeout=5)

    with pytest.raises(ValueError, match="reused"):
        save(other, other.open(), "Different edit using an earlier operation.", "a" * 32)
    assert other.open()["text"] == "Second accepted edit.\n"
    base, first_snapshot, second_snapshot = other.timeline()
    assert base["revision"] == opened["revision"]
    assert first_snapshot["revision"] == first_result["revision"]
    assert first_snapshot["parent_revision"] == base["revision"]
    assert second_snapshot["revision"] == second_result["revision"]
    assert second_snapshot["parent_revision"] == first_snapshot["revision"]


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


@pytest.mark.parametrize(("initial", "sentences"), [
    ("# Manuscript\n\nShe said that a storm was coming.\n\n## Empty chapter\n", 1),
    ("## Only code\n\n```\nOnly excluded code.\n```\n", 0),
])
def test_revision_snapshot_keeps_unmeasurable_chapter_rates_unknown(tmp_path, initial, sentences):
    editor, _source = store(tmp_path, initial.encode())
    current = editor.delta()["current"]
    assert current["sentences"] == sentences
    assert current["chapter_metrics"] == []
    assert current["sticky_pct"] is None
    assert current["indirect_speech_per_1000"] is None

    opened = editor.open()
    save(editor, opened, "## Chapter\n\nMara waits.\n")
    history = editor.timeline()
    assert history[0]["sticky_pct"] is None
    assert history[0]["indirect_speech_per_1000"] is None
    assert history[1]["sticky_pct"] == 0.0
    assert history[1]["indirect_speech_per_1000"] == 0.0

    previous_method = sha256(b'{"language":"en","snapshot_method":"lixity-snapshot/1"}').hexdigest()
    with closing(editor._database()) as connection, connection:
        connection.execute(
            "UPDATE manuscript_revisions SET settings_sha256=?, sticky_pct=0, indirect_speech_per_1000=0 "
            "WHERE document=? AND revision=?", (previous_method, editor.document, opened["revision"]),
        )
    archived = editor.timeline()
    compared = editor.delta()
    assert compared["has_baseline"] is True
    for key in ("sticky_pct", "indirect_speech_per_1000"):
        assert archived[0][key] == 0.0
        assert compared["base"][key] is None
        assert compared["deltas"][key] is None
    assert editor.timeline() == archived


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

    from lixity.manuscript_editing import document_lock

    initial = "## Chapter 1\n\nThe river was quiet.\n"
    updated = "## Chapter 1\n\nThe river was loud and fast.\n"
    editor, source = store(tmp_path, initial.encode("utf-8"))
    opened = editor.open()
    lock = document_lock(source)

    calls: list[tuple[str, bool]] = []
    orig_analyze = editor.analyze_snapshot

    def spy_analyze(text: str):
        # Verify the document lock is NOT held by this thread during analysis
        acquired_by_other = [False]

        def probe():
            got = lock.acquire(blocking=False)
            if got:
                lock.release()
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


def test_document_lock_isolates_distinct_manuscripts(tmp_path):
    from lixity.manuscript_editing import document_lock

    first = tmp_path / "book-a.md"
    second = tmp_path / "book-b.md"
    first_alias = tmp_path / "." / "book-a.md"
    assert document_lock(first) is document_lock(first_alias)
    assert document_lock(first) is not document_lock(second)


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


@pytest.mark.parametrize(("newline", "raw_chars", "clean_chars"), [("\n", 163, 81), ("\r\n", 176, 90)])
def test_snapshot_keeps_legacy_whitespace_counts_for_markdown_and_custom_headings(newline, raw_chars, clean_chars):
    from lixity.analyzer import CorpusAnalyzer
    from lixity.models import CorpusConfig

    source = (
        "## Title\n\nCHAPTER THE TRACK\nFirst sentence.<!-- don't count this -->\n"
        "Second sentence.\n\n```txt\n## Hidden example\nCHAPTER CODE\nSample code text.\n```\n\n"
        "END NOTES\nEverything after the appendix."
    ).replace("\n", newline)
    config = CorpusConfig(language="en", chapter_regex=r"(?m)^CHAPTER [^\r\n]+$", appendix_marker="END NOTES")
    metrics = CorpusAnalyzer(config).analyze_text(source)
    snapshot = analyze_manuscript_snapshot(source, config=config)
    assert (metrics.raw_words, metrics.raw_chars) == (25, raw_chars)
    assert (metrics.clean_words, metrics.clean_chars, metrics.tokens) == (11, clean_chars, 4)
    assert snapshot["words"] == 11


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


def test_recovery_db_enforces_wal_trusted_schema_and_skips_read_ddl(tmp_path, monkeypatch):
    import sqlite3
    from contextlib import closing

    editor, _source = store(tmp_path, b"## Chapter 1\n\nThe river was quiet.\n")
    opened = editor.open()
    save(editor, opened, "## Chapter 1\n\nThe river was loud.\n", "1" * 32)
    db_path = editor.directory / "recovery.sqlite3"
    with closing(sqlite3.connect(db_path)) as conn:
        assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) >= 1

    fresh = ManuscriptStore(tmp_path, editor.source)
    opened_conns = []
    real_connect = sqlite3.connect

    class SpyConnection:
        def __init__(self, inner):
            self._inner = inner
            self.statements = []
            self.commits = 0

        def execute(self, sql, *args, **kwargs):
            self.statements.append(sql)
            return self._inner.execute(sql, *args, **kwargs)

        def commit(self):
            self.commits += 1
            return self._inner.commit()

        def close(self):
            return self._inner.close()

        def __setattr__(self, name, value):
            if name in ("_inner", "statements", "commits"):
                super().__setattr__(name, value)
            else:
                setattr(self._inner, name, value)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __enter__(self):
            self._inner.__enter__()
            return self

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

    def tracking_connect(*args, **kwargs):
        spy = SpyConnection(real_connect(*args, **kwargs))
        opened_conns.append(spy)
        return spy

    monkeypatch.setattr("lixity.manuscript_editing.sqlite3.connect", tracking_connect)
    assert fresh.open()["recovery"] != []
    assert len(fresh.timeline()) == 2
    assert fresh.delta()["has_baseline"] is True
    assert fresh._recorded_revision(opened["revision"]) is not None
    # One connection per read call (including one shared connection in delta())
    assert len(opened_conns) == 4
    for spy in opened_conns:
        assert "PRAGMA trusted_schema=OFF" in spy.statements
        assert spy.commits == 0
        assert not any(stmt.lstrip().startswith(("CREATE ", "ALTER ", "DROP ")) for stmt in spy.statements)


def test_compare_measures_base_current_and_draft_with_project_config(tmp_path):
    source = tmp_path / "book.md"
    base_text = "## Chapter 1\n\nDr. Vale waits. She turns.\n"
    source.write_text(base_text, encoding="utf-8")
    cfg = {"short_sentence_max": 2, "sticky_max_words": 6, "language": "en"}
    editor = ManuscriptStore(tmp_path, source, language="en", project_config=cfg)
    result = editor.compare(
        revision=editor.open()["revision"],
        base_text=base_text,
        draft_text="## Chapter 1\n\nDr. Vale waits. She turns. A long sentence runs past two words carefully.\n",
    )
    measurements = result["measurements"]
    assert measurements["base"]["asl"] == 2.5
    assert measurements["current"]["asl"] == 2.5
    assert result["settings_sha256"]
    assert measurements["draft"]["asl"] > 2.5
    assert result["base_to_current"]["deltas"]["asl"] == 0.0
    assert result["current_to_draft"]["chapter_matching"]["clear"] is True
    assert result["primary_diff"] == "current_to_draft"
    assert result["current_to_draft"]["chapter_matching"]["changed"] == 1
    assert result["current_to_draft"]["chapter_deltas"][0]["changed"] is True
    assert result["base_to_current"]["chapter_matching"]["changed"] == 0
    assert result["base_to_current"]["chapter_deltas"][0]["changed"] is False


def test_compare_uses_one_detected_language_and_does_not_create_history(tmp_path):
    from lixity.language import detect_language
    from lixity.manuscript_editing import analyze_manuscript_snapshot, compare_texts

    source = tmp_path / "book.md"
    current = "Der Mann und die Frau sind in dem Haus, weil sie auf den Regen warten."
    draft = "It was only a matter of time before the door that he had opened would close."
    assert detect_language(current) == "de"
    assert detect_language(draft) == "en"
    original = b"\xef\xbb\xbf" + (current + "\r\n").encode()
    source.write_bytes(original)
    config = {"sticky_glue_pct": 45.0, "sticky_min_words": 2}
    editor = ManuscriptStore(tmp_path, source, language="auto", project_config=config)
    opened = editor.open()
    compared = editor.compare(revision=opened["revision"], base_text=draft, draft_text=draft)
    expected = analyze_manuscript_snapshot(draft, language="de", project_config=config)
    independently_detected = analyze_manuscript_snapshot(draft, language="auto", project_config=config)
    assert expected["sticky_pct"] != independently_detected["sticky_pct"]
    assert compared["measurements"]["draft"]["sticky_pct"] == expected["sticky_pct"]
    assert compared["measurements"]["base"] == compared["measurements"]["draft"]
    assert compared["measurements"]["current"]["revision"] == opened["revision"]
    assert compare_texts(draft, current, language="auto", project_config=config)["base"]["sticky_pct"] == expected["sticky_pct"]
    assert source.read_bytes() == original
    assert not editor.directory.exists()


def test_unrelated_inserted_chapter_does_not_inherit_a_previous_title_match(tmp_path):
    source = tmp_path / "book.md"
    base = "## Arrival\n\nClara crossed the square, carrying letters wrapped in linen.\n\n## Departure\n\nShe waited under dusky trees by the old stone gate."
    draft = (
        "## Arrival\n\nHana crossed the square, carrying letters wrapped in linen.\n\n"
        "## Prologue\n\nGolden orchards neighbored pastures scattered across distant hills.\n\n"
        "## Departure\n\nShe waited under dusky trees by the old stone gate."
    )
    source.write_text(base)
    editor = ManuscriptStore(tmp_path, source)
    result = editor.compare(revision=editor.open()["revision"], base_text=base, draft_text=draft)
    chapters = result["current_to_draft"]["chapter_deltas"]
    assert [c["match_status"] for c in chapters] == ["ambiguous", "ambiguous", "matched"]
    assert chapters[0]["words_delta"] is None
    assert chapters[0]["asl_delta"] is None


def test_resaving_with_changed_settings_keeps_archived_measurements_immutable(tmp_path):
    initial = "## Chapter\n\nShe waited.\n\nCUT HERE\n\nSeveral optional words follow.\n"
    editor, source = store(tmp_path, initial.encode())
    opened = editor.open()
    saved = save(editor, opened, initial + "Extra words here.\n")
    archived = editor.timeline()
    revised = ManuscriptStore(tmp_path, source, project_config={"appendix_marker": "CUT HERE"})
    assert revised.analyze_snapshot(source.read_text())["words"] < archived[-1]["words"]
    save(revised, revised.open(), source.read_text(), "b" * 32)
    assert revised.timeline() == archived
    delta = revised.delta()
    assert delta["has_baseline"] is True
    assert delta["deltas"]["words"] == 0
    assert delta["current"]["revision"] == saved["revision"]


def test_delta_recomputes_auto_language_from_target_or_withholds_unverifiable_history(tmp_path):
    source = tmp_path / "book.md"
    initial = "It was only a matter of time before the door that he had opened would close."
    current = "Der Mann und die Frau sind in dem Haus, weil sie auf den Regen warten."
    source.write_text(initial)
    config = {"sticky_glue_pct": 45.0, "sticky_min_words": 2}
    auto = ManuscriptStore(tmp_path, source, language="auto", project_config=config)
    opened = auto.open()
    saved = save(auto, opened, current)
    history = auto.timeline()
    assert history[0]["sticky_pct"] == 100.0
    delta = auto.delta(base_revision=opened["revision"], target_revision=saved["revision"])
    assert delta["has_baseline"] is True
    assert delta["base"]["sticky_pct"] == 0.0
    assert auto.timeline() == history
    auto.discard(opened["revision"])
    unavailable = auto.delta()
    assert unavailable["has_baseline"] is False
    assert unavailable["deltas"] is None
    assert unavailable["current"]["revision"] == saved["revision"]


def test_legacy_row_without_provenance_or_text_does_not_imply_a_comparable_baseline(tmp_path):
    editor, _source = store(tmp_path)
    opened = editor.open()
    save(editor, opened, "Someone walked across the square.")
    with closing(editor._database()) as connection, connection:
        connection.execute(
            "UPDATE manuscript_revisions SET settings_sha256=NULL WHERE document=? AND revision=?",
            (editor.document, opened["revision"]),
        )
    assert editor.delta()["has_baseline"] is True  # The original text is retained and can be remeasured.
    editor.discard(opened["revision"])
    assert editor.delta()["deltas"] is None


def test_delta_remeasures_retained_snapshots_cut_by_the_previous_appendix_policy(tmp_path):
    previous_method = sha256(b'{"language":"en","snapshot_method":"lixity-snapshot/1"}').hexdigest()
    original = "## One\n\nRain falls.\n\n<!-- ## Anmerkungen und Literaturverzeichnis -->\n\n## Two\n\nRain stays.\n"
    editor, _source = store(tmp_path, original.encode())
    opened = editor.open()
    save(editor, opened, original + "It also hails.\n")
    with closing(editor._database()) as connection, connection:
        connection.execute(
            "UPDATE manuscript_revisions SET settings_sha256=?, sentences=1 WHERE document=? AND revision=?",
            (previous_method, editor.document, opened["revision"]),
        )
    archive = editor.timeline()
    assert archive[0]["sentences"] == 1
    compared = editor.delta()
    assert compared["has_baseline"] is True
    assert compared["base"]["sentences"] == 2
    assert compared["deltas"]["sentences"] == 1
    assert editor.timeline() == archive

    editor.discard(opened["revision"])
    unavailable = editor.delta()
    assert unavailable["has_baseline"] is False
    assert unavailable["deltas"] is None
    assert editor.timeline() == archive


def test_snapshot_dialogue_stops_at_chapters_and_counts_only_scope_words():
    chapter_break = '## One\n\n“She waits.\n\n## Two\n\nHe rests.”'
    snap = analyze_manuscript_snapshot(chapter_break)
    assert snap["dialogue_ratio"] == 0.0
    assert [chapter["dialog_pct"] for chapter in snap["chapter_metrics"]] == [0.0, 0.0]

    custom_words = {"word_regex": r"^(\w+)"}
    detached = '## One\n\nShe said, "Come." He said, "Rest."'
    snap = analyze_manuscript_snapshot(detached, project_config=custom_words)
    assert snap["dialogue_ratio"] == 0.0
    assert snap["chapter_metrics"][0]["dialog_pct"] == 0.0


def test_snapshot_indirect_speech_suppresses_unresolved_quotation_context():
    prose = analyze_manuscript_snapshot("## One\n\nShe said that Mara had left.")
    unclear = analyze_manuscript_snapshot("## One\n\n“She said that Mara had left.")
    assert prose["indirect_speech_per_1000"] > 0.0
    assert unclear["indirect_speech_per_1000"] == 0.0


def test_delta_remeasures_both_retained_quotation_snapshots_with_current_method(tmp_path):
    source = tmp_path / "book.md"
    original = '## One\n\nShe said, "Come." He said, "Rest."'
    source.write_text(original, encoding="utf-8")
    settings = {"word_regex": r'^"?(\w+)'}
    editor = ManuscriptStore(tmp_path, source, project_config=settings)
    base = editor.open()
    target = save(editor, base, '## One\n\n"Stay." She said, "Wait."')
    save(editor, target, "## One\n\nThe light faded.", "b" * 32)

    older_settings = {**settings, "language": "en", "snapshot_method": "lixity-snapshot/2"}
    previous_method = sha256(json.dumps(older_settings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with closing(editor._database()) as connection, connection:
        connection.execute(
            "UPDATE manuscript_revisions SET settings_sha256=?, dialogue_ratio=200 "
            "WHERE document=? AND revision IN (?, ?)",
            (previous_method, editor.document, base["revision"], target["revision"]),
        )
    archive = editor.timeline()
    assert [row["dialogue_ratio"] for row in archive[:2]] == [200.0, 200.0]

    compared = editor.delta(base_revision=base["revision"], target_revision=target["revision"])
    assert compared["has_baseline"] is True
    assert compared["base"]["dialogue_ratio"] == 0.0
    assert compared["current"]["dialogue_ratio"] == 100.0
    assert compared["deltas"]["dialogue_ratio"] == 100.0
    assert compared["base"]["created_at"] == archive[0]["created_at"]
    assert compared["current"]["created_at"] == archive[1]["created_at"]
    assert editor.timeline() == archive

    editor.discard(target["revision"])
    unavailable = editor.delta(base_revision=base["revision"], target_revision=target["revision"])
    assert unavailable["has_baseline"] is False
    assert unavailable["deltas"] is None
    assert editor.timeline() == archive


def test_delta_withholds_ambiguous_chapters_and_matches_renumbered_content(tmp_path):
    source = tmp_path / "book.md"
    old_ch1 = "Lanterns flickered above the harbour wall as waves struck the stone stairs again."
    old_ch2 = "Clara locked the cedar drawer and listened to footsteps along the gravel drive."
    source.write_text(f"## One\n\n{old_ch1}\n\n## Two\n\n{old_ch2}\n", encoding="utf-8")
    editor = ManuscriptStore(tmp_path, source)
    opened = editor.open()
    # Renumbered after inserting a new prologue: unique content matches Ch1 -> Ch2 and Ch2 -> Ch3.
    renumbered = (
        "## Prologue\n\nThunder rolled across the empty square before dawn.\n\n"
        f"## Two\n\n{old_ch1}\n\n## Three\n\n{old_ch2}\n"
    )
    save(editor, opened, renumbered, "c" * 32)
    delta = editor.delta()
    assert [c["match_status"] for c in delta["chapter_deltas"]] == ["unmatched", "matched", "matched"]
    assert delta["chapter_deltas"][0]["words_delta"] is None
    assert delta["chapter_deltas"][1]["base_title"] == "One"
    assert delta["chapter_deltas"][1]["words_delta"] == 0
    assert delta["chapter_matching"]["unmatched"] == 1
    assert delta["chapter_matching"]["clear"] is True

    # Identical generic chapters make correspondence ambiguous -> deltas withheld.
    source_amb = tmp_path / "amb.md"
    source_amb.write_text("## Chapter\n\nSame words here.\n\n## Chapter\n\nSame words here.\n", encoding="utf-8")
    amb_editor = ManuscriptStore(tmp_path, source_amb)
    amb_open = amb_editor.open()
    save(
        amb_editor,
        amb_open,
        "## Chapter\n\nSame words here.\n\n## Chapter\n\nDifferent words entirely.\n",
        "d" * 32,
    )
    amb_delta = amb_editor.delta()
    assert any(
        c["match_status"] in {"ambiguous", "unmatched"} and c["words_delta"] is None
        for c in amb_delta["chapter_deltas"]
    )
    assert amb_delta["chapter_matching"]["clear"] is False
