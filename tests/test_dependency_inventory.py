"""Dependency evidence describes the packages and bytes the project ships."""

import hashlib
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dependency_inventory as inventory  # noqa: E402


def test_inventory_distinguishes_bundled_code_from_build_packages():
    components = inventory.browser_components(ROOT)
    packages = {component.get("purl") for component in components}
    assert {
        "pkg:npm/%40mermaid-js/tiny@12.3.0", "pkg:npm/preact@10.29.8",
        "pkg:npm/photoswipe@5.4.4", "pkg:npm/htm@3.1.1", "pkg:npm/leaflet@1.9.4",
    } <= packages
    mermaid = next(component for component in components if component["name"] == "tiny")
    assert "pkg:npm/dompurify@3.4.17" in {
        component.get("purl") for component in mermaid["components"]
    }
    editor = next(component for component in components if component["name"] == "codemirror-editor.js")
    embedded = {component["name"] for component in editor["components"]}
    assert "state" in embedded
    assert {"esbuild", "lint", "streamparser"}.isdisjoint(embedded)
    bundle = ROOT / "src/lixity/ui/assets/vendor/codemirror-editor.js"
    assert editor["hashes"] == [{"alg": "SHA-256", "content": hashlib.sha256(bundle.read_bytes()).hexdigest()}]


def test_python_inventory_requires_a_single_runtime_resolution():
    project = {"metadata": {"name": "Lixity", "version": "0.8.2"}, "requested": True}
    dependency = {
        "metadata": {"name": "Typing_Extensions", "version": "4.16.0"},
        "requested": False,
        "download_info": {"archive_info": {"hashes": {"sha256": "a" * 64}}},
    }
    report = {"version": "1", "install": [project, dependency]}
    selected, [component] = inventory.python_resolution(report, "0.8.2")
    assert selected == project
    assert component["purl"] == "pkg:pypi/typing-extensions@4.16.0"
    assert component["hashes"] == [{"alg": "SHA-256", "content": "a" * 64}]
    project["requested_extras"] = ["dev"]
    with pytest.raises(ValueError, match="exactly one Lixity runtime target"):
        inventory.python_resolution(report, "0.8.2")


def test_vendor_catalog_must_cover_every_shipped_vendor_file(tmp_path):
    catalog = tmp_path / "scripts/browser-vendor.json"
    catalog.parent.mkdir()
    catalog.write_text(json.dumps([]), encoding="utf-8")
    asset = tmp_path / "src/lixity/ui/assets/vendor/uncataloged.js"
    asset.parent.mkdir(parents=True)
    asset.write_text("var example = 1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"uncataloged\.js"):
        inventory.vendor_packages(tmp_path)


def test_release_inventory_rejects_pip_report_for_different_wheel(tmp_path):
    version = inventory.source_version(ROOT)
    wheel = tmp_path / f"lixity-{version}-py3-none-any.whl"
    sdist = tmp_path / f"lixity-{version}.tar.gz"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("lixity/__init__.py", "# release fixture\n")
    with tarfile.open(sdist, "w:gz"):
        pass
    (tmp_path / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in (wheel, sdist)
    ), encoding="utf-8")
    report = {
        "version": "1",
        "environment": {
            "python_full_version": "3.12.10", "implementation_name": "cpython",
            "sys_platform": "linux", "platform_machine": "x86_64",
        },
        "install": [
            {
                "metadata": {"name": "lixity", "version": version}, "requested": True,
                "download_info": {"archive_info": {"hashes": {"sha256": "a" * 64}}},
            },
            {"metadata": {"name": "rich", "version": "15.0.0"}, "requested": False},
        ],
    }
    with pytest.raises(ValueError, match="not resolved from the exact release wheel"):
        inventory.create_sbom(ROOT, report, None, tmp_path)
