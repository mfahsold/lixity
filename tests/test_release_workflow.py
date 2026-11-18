"""Release publication depends on checks for the actual tagged commit."""

import ast
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE_GATES = {
    "source_checks": "tests.yml",
    "browser_checks": "browser.yml",
    "native_checks": "research-platforms.yml",
    "dependency_checks": "dependencies.yml",
}


def workflow(name):
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def job(source, name):
    match = re.search(rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [a-zA-Z][\w-]*:\n|\Z)", source)
    assert match, f"Missing workflow job: {name}"
    return match.group(1)


def test_release_reuses_source_browser_and_native_checks_for_tag_pushes():
    source = workflow("release.yml")
    for job_name, filename in RELEASE_GATES.items():
        gate = job(source, job_name)
        assert "if: github.event_name == 'push'" in gate
        assert f"uses: ./.github/workflows/{filename}" in gate
        assert "needs:" not in gate
        assert "continue-on-error" not in gate
        assert re.search(r"(?m)^      contents: read$", gate)
        called = workflow(filename)
        assert re.search(r"(?m)^  workflow_dispatch:\s*$", called)
        assert re.search(r"(?m)^  workflow_call:\s*$", called)
        assert re.search(r"(?m)^\s+ref: \$\{\{ github\.sha \}\}\s*$", called)
    published = job(source, "publish")
    assert f"needs: [{', '.join(RELEASE_GATES)}]" in published
    assert "if: github.event_name == 'push'" in published
    assert "always()" not in published and "continue-on-error" not in published
    assert re.search(r"(?m)^\s+ref: \$\{\{ github\.sha \}\}\s*$", published)


def test_source_gate_runs_full_suite_on_minimum_supported_python():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    minimum = re.fullmatch(r">=(\d+\.\d+)", project["project"]["requires-python"])
    assert minimum, "Review the source gate when the supported Python range changes"
    gate = job(workflow("tests.yml"), "check")
    versions = re.search(r"(?m)^\s+python-version:\s*(\[[^\n]+\])\s*$", gate)
    assert versions, "Source checks need an explicit supported-interpreter matrix"
    assert {minimum.group(1), "3.12"} <= set(ast.literal_eval(versions.group(1)))
    assert "python-version: ${{ matrix.python-version }}" in gate
    assert 'python -m pytest -W error -q -p no:asyncio -n "$PYTEST_WORKERS"' in gate
    assert "continue-on-error" not in gate


def test_catchup_uses_workflow_helpers_and_immutable_assets_without_rebuilding():
    source = workflow("release.yml")
    pypi = job(source, "pypi")
    assert re.search(r"(?m)^    needs: publish\s*$", pypi)
    assert "github.event_name == 'workflow_dispatch' || needs.publish.result == 'success'" in pypi
    assert "ref: ${{ github.event_name == 'workflow_dispatch'" in pypi
    assert "ref: ${{ github.workflow_sha }}" in pypi
    assert "path: .release-tools" in pypi and "path: release-source" in pypi
    assert "release_channels.py recover" in pypi
    assert "release_channels.py stage-pypi" in pypi
    assert "release_channels.py verify-pypi" in pypi
    assert "--build" not in pypi and "pip install build" not in pypi
    assert "skip-existing" not in pypi
    assert "steps.reconcile.outputs.upload_count != '0'" in pypi
    assert "environment: pypi" in pypi
    assert "id-token: write" in pypi
    pages = job(source, "pages")
    assert "needs: [publish, pypi]" in pages
    assert "needs.pypi.result == 'success'" in pages
    assert "source_ref: ${{ github.event_name == 'workflow_dispatch'" in pages


def test_native_gate_requests_full_scope_and_blocks_publication_on_failure():
    source = workflow("release.yml")
    native = job(source, "native_checks")
    assert "scope: full" in native
    assert "needs:" not in native
    publish = job(source, "publish")
    assert "native_checks" in re.search(r"needs: \[(.*?)\]", publish).group(1)
    assert "always()" not in publish and "!cancelled()" not in publish
    assert "continue-on-error" not in publish


def test_first_publication_and_reruns_select_one_verified_artifact_set():
    source = workflow("release.yml")
    publish = job(source, "publish")
    assert "release_channels.py inspect" in publish
    assert "release_channels.py recover" in publish
    assert "release_channels.py verify-draft" in publish
    assert "release_channels.py verify-github" in publish
    assert "--build" not in publish and "--smoke" not in publish
    assert "actions/download-artifact@" in publish
    assert "name: verified-release-candidate" in publish
    assert 'scripts/check_release.py --dist .release-candidate/dist --tag "$RELEASE_TAG"' in publish
    assert "if: steps.release_state.outputs.state != 'published'" in publish
    assert "if: steps.release_state.outputs.state == 'published'" in publish
    assert "echo missing" not in publish
    assert "2>/dev/null" not in publish
    assert "name: dist" in publish and "path: dist/" in publish
    pypi = job(source, "pypi")
    assert "actions/download-artifact@" in pypi
    assert "if: github.event_name == 'push'" in pypi


def test_publication_permissions_and_serialization_are_job_scoped():
    source = workflow("release.yml")
    global_settings = source[:source.index("jobs:")]
    assert "contents: write" not in global_settings and "id-token: write" not in global_settings
    for name in ("publish", "pypi"):
        publishing = job(source, name)
        assert "concurrency:" in publishing
        assert "cancel-in-progress: false" in publishing
    publish = job(source, "publish")
    assert "contents: write" in publish and "attestations: write" in publish
    assert "persist-credentials: false" in publish


def test_browser_release_gate_uses_the_shared_full_suite_command():
    source = workflow("browser.yml")
    assert "github.event_name == 'workflow_dispatch' && inputs.suites || ''" in source
    assert 'python scripts/run_browser_suites.py --only "${suite_names[@]}" --jobs 3' in source
    assert "LIXITY_BROWSER_FULL=1 python scripts/run_browser_suites.py" in source
    assert "fromJson('[1, 2, 3, 4]')" in source
    assert '--shard "$SHARD/4"' in source


def test_source_gate_runs_wheel_smoke_on_each_python_matrix_version():
    gate = job(workflow("tests.yml"), "check")
    assert "scripts/check_release.py --build --smoke" in gate
    assert "--install-report" in gate
    assert "name: verified-release-candidate" in gate
    assert "inputs.stage_candidate && matrix.python-version == '3.12'" in gate
    for name in ("release.yml", "rc.yml"):
        assert "stage_candidate: true" in job(workflow(name), "source_checks")


def test_release_candidate_workflow_qualifies_source_browser_and_native_before_tagging():
    source = workflow("rc.yml")
    assert "workflow_dispatch:" in source
    for job_name, filename in RELEASE_GATES.items():
        gate = job(source, job_name)
        assert f"uses: ./.github/workflows/{filename}" in gate
        assert "needs:" not in gate
    assert "scope: full" in job(source, "native_checks")
    ready = job(source, "ready")
    assert f"needs: [{', '.join(RELEASE_GATES)}]" in ready
    assert "name: verified-release-candidate" in ready
    assert "scripts/check_release.py --dist .release-candidate/dist" in ready


def test_release_checks_install_synthetic_audio_prerequisites():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert any(re.match(r"numpy(?:[<>=!~; ]|$)", dep, re.IGNORECASE)
               for dep in project["project"]["optional-dependencies"]["dev"])
    source = workflow("tests.yml")
    assert 'python -m pip install ".[dev]"' in source
    assert re.search(r"apt-get install -y [^\n]*\bffmpeg\b", source)
    browser = workflow("browser.yml")
    assert 'python -m pip install ".[dev]"' in browser
    assert re.search(r"npm install --no-save [^\n]*\baxe-core@", browser)


def test_native_scope_validation_executes_before_an_unknown_scope_can_select_portability():
    source = workflow("research-platforms.yml")
    validation = re.search(r"Validate native check scope.*?run: >-\n\s+(python -c [^\n]+)", source, re.S)
    assert validation, "Native workflow must validate its open-ended workflow_call input"
    argv = shlex.split(validation.group(1))
    argv[0] = sys.executable
    for scope, expected in (("full", 0), ("portability", 0), ("invalid", 1)):
        result = subprocess.run(  # noqa: S603 - checked-in workflow command, fixed interpreter
            argv, env={**os.environ, "NATIVE_SCOPE": scope},
                                text=True, capture_output=True, check=False)
        assert result.returncode == expected
    callable_inputs = source.split("  workflow_call:", 1)[1].split("permissions:", 1)[0]
    assert "type: string" in callable_inputs and "default: full" in callable_inputs
    assert "group: research-platforms-" in source
