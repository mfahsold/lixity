"""Convenient direction entry keeps existing optimistic-write safeguards."""

import json

from lixity.cli import main


def test_add_direction_from_chapter_and_line_without_exposing_hashes(tmp_path, capsys):
    manuscript = tmp_path / "draft.md"
    manuscript.write_text("## One\n\nFirst paragraph.\n\nSecond paragraph.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('language = "en"\nmanuscript = "draft.md"\n', encoding="utf-8")
    original = manuscript.read_bytes()
    args = ["audio-direction", "add", "--project", str(tmp_path), "--chapter", "1", "--line", "5",
            "--instruction", "Quietly.", "--pause-after", "0.4"]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["directions"]) == 1
    assert result["directions"][0]["anchor"]["start_line"] == 5
    assert result["directions"][0]["instructions"] == "Quietly."
    assert result["directions"][0]["pause_after"] == 0.4
    assert manuscript.read_bytes() == original
    assert main(args) != 0
    assert "already" in capsys.readouterr().out.lower()


def test_add_direction_rejects_unmatched_line_without_writing(tmp_path, capsys):
    (tmp_path / "draft.md").write_text("## One\n\nFirst paragraph.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('language = "en"\nmanuscript = "draft.md"\n', encoding="utf-8")
    assert main(["audio-direction", "add", "--project", str(tmp_path), "--chapter", "1", "--line", "2",
                 "--instruction", "Quietly."]) != 0
    assert "passage" in capsys.readouterr().out.lower()
    assert not (tmp_path / ".lixity" / "audio-directions.json").exists()


def test_add_checks_overlaps_and_preserves_existing_directions(tmp_path, capsys):
    (tmp_path / "draft.md").write_text("## One\n\nA long passage here.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('language = "en"\nmanuscript = "draft.md"\n', encoding="utf-8")
    base = ["audio-direction", "add", "--project", str(tmp_path), "--chapter", "1", "--line", "3"]
    assert main([*base, "--instruction", "Softly", "--start", "0", "--end", "6"]) == 0
    capsys.readouterr()
    ledger = tmp_path / ".lixity" / "audio-directions.json"
    before = ledger.read_bytes()
    assert main([*base, "--instruction", "Loudly", "--start", "4", "--end", "9"]) != 0
    assert "overlap" in capsys.readouterr().out.lower()
    assert ledger.read_bytes() == before
    assert main([*base, "--instruction", "Next", "--start", "7", "--end", "11"]) == 0
    assert len(json.loads(capsys.readouterr().out)["directions"]) == 2


def test_add_rejects_concurrent_manuscript_change(tmp_path, capsys, monkeypatch):
    import lixity.speech_direction_cli as cli

    manuscript = tmp_path / "draft.md"
    manuscript.write_text("## One\n\nFirst paragraph.\n", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('language = "en"\nmanuscript = "draft.md"\n', encoding="utf-8")
    original_save = cli.save_direction

    def concurrent_save(*args, **kwargs):
        manuscript.write_text("## One\n\nChanged paragraph.\n", encoding="utf-8")
        return original_save(*args, **kwargs)

    monkeypatch.setattr(cli, "save_direction", concurrent_save)
    assert main(["audio-direction", "add", "--project", str(tmp_path), "--chapter", "1", "--line", "3",
                 "--instruction", "Quietly."]) != 0
    assert "changed" in capsys.readouterr().out.lower()
    assert not (tmp_path / ".lixity" / "audio-directions.json").exists()
