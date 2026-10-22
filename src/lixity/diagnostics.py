"""Read-only installation diagnostics, without opening a manuscript project."""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from . import __version__
from .config import DEFAULT_PORT
from .service import service_status

DOCTOR_SCHEMA = "lixity-doctor/1"


def doctor(*, port: int = DEFAULT_PORT) -> dict[str, Any]:
    """Compare the imported package, distribution metadata and owned service.

    Diagnostics never install, repair, restart or read project settings. Module
    and interpreter paths identify the installation; project paths and process
    arguments do not belong to this report. A stopped service is a valid state.
    """
    from .api import about

    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Service port must be an integer between 1 and 65535")
    issues: list[dict[str, str]] = []
    distribution_version = None
    try:
        value = metadata.distribution("lixity").version
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Package metadata has no version")
        distribution_version = value
    except (metadata.PackageNotFoundError, OSError, ValueError, KeyError, TypeError):
        issues.append({"code": "distribution-metadata-unavailable", "severity": "error"})
    if distribution_version is not None and distribution_version != __version__:
        issues.append({"code": "distribution-version-mismatch", "severity": "warning"})

    observed = service_status(port)
    if not observed["ok"]:
        issues.append({"code": "service-inspection-unavailable", "severity": "error"})
    elif observed.get("running") is True:
        if observed.get("running_version") is None:
            issues.append({"code": "service-version-unavailable", "severity": "warning"})
        elif observed["running_version"] != __version__:
            issues.append({"code": "service-version-mismatch", "severity": "warning"})

    installed = about()
    commands = {command["name"]: command for command in installed["commands"]}
    return {
        "schema_version": DOCTOR_SCHEMA, "ok": not issues,
        "installation": {
            "cli_version": __version__, "distribution_version": distribution_version,
            "module_path": str(Path(__file__).with_name("__init__.py").resolve()),
            "interpreter": str(Path(sys.executable).absolute()),
        },
        "service": observed,
        "schemas": {
            "analysis": installed["meta"]["schema_version"],
            "style": commands["style"]["schema_version"],
            "research_records": commands["research"]["record_schema_versions"],
            "research_manifests": commands["research"]["manifest_schema_versions"],
            "reading_website": commands["export-site"]["schema_version"],
            "reading_website_data": commands["export-site"]["data_schema_version"],
            "service": observed["schema_version"],
        },
        "issues": issues,
    }
