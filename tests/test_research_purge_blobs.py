"""Purge follows both original-source and extracted-text blob ownership."""

from unittest.mock import patch

import pytest

from lixity.research import api
from lixity.research.ocr import OCRBlock, OCRExtractionResult
from lixity.research.repository import Repository, digest
from tests.research_support import retained_files


def capture(project, root, name, kind, text, *, source_id=None, pdf_bytes=None):
    """Keep storage real; substitute only the external PDF extraction result."""
    source = root / (name + (".pdf" if kind == "pdf" else ".txt"))
    content = pdf_bytes if pdf_bytes is not None else ("%PDF-1.4 synthetic " + name).encode()
    source.write_bytes(content if kind == "pdf" else text.encode("utf-8"))
    if kind == "text":
        return api.ingest(project, source, allow_retention=True, source_id=source_id)
    extraction = OCRExtractionResult(
        pages=[],
        full_text=text,
        blocks=[OCRBlock(page_number=1, text=text)],
        spans=[(0, len(text))],
    )
    with patch("lixity.research.api.extract_pdf_document", return_value=extraction):
        return api.ingest(project, source, allow_retention=True, source_id=source_id)


@pytest.mark.parametrize(
    "removed_kind,retained_kind", [("text", "pdf"), ("pdf", "text"), ("pdf", "pdf")]
)
@pytest.mark.parametrize("same_source", [False, True])
def test_purge_keeps_text_owned_by_a_retained_source_or_extraction(
    tmp_path, removed_kind, retained_kind, same_source
):
    project = tmp_path / "project"
    api.init(project, title="Synthetic shared blobs")
    text = "Synthetic shared extracted text."
    shared = digest(text.encode())
    removed = capture(project, tmp_path, "removed", removed_kind, text)
    retained = capture(
        project,
        tmp_path,
        "retained",
        retained_kind,
        text,
        source_id=removed["source_id"] if same_source else None,
    )
    passage = api.get_source(project, retained["source_id"])["passages"][0]["id"]
    arguments = {"version_id": removed["source_version_id"]} if same_source else {}
    expected_deleted = {digest(b"%PDF-1.4 synthetic removed")} if removed_kind == "pdf" else set()
    before = retained_files(project)
    head = Repository(project).snapshot().digest

    preview = api.purge(project, removed["source_id"], dry_run=True, **arguments)
    assert set(preview["deleted_blobs"]) == expected_deleted
    assert preview["retained_shared_blobs"] == [shared]
    assert preview["snapshot"] == head
    assert retained_files(project) == before

    result = api.purge(project, removed["source_id"], **arguments)
    assert set(result["deleted_blobs"]) == expected_deleted
    assert result["retained_shared_blobs"] == [shared]
    assert result["snapshot"] != head
    assert (project / "research" / "blobs" / shared).read_bytes() == text.encode()
    assert api.cite(project, passage)["verbatim"] == text
    assert api.audit(project)["ok"]


def test_purge_preserves_both_shared_pdf_descriptors_until_the_last_owner(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic duplicate PDFs")
    text = "Synthetic text shared by two PDF extractions."
    pdf = b"%PDF-1.4 synthetic shared original"
    first = capture(project, tmp_path, "first", "pdf", text, pdf_bytes=pdf)
    second = capture(project, tmp_path, "second", "pdf", text, pdf_bytes=pdf)
    descriptors = {digest(pdf), digest(text.encode())}
    passage = api.get_source(project, second["source_id"])["passages"][0]["id"]

    result = api.purge(project, first["source_id"])
    assert result["deleted_blobs"] == []
    assert set(result["retained_shared_blobs"]) == descriptors
    assert api.cite(project, passage)["verbatim"] == text
    assert api.audit(project)["ok"]

    result = api.purge(project, second["source_id"])
    assert set(result["deleted_blobs"]) == descriptors
    assert result["retained_shared_blobs"] == []
    assert not any((project / "research" / "blobs" / sha).exists() for sha in descriptors)
    assert api.audit(project)["ok"]


def test_pdf_purge_dry_run_and_save_include_exclusive_extracted_bytes(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic exclusive PDF blobs")
    text = "Synthetic exclusive extracted bytes."
    source = capture(project, tmp_path, "exclusive", "pdf", text)
    descriptors = {digest(b"%PDF-1.4 synthetic exclusive"), digest(text.encode())}
    before = retained_files(project)

    preview = api.purge(project, source["source_id"], dry_run=True)
    assert set(preview["deleted_blobs"]) == descriptors
    assert preview["retained_shared_blobs"] == []
    assert retained_files(project) == before
    result = api.purge(project, source["source_id"])
    assert set(result["deleted_blobs"]) == descriptors
    assert result["retained_shared_blobs"] == []
    assert not any((project / "research" / "blobs" / sha).exists() for sha in descriptors)
    assert api.audit(project)["ok"]


def test_failed_purge_head_rotation_keeps_original_and_extracted_bytes(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic PDF purge atomicity")
    text = "Synthetic extraction retained until HEAD publication."
    source = capture(project, tmp_path, "exclusive", "pdf", text)
    descriptors = {digest(b"%PDF-1.4 synthetic exclusive"), digest(text.encode())}
    passage = api.get_source(project, source["source_id"])["passages"][0]["id"]
    before = Repository(project).snapshot()

    with (
        patch(
            "lixity.research.repository.replace_head",
            side_effect=OSError("Synthetic interrupted HEAD"),
        ),
        pytest.raises(OSError, match="Synthetic interrupted HEAD"),
    ):
        api.purge(project, source["source_id"])
    assert Repository(project).snapshot().digest == before.digest
    assert all((project / "research" / "blobs" / sha).is_file() for sha in descriptors)
    assert api.cite(project, passage)["verbatim"] == text
    assert api.audit(project)["ok"]

    result = api.purge(project, source["source_id"])
    assert set(result["deleted_blobs"]) == descriptors
    assert not any((project / "research" / "blobs" / sha).exists() for sha in descriptors)
    assert api.audit(project)["ok"]
