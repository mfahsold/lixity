"""Readiness uses API metadata only, never a library or attachment request."""

from unittest.mock import patch

from lixity.research import zotero
from lixity.research.repository import ResearchError


def test_local_status_does_not_read_library_records() -> None:
    def metadata_only(path):
        assert path == ""
        return b"Local Zotero API", "synthetic-server"

    with patch.object(zotero, "_request", side_effect=metadata_only):
        result = zotero.connection_status()
    assert result["status"] == "ready"
    assert result["local_api_enabled"] is True
    assert result["safe_refresh_available"] is True
    assert result["library_checked"] is False
    assert "synthetic-server" not in str(result)


def test_unavailable_local_api_is_a_reported_state() -> None:
    with patch.object(zotero, "_request", side_effect=ResearchError("Start Zotero and enable its local API")):
        result = zotero.connection_status()
    assert result["status"] == "unavailable"
    assert result["local_api_enabled"] is None
    assert result["library_checked"] is False


def test_reachable_old_api_does_not_claim_safe_refresh() -> None:
    with patch.object(zotero, "_request", return_value=(b"API", None)):
        result = zotero.connection_status()
    assert result["status"] == "connected"
    assert result["safe_refresh_available"] is False
    assert result["library_checked"] is False
