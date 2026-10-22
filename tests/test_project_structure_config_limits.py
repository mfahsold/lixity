"""Inspection bounds configuration bytes at the shared read and token owners."""

import os
from urllib.parse import urlencode

import pytest

from lixity import config, workspace
from lixity.server import pdf_context, routes_project
from tests.support import recording_handler

pytestmark = pytest.mark.portability


def observe_reads(monkeypatch, *, grow=None):
    requests, streams = [], []
    original = os.fdopen
    grown = False

    class Observed:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def read(self, size=-1):
            nonlocal grown
            requests.append(size)
            if grow is not None and not grown:
                grown = True
                path, content = grow
                path.write_bytes(content)
            return self.stream.read(size)

    def fdopen(*args, **kwargs):
        stream = original(*args, **kwargs)
        streams.append(stream)
        return Observed(stream)

    monkeypatch.setattr(os, "fdopen", fdopen)
    return requests, streams


def test_bounded_snapshot_rejects_growth_after_stat_and_closes_the_stream(tmp_path, monkeypatch):
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'title = "x"\n')
    requests, streams = observe_reads(monkeypatch, grow=(path, b'title = "' + b"x" * 100 + b'"\n'))

    with pytest.raises(ValueError) as error:
        config.project_config_snapshot(path, maximum_bytes=16)

    assert type(error.value).__name__ == "ProjectConfigTooLargeError"
    assert requests and all(0 <= size <= 17 for size in requests)
    assert streams and all(stream.closed for stream in streams)


def test_explicit_config_loader_retains_the_shared_descriptor_byte_limit(tmp_path, monkeypatch):
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'title = "x"\n')
    requests, streams = observe_reads(monkeypatch, grow=(path, b'title = "' + b"x" * 100 + b'"\n'))

    with pytest.raises(ValueError) as error:
        config.read_explicit_project_config(tmp_path, maximum_bytes=16)

    assert type(error.value).__name__ == "ProjectConfigTooLargeError"
    assert requests and all(0 <= size <= 17 for size in requests)
    assert streams and all(stream.closed for stream in streams)


def test_bounded_config_loader_preserves_existing_newline_normalization(tmp_path):
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'manuscript = "draft.md"\rtitle = "Synthetic"\r')

    expected = config.read_explicit_project_config(tmp_path)

    assert expected == {"manuscript": "draft.md", "title": "Synthetic"}
    assert config.read_explicit_project_config(tmp_path, maximum_bytes=1024) == expected


def test_workspace_selection_reuses_an_explicit_mapping_without_reopening_config(tmp_path, monkeypatch):
    source = tmp_path / "manuscript.md"
    source.write_text("Synthetic source.", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript = [', encoding="utf-8")

    def forbidden(*args, **kwargs):
        pytest.fail("An explicitly supplied configuration must not be reopened")

    monkeypatch.setattr(workspace, "read_explicit_project_config", forbidden)
    assert workspace.configured_manuscript(tmp_path, project_config={}) is None
    assert workspace.configured_manuscript(tmp_path, project_config={"manuscript": "manuscript.md"}) == str(source)
    assert workspace.discover(root=str(tmp_path), project_config={}).manuscript == str(source)


def test_bounded_context_token_handles_post_stat_growth_without_unbounded_reads(tmp_path, monkeypatch):
    source = tmp_path / "draft.md"
    source.write_text("Synthetic source.", encoding="utf-8")
    path = tmp_path / "lixity.toml"
    path.write_bytes(b'title = "x"\n')
    before = pdf_context.project_settings_token(tmp_path, str(source))
    requests, streams = observe_reads(monkeypatch, grow=(path, b'title = "' + b"x" * 100 + b'"\n'))

    after = pdf_context.project_settings_token(tmp_path, str(source), maximum_config_bytes=16)

    assert after != before
    assert len(after) == 64
    assert requests and all(0 <= size <= 17 for size in requests)
    assert streams and all(stream.closed for stream in streams)


def test_native_inspection_passes_the_same_config_ceiling_to_its_context_guard(tmp_path, monkeypatch):
    from lixity.project_structure import MAX_CONFIG_BYTES

    source = tmp_path / "draft.md"
    source.write_text("Synthetic source.", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('manuscript = "draft.md"\n', encoding="utf-8")
    token = pdf_context.project_settings_token(tmp_path, str(source))
    handler = recording_handler(tmp_path, source_input=source)
    handler.path = "/api/project-structure?" + urlencode({"project_token": token})

    def bounded_token(root, manuscript, **kwargs):
        assert kwargs.get("maximum_config_bytes") == MAX_CONFIG_BYTES
        return token

    monkeypatch.setattr(routes_project, "project_settings_token", bounded_token)
    handler._handle_project_structure()
    status, report = handler.response
    assert status == 200 and report["schema_version"] == "lixity-project-structure/1"
