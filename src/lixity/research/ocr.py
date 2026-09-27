"""Custom worker boundary and native PDF extraction for research archives.

Model and Baidu source revisions are requested identifiers, not attestations
of the deployed runtime. An external adapter must implement this protocol;
upstream inference entrypoints do not implement it directly.

Page images, block coordinates and warnings exist only in the runtime result.
The research API retains original PDF bytes and extracted UTF-8 text, with
character-span passages; it does not persist audited page/box provenance.
See docs/research/OCR_INTEGRATION.md for upstream compatibility and limitations.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .repository import ResearchError

MODEL_SNAPSHOT = "07dea832e22aefee32ad281d4b80551282e1c168"
INTEGRATION_RECIPE_REVISION = "d49ff64afffc1f47ab563dc1c589bc2f78808fa4"
RECIPE_DATE = "2026-07-29"
IMPLEMENTATION_ID = "baidu-unlimited-ocr/1"


@dataclass(frozen=True)
class PageImage:
    page_number: int
    image_bytes: bytes
    sha256: str
    media_type: str = "image/png"


@dataclass(frozen=True)
class OCRBlock:
    page_number: int
    text: str
    box: list[float] | None = None
    confidence: float = 1.0


@dataclass
class OCRExtractionResult:
    pages: list[PageImage]
    full_text: str
    blocks: list[OCRBlock]
    spans: list[tuple[int, int]]  # (start, end) offsets into full_text
    warnings: list[str] = field(default_factory=list)
    model_snapshot: str = MODEL_SNAPSHOT
    recipe_revision: str = INTEGRATION_RECIPE_REVISION


def render_pdf_pages(pdf_path: Path) -> list[PageImage]:
    """Render physical PDF pages to PNG image streams using system pdftoppm.

    Maps physical 1-indexed page numbers to image bytes and SHA-256 digests.
    """
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return []

    with tempfile.TemporaryDirectory(prefix="lixity-pdf-pages-") as tmpdir:
        out_prefix = Path(tmpdir) / "page"
        cmd = [pdftoppm, "-png", "-r", "150", str(pdf_path), str(out_prefix)]
        try:
            res = subprocess.run(cmd, capture_output=True, check=False)  # noqa: S603
            if res.returncode != 0:
                return []
        except OSError:
            return []

        # Find rendered pages, sorted numerically
        page_files = sorted(
            Path(tmpdir).glob("page-*.png"),
            key=lambda p: int(p.stem.split("-")[-1]) if p.stem.split("-")[-1].isdigit() else 0,
        )

        pages: list[PageImage] = []
        for idx, page_file in enumerate(page_files, start=1):
            img_bytes = page_file.read_bytes()
            pages.append(
                PageImage(
                    page_number=idx,
                    image_bytes=img_bytes,
                    sha256=hashlib.sha256(img_bytes).hexdigest(),
                    media_type="image/png",
                )
            )
        return pages


def extract_pdf_with_worker(
    pdf_path: Path,
    pages: list[PageImage],
    worker_cmd: str | None = None,
) -> tuple[str, list[OCRBlock], list[str]]:
    """Execute the configured OCR worker or physical page-aware text extractor."""
    cmd = worker_cmd or os.environ.get("LIXITY_OCR_WORKER")
    warnings: list[str] = []

    # 1. External self-hosted worker invocation if configured
    if cmd:
        with tempfile.TemporaryDirectory(prefix="lixity-ocr-worker-") as tmpdir:
            req_file = Path(tmpdir) / "request.json"
            req_data = {
                "model_snapshot": MODEL_SNAPSHOT,
                "recipe_revision": INTEGRATION_RECIPE_REVISION,
                "pdf_path": str(pdf_path.resolve()),
                "pages": [{"page_number": p.page_number, "sha256": p.sha256} for p in pages],
            }
            req_file.write_text(json.dumps(req_data), encoding="utf-8")

            try:
                proc = subprocess.run(  # noqa: S603
                    [cmd, str(req_file)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=120,
                )
                if proc.returncode == 0:
                    resp = json.loads(proc.stdout)
                    blocks = [
                        OCRBlock(
                            page_number=int(b.get("page_number", 1)),
                            text=str(b.get("text", "")).strip(),
                            box=b.get("box"),
                            confidence=float(b.get("confidence", 1.0)),
                        )
                        for b in resp.get("blocks", [])
                    ]
                    full_text = "\n\n".join(b.text for b in blocks if b.text)
                    return full_text, blocks, resp.get("warnings", [])
                warnings.append(f"OCR worker exited with code {proc.returncode}: {proc.stderr.strip()[:200]}")
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
                warnings.append(f"OCR worker failed: {exc}")

    # 2. Local fallback using system pdftotext with per-page tracking
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        blocks = []
        page_count = len(pages) if pages else 1
        for p_idx in range(1, page_count + 1):
            cmd_args = [pdftotext, "-f", str(p_idx), "-l", str(p_idx), str(pdf_path), "-"]
            try:
                sub = subprocess.run(cmd_args, capture_output=True, check=False)  # noqa: S603
                if sub.returncode == 0:
                    p_text = sub.stdout.decode("utf-8", errors="replace").strip()
                    if p_text:
                        # Split by double newline into distinct paragraphs
                        for para in p_text.split("\n\n"):
                            cleaned = para.strip()
                            if cleaned:
                                blocks.append(OCRBlock(page_number=p_idx, text=cleaned))
            except OSError:
                break

        if blocks:
            full_text = "\n\n".join(b.text for b in blocks)
            return full_text, blocks, warnings

    raise ResearchError(
        "PDF text extraction failed: no text layer found and Baidu Unlimited-OCR worker is not configured. "
        f"Install recipe {INTEGRATION_RECIPE_REVISION} or configure LIXITY_OCR_WORKER."
    )


def extract_pdf_document(
    pdf_path: Path,
    worker_cmd: str | None = None,
) -> OCRExtractionResult:
    """Full extraction pipeline for a PDF document.

    Renders pages, executes the OCR extraction boundary, records spans and warnings.
    """
    if not pdf_path.is_file():
        raise ResearchError(f"PDF document does not exist: {pdf_path}")

    # Step 1 & 2: Render pages
    pages = render_pdf_pages(pdf_path)

    # Step 3 & 4: Execute OCR extraction boundary
    full_text, blocks, warnings = extract_pdf_with_worker(pdf_path, pages, worker_cmd=worker_cmd)

    if not full_text.strip():
        raise ResearchError("OCR extraction produced no readable text")

    # Step 5: Compute exact character spans for passages
    spans: list[tuple[int, int]] = []
    current_offset = 0
    for b in blocks:
        pos = full_text.find(b.text, current_offset)
        if pos == -1:
            pos = full_text.find(b.text)
        if pos != -1:
            end_pos = pos + len(b.text)
            spans.append((pos, end_pos))
            current_offset = end_pos

    return OCRExtractionResult(
        pages=pages,
        full_text=full_text,
        blocks=blocks,
        spans=spans,
        warnings=warnings,
    )


def get_ocr_diagnostics(worker_cmd: str | None = None) -> dict[str, Any]:
    """Inspect and report runtime diagnostic status for OCR and PDF extraction."""
    pdftoppm_path = shutil.which("pdftoppm")
    pdftotext_path = shutil.which("pdftotext")
    cmd = worker_cmd or os.environ.get("LIXITY_OCR_WORKER")

    worker_executable = False
    worker_resolved: str | None = None
    if cmd:
        resolved = shutil.which(cmd)
        if resolved and os.access(resolved, os.X_OK):
            worker_executable = True
            worker_resolved = str(resolved)
        else:
            p = Path(cmd).expanduser().resolve()
            if p.is_file() and os.access(p, os.X_OK):
                worker_executable = True
                worker_resolved = str(p)

    guidance: list[str] = []
    if cmd and not worker_executable:
        status = "misconfigured_worker"
        guidance.append(
            f"Configured OCR worker '{cmd}' was not found or is not executable. Verify file path and execute permissions."
        )
    elif worker_executable and pdftoppm_path:
        status = "ready"
    elif worker_executable and not pdftoppm_path:
        status = "partial"
        guidance.append("OCR worker is configured, but pdftoppm is missing. Install poppler-utils for page rasterization.")
    elif pdftotext_path and pdftoppm_path:
        status = "native_only"
        guidance.append(
            f"Native PDF extraction is available via poppler. To enable OCR for scanned pages, configure self-hosted Baidu Unlimited-OCR worker via LIXITY_OCR_WORKER (recipe {INTEGRATION_RECIPE_REVISION})."
        )
    elif pdftotext_path and not pdftoppm_path:
        status = "partial"
        guidance.append("pdftoppm is missing. Install poppler-utils for page rasterization and coordinate mapping.")
    else:
        status = "missing_dependencies"
        guidance.append("Install poppler-utils (apt install poppler-utils / brew install poppler) for PDF text extraction.")
        guidance.append(f"For scanned documents, configure LIXITY_OCR_WORKER with snapshot {MODEL_SNAPSHOT[:8]}.")

    return {
        "status": status,
        "pdftoppm_available": bool(pdftoppm_path),
        "pdftoppm_path": pdftoppm_path,
        "pdftotext_available": bool(pdftotext_path),
        "pdftotext_path": pdftotext_path,
        "worker_configured": bool(cmd),
        "worker_cmd": cmd,
        "worker_executable": worker_executable,
        "worker_path": worker_resolved,
        "model_snapshot": MODEL_SNAPSHOT,
        "recipe_revision": INTEGRATION_RECIPE_REVISION,
        "recipe_date": RECIPE_DATE,
        "implementation_id": IMPLEMENTATION_ID,
        "guidance": guidance,
    }
