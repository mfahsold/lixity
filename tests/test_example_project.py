"""The synthetic example is an ordinary editable project, not a browser fixture."""

from pathlib import Path

import pytest


def test_example_project_is_openable_and_exports_without_screenshot_adapter(tmp_path):
    from lixity.config import read_explicit_project_config
    from lixity.site_export import prepare_site
    from scripts.example_project import create_example_project

    target = tmp_path / "example"
    created = create_example_project(target)
    assert created["project"] == target
    config = read_explicit_project_config(target)
    assert config["manuscript"] == "harbour-manuscript.md"
    assert config["language"] == "en"
    assert config["site_publications"]["readers"]["entries"]
    assert (target / config["manuscript"]).read_bytes() == Path("samples/first-look.md").read_bytes()
    bundle = prepare_site(target, manuscript=target / config["manuscript"], include_research=True)
    assert "index.html" in bundle.files
    assert b"The Crate at Warehouse 4" in bundle.files["index.html"]


def test_example_project_never_replaces_an_existing_destination(tmp_path):
    from scripts.example_project import create_example_project

    target = tmp_path / "existing"
    target.mkdir()
    manuscript = target / "manuscript.md"
    manuscript.write_text("Keep this project.")
    with pytest.raises(FileExistsError):
        create_example_project(target)
    assert manuscript.read_text() == "Keep this project."
