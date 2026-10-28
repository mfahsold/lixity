"""Release publication depends on checks for the actual tagged commit."""

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def workflow(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def job(source, name):
    match = re.search(rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-zA-Z][\w-]*:\n|\Z)", source)
    assert match, f"Missing workflow job: {name}"
    return match.group(1)


def test_release_reuses_source_and_browser_checks_for_tag_pushes():
    source = workflow("release.yml")
    for job_name, filename in (("source_checks", "tests.yml"), ("browser_checks", "browser.yml")):
        gate = job(source, job_name)
        assert "if: github.event_name == 'push'" in gate
        assert f"uses: ./.github/workflows/{filename}" in gate
        assert "continue-on-error" not in gate
        assert re.search(r"(?m)^      contents: read$", gate)
        called = workflow(filename)
        assert re.search(r"(?m)^  workflow_dispatch:\s*$", called)
        assert re.search(r"(?m)^  workflow_call:\s*$", called)
        assert re.search(r"(?m)^\s+ref: \$\{\{ github\.sha \}\}\s*$", called)
    published = job(source, "publish")
    assert re.search(r"(?m)^    needs: \[source_checks, browser_checks\]\s*$", published)
    assert "if: github.event_name == 'push'" in published
    assert "always()" not in published and "continue-on-error" not in published
    assert re.search(r"(?m)^\s+ref: \$\{\{ github\.sha \}\}\s*$", published)


def test_existing_pypi_catchup_and_pages_release_ref_remain_available():
    source = workflow("release.yml")
    pypi = job(source, "pypi")
    assert re.search(r"(?m)^    needs: publish\s*$", pypi)
    assert "github.event_name == 'workflow_dispatch' || needs.publish.result == 'success'" in pypi
    assert "ref: ${{ format('refs/tags/{0}', inputs.tag) }}" in pypi
    assert "skip-existing: true" in pypi
    pages = job(source, "pages")
    assert "needs: [publish, pypi]" in pages
    assert "needs.pypi.result == 'success'" in pages
    assert "source_ref: ${{ github.event_name == 'workflow_dispatch'" in pages


def test_browser_release_gate_uses_the_shared_full_suite_command():
    assert re.search(r"(?m)^\s+run: make browser-full PYTHON=python\s*$", workflow("browser.yml"))


def test_release_checks_install_synthetic_audio_prerequisites():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert any(re.match(r"numpy(?:[<>=!~; ]|$)", dep, re.IGNORECASE)
               for dep in project["project"]["optional-dependencies"]["dev"])
    for filename in ("tests.yml", "browser.yml"):
        source = workflow(filename)
        assert 'python -m pip install ".[dev]"' in source
        assert re.search(r"apt-get install -y [^\n]*\bffmpeg\b", source)
