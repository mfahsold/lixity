"""Audit standalone browser pins and assemble a CycloneDX runtime inventory."""

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from check_release import source_version, verify_checksums

ROOT = Path(__file__).resolve().parents[1]
VENDOR = Path("src/lixity/ui/assets/vendor")
EDITOR = Path("scripts/editor")
EDITOR_BUNDLE = "codemirror-editor.js"
EDITOR_LICENSE = "codemirror.LICENSE"
NPM_ADVISORIES = "https://registry.npmjs.org/-/npm/v1/security/advisories/bulk"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_component(filename, digest):
    return {"type": "file", "name": filename, "hashes": [{"alg": "SHA-256", "content": digest}]}


def library(ecosystem, name, version, license_id=None):
    group, _, leaf = name.rpartition("/")
    component = {
        "type": "library", "name": leaf, "version": version,
        "purl": f"pkg:{ecosystem}/{quote(name, safe='/')}@{quote(version, safe='')}",
    }
    if group:
        component["group"] = group
    if license_id:
        component["licenses"] = [{"license": {"id": license_id}}]
    return component


def vendor_packages(root):
    packages = read_json(root / "scripts/browser-vendor.json")
    directory = root / VENDOR
    declared = {EDITOR_BUNDLE, EDITOR_LICENSE, "README.md"}
    for package in packages:
        files = package["files"]
        if declared.intersection(files):
            raise ValueError(f"Duplicate vendor file registration for {package['name']}")
        declared.update(files)
        scripts = []
        for filename, digest in files.items():
            if Path(filename).name != filename:
                raise ValueError(f"Expected a vendor filename: {filename}")
            data = (directory / filename).read_bytes()
            if sha256(data) != digest:
                raise ValueError(f"Vendored SHA-256 did not match the catalog: {filename}")
            if filename.endswith(".js"):
                scripts.append(data)
        for bundled in package.get("embedded", []):
            marker = bundled["notice"].format(version=bundled["version"]).encode()
            if not any(marker in script for script in scripts):
                raise ValueError(f"Vendored {bundled['name']} version did not match {package['name']}")
    unexpected = sorted(path.name for path in directory.iterdir() if path.name not in declared)
    if unexpected:
        raise ValueError(f"Vendor files have no package registration: {', '.join(unexpected)}")
    return packages


def npm_source(component, integrity):
    algorithm, _, encoded = integrity.partition("-")
    digest = base64.b64decode(encoded, validate=True)
    if algorithm != "sha512" or len(digest) != 64:
        raise ValueError(f"Expected SHA-512 registry integrity for {component['name']}")
    name = (component.get("group", "") + "/" + component["name"]).lstrip("/")
    url = f"https://registry.npmjs.org/{name}/-/{component['name']}-{component['version']}.tgz"
    component["externalReferences"] = [{
        "type": "distribution", "url": url,
        "hashes": [{"alg": "SHA-512", "content": digest.hex()}],
    }]


def browser_components(root):
    components = []
    for package in vendor_packages(root):
        component = library("npm", package["name"], package["version"], package["license"])
        npm_source(component, package["integrity"])
        component["components"] = [
            file_component(filename, digest) for filename, digest in package["files"].items()
        ] + [library("npm", item["name"], item["version"]) for item in package.get("embedded", [])]
        components.append(component)

    inputs = read_json(root / EDITOR / "bundle-inputs.json")
    bundle_hash = sha256((root / VENDOR / EDITOR_BUNDLE).read_bytes())
    if bundle_hash != inputs["sha256"] or not inputs["packages"]:
        raise ValueError("Stale CodeMirror bundle inventory. Run npm run build in scripts/editor.")
    editor = file_component(EDITOR_BUNDLE, bundle_hash)
    editor["components"] = [file_component(
        EDITOR_LICENSE, sha256((root / VENDOR / EDITOR_LICENSE).read_bytes()),
    )]
    lock = read_json(root / EDITOR / "package-lock.json")["packages"]
    seen = set()
    for path, version in sorted(inputs["packages"].items()):
        entry = lock[path]
        if entry.get("dev") or entry["version"] != version:
            raise ValueError(f"CodeMirror bundle inventory disagrees with the lock: {path}")
        name = entry.get("name", path.split("node_modules/")[-1])
        if (name, version) in seen:
            continue
        seen.add((name, version))
        component = library("npm", name, version, entry.get("license"))
        npm_source(component, entry["integrity"])
        editor["components"].append(component)
    return [*components, editor]


def download_hash(entry):
    digest = entry.get("download_info", {}).get("archive_info", {}).get("hashes", {}).get("sha256")
    if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Malformed SHA-256 in pip installation report")
    return digest


def python_resolution(report, version):
    if report["version"] != "1":
        raise ValueError("Unsupported pip installation report version")
    requested = [entry for entry in report["install"] if entry["requested"]]
    if (len(requested) != 1 or requested[0]["metadata"]["name"].lower() != "lixity"
            or requested[0]["metadata"]["version"] != version or requested[0].get("requested_extras")):
        raise ValueError("The pip report must resolve exactly one Lixity runtime target without extras")

    components = {}
    for entry in report["install"]:
        if entry is requested[0]:
            continue
        metadata = entry["metadata"]
        name = re.sub(r"[-_.]+", "-", metadata["name"]).lower()
        if (name in components or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name)
                or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.+!-]*", metadata["version"])):
            raise ValueError(f"Invalid or duplicate Python dependency in pip report: {name}")
        component = library("pypi", name, metadata["version"])
        digest = download_hash(entry)
        if digest:
            component["hashes"] = [{"alg": "SHA-256", "content": digest}]
        components[name] = component
    if not components:
        raise ValueError("The pip report must include the Lixity runtime dependency resolution")
    return requested[0], [components[name] for name in sorted(components)]


def create_sbom(root, report, source_sha, dist=None):
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True,  # noqa: S607 - trusted PATH, no shell
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or (source_sha is not None and source_sha != commit):
        raise ValueError("Source SHA must match the checked-out Git commit")
    changes = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal", "--",  # noqa: S607
         "src/lixity", "pyproject.toml", "MANIFEST.in", "scripts/browser-vendor.json", "scripts/editor"],
        cwd=root, text=True,
    )
    if changes and source_sha is not None:
        raise ValueError("An explicit source SHA requires unchanged inventory and package inputs")

    version = source_version(root)
    selected, resolved = python_resolution(report, version)
    environment = report["environment"]
    properties = [
        {"name": "lixity:source:commit", "value": commit},
        {"name": "lixity:source:working-tree", "value": "modified" if changes else "clean"},
        {"name": "lixity:scope", "value": "One Python runtime resolution and vendored browser assets. "
         "Nested third-party browser bundles can contain additional upstream components."},
    ] + [
        {"name": f"lixity:python:{key}", "value": environment[key]}
        for key in ("python_full_version", "implementation_name", "sys_platform", "platform_machine")
    ]
    product = {"type": "application", "name": "lixity", "version": version, "purl": f"pkg:pypi/lixity@{version}"}
    if dist is not None:
        verify_checksums(dist, version)
        wheel = f"lixity-{version}-py3-none-any.whl"
        wheel_hash = sha256((dist / wheel).read_bytes())
        if wheel_hash != download_hash(selected):
            raise ValueError("The pip report was not resolved from the exact release wheel")
        sdist = f"lixity-{version}.tar.gz"
        product["components"] = [
            file_component(wheel, wheel_hash), file_component(sdist, sha256((dist / sdist).read_bytes())),
        ]
    return {
        "$schema": "https://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {"component": product, "properties": properties},
        "components": [*resolved, *browser_components(root)],
    }, resolved


def audit_vendors(root):
    pins = defaultdict(set)
    for package in vendor_packages(root):
        for name in (package["name"], *package.get("advisory_aliases", [])):
            pins[name].add(package["version"])
        for embedded in package.get("embedded", []):
            pins[embedded["name"]].add(embedded["version"])
    coordinates = {name: sorted(pins[name]) for name in sorted(pins)}
    print(f"Auditing vendored npm coordinates: {json.dumps(coordinates)}", flush=True)
    request = Request(NPM_ADVISORIES, json.dumps(coordinates).encode(), {"Content-Type": "application/json"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS npm registry
        advisories = json.load(response)
    if not isinstance(advisories, dict) or advisories.keys() - pins.keys():
        raise ValueError("Unexpected response from the npm bulk advisory API")
    for name, findings in sorted(advisories.items()):
        if not isinstance(findings, list):
            raise ValueError(f"Invalid npm advisory list for {name}")
        for item in findings:
            print(f"{name}: {item['severity']} {item['title']} ({item['url']})")
    print("Vendor advisories found." if any(advisories.values()) else "No vendor advisories found.")
    return int(any(advisories.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit-vendors", help="Query npm advisories for exact checked-in browser pins")
    sbom = commands.add_parser("sbom", help="Describe the Python resolution and checked-in browser bundles")
    sbom.add_argument("--python-report", required=True, type=Path)
    sbom.add_argument("--output", required=True, type=Path)
    sbom.add_argument("--python-requirements", type=Path)
    sbom.add_argument("--source-sha")
    sbom.add_argument("--dist", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "audit-vendors":
            return audit_vendors(ROOT)
        bom, resolved = create_sbom(ROOT, read_json(args.python_report), args.source_sha, args.dist)
        if args.python_requirements is not None:
            lines = []
            for component in resolved:
                if not component.get("hashes"):
                    raise ValueError(f"No archive hash in pip report for {component['name']}")
                digest = component["hashes"][0]["content"]
                lines.append(f"{component['name']}=={component['version']} --hash=sha256:{digest}\n")
            args.python_requirements.write_text("".join(lines), encoding="utf-8")
        args.output.write_text(json.dumps(bom, indent=2) + "\n", encoding="utf-8")
    except (KeyError, OSError, subprocess.CalledProcessError, TypeError, ValueError) as exc:
        print(f"Dependency inventory error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
