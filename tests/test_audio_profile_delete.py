"""Saved speech directions must not be orphaned by profile deletion."""

import json

from lixity.config import read_explicit_project_config
from lixity.speech_direction import direction_state, save_direction
from tests.support import send
from tests.test_server_speech import context

pytest_plugins = ["tests.test_server_speech"]


def test_settings_refuse_deleting_profile_referenced_by_another_source(speech_server):
    port, source, handler, _ = speech_server
    root = source.parent
    config = root / "lixity.toml"
    config.write_text('''language = "en"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3"
[audio.profiles.second]
name = "Second"
engine = "qwen3"
''')
    other = root / "other.md"
    other.write_text("## Another\n\nA second source.\n")
    view = direction_state(root, other)
    save_direction(root, other, {"anchor": view["passages"][0]["anchor"], "profile_id": "second"},
                   expected_source_sha256=view["source_sha256"], expected_settings_sha256=view["settings_sha256"],
                   expected_direction_sha256=view["direction_sha256"])
    other.write_text("## Another\n\nThe passage has changed.\n")
    old = config.read_bytes()
    audio = read_explicit_project_config(root)["audio"]
    del audio["profiles"]["second"]
    response = send(port, "/api/settings", payload={"project_token": context(source, handler)["project_token"],
                                                      "audio": audio})
    assert response.status == 400
    assert "direction" in json.loads(response.body)["message"].lower()
    assert config.read_bytes() == old


def test_settings_can_delete_unreferenced_profile(speech_server):
    port, source, handler, _ = speech_server
    root = source.parent
    (root / "lixity.toml").write_text('''language = "en"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3"
[audio.profiles.second]
name = "Second"
engine = "qwen3"
''')
    audio = read_explicit_project_config(root)["audio"]
    del audio["profiles"]["second"]
    response = send(port, "/api/settings", payload={"project_token": context(source, handler)["project_token"],
                                                      "audio": audio})
    assert response.status == 200, response.body
    assert set(read_explicit_project_config(root)["audio"]["profiles"]) == {"narrator"}


def test_settings_refuse_removal_while_direction_writer_is_busy(speech_server):
    from lixity.research.repository import Repository

    port, source, handler, _ = speech_server
    root = source.parent
    config = root / "lixity.toml"
    config.write_text('''language = "en"
[audio]
selected = "narrator"
[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3"
[audio.profiles.second]
name = "Second"
engine = "qwen3"
''')
    old = config.read_bytes()
    audio = read_explicit_project_config(root)["audio"]
    del audio["profiles"]["second"]
    with Repository(root).locked():
        response = send(port, "/api/settings", payload={"project_token": context(source, handler)["project_token"],
                                                          "audio": audio})
    assert response.status == 400
    assert "busy" in json.loads(response.body)["message"]
    assert config.read_bytes() == old
