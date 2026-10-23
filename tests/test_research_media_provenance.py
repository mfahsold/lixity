"""Presence checks expose provenance gaps without claiming rights validation."""

import json

from lixity.cli import main
from lixity.research import api
from lixity.research.repository import Repository
from tests.test_research_images import png


def test_missing_provenance_is_filtered_before_pagination_without_writes(tmp_path, capsys):
    api.init(tmp_path, title="Synthetic provenance")
    dossier = api.create_dossier(tmp_path, "References", "## Photos\n\n![Unretained](local.png)\n")["dossier_id"]
    for context in ({"origin_url":"https://example.org/one"},
                    {"origin_url":"https://example.org/two", "provenance_note":"Synthetic credit and license note"}):
        current = api.get_dossier(tmp_path, dossier)
        api.attach_dossier_image(tmp_path, dossier, png(), filename="sample.png", allow_retention=True,
            expected_snapshot=current["snapshot"], expected_revision=current["revision"], context=context)
    before = Repository(tmp_path).snapshot().digest
    first = api.list_dossier_images(tmp_path, missing_provenance=True, limit=1)
    second = api.list_dossier_images(tmp_path, missing_provenance=True, limit=1, offset=1)
    assert first["total"] == second["total"] == 2
    assert first["images"][0]["provenance_missing"] == ["origin_url", "provenance_note"]
    assert second["images"][0]["provenance_missing"] == ["provenance_note"]
    assert first["has_more"] and not second["has_more"]
    assert Repository(tmp_path).snapshot().digest == before

    assert main(["research", "dossier-images", "--project", str(tmp_path), "--missing-provenance", "--json", "--limit", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["total"] == 2
    assert Repository(tmp_path).snapshot().digest == before
