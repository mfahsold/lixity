"""Filtered snapshots keep list commands fast on large archives."""

from unittest.mock import patch

from lixity.research import api as research_api
from lixity.research.repository import Repository


def test_claim_list_reads_only_claim_records(tmp_path):
    root = str(tmp_path)
    research_api.init(root, title="Filtered archive", language="en")
    dossier = research_api.create_dossier(root, "Synthetic dossier", "Body", language="en")
    claim = research_api.create_claim(
        root, title="Synthetic claim", statement="Statement", dossier_id=dossier["dossier_id"])
    original = Repository.snapshot
    with patch.object(Repository, "snapshot", autospec=True, side_effect=original) as snapshot:
        result = research_api.list_claims(root)
    assert snapshot.call_args.kwargs["kinds"] == frozenset({"claim"})
    assert [item["id"] for item in result["claims"]] == [claim["claim_id"]]


def test_filtered_snapshot_does_not_poison_the_full_cache(tmp_path):
    root = str(tmp_path)
    research_api.init(root, title="Filtered archive", language="en")
    research_api.create_dossier(root, "Synthetic dossier", "Body", language="en")
    repository = Repository(root)
    filtered = repository.snapshot(kinds=frozenset({"claim"}))
    full = repository.snapshot()
    assert set(filtered.records) <= set(full.records)
    assert len(full.records) > len(filtered.records)
