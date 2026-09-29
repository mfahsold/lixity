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
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
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
    confidence: float | None = None


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


def get_pdf_page_count(pdf_path: Path) -> int:
    """Determine the physical page count of a PDF file using pdfinfo or structure inspection."""
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        try:
            res = subprocess.run([pdfinfo, str(pdf_path)], capture_output=True, text=True, check=False)  # noqa: S603
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.startswith("Pages:"):
                        count_str = line.split(":", 1)[1].strip()
                        if count_str.isdigit():
                            return max(1, int(count_str))
        except OSError:
            pass

    try:
        raw = pdf_path.read_bytes()
        match = re.search(rb"/Type\s*/Pages.*?/Count\s+(\d+)", raw, re.DOTALL)
        if match:
            return max(1, int(match.group(1)))
    except OSError:
        pass

    return 1


def worker_timeout() -> int:
    try:
        seconds = int(os.environ.get("LIXITY_OCR_TIMEOUT", "120"))
    except ValueError as error:
        raise ResearchError("LIXITY_OCR_TIMEOUT must be an integer from 1 to 3600 seconds") from error
    if not 1 <= seconds <= 3600:
        raise ResearchError("LIXITY_OCR_TIMEOUT must be an integer from 1 to 3600 seconds")
    return seconds


def _worker_blocks(response: Any, pages: list[PageImage]) -> tuple[list[OCRBlock], list[str]]:
    if not isinstance(response, dict) or not isinstance(response.get("blocks"), list):
        raise ResearchError("Invalid OCR worker response")
    expected = {page.page_number for page in pages}
    if not expected or len(response["blocks"]) > 5000:
        raise ResearchError("OCR requires rendered page coverage and at most 5000 blocks")
    blocks: list[OCRBlock] = []
    for block in response["blocks"]:
        if (not isinstance(block, dict) or type(block.get("page_number")) is not int
                or block["page_number"] not in expected or not isinstance(block.get("text"), str)
                or not block["text"].strip()):
            raise ResearchError("Invalid OCR block text or page number")
        confidence = block.get("confidence")
        if confidence is not None and (type(confidence) not in (float, int)
                or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ResearchError("Invalid OCR confidence")
        box = block.get("box")
        if box is not None and (not isinstance(box, list) or len(box) != 4 or
                any(type(value) not in (float, int) or not math.isfinite(value) for value in box)):
            raise ResearchError("Invalid OCR block coordinates")
        blocks.append(OCRBlock(page_number=block["page_number"], text=block["text"].strip(),
                               box=box, confidence=confidence))
    completed = response.get("completed_pages", [])
    if not isinstance(completed, list) or any(type(page) is not int or page not in expected for page in completed):
        raise ResearchError("Invalid OCR completed pages")
    if {block.page_number for block in blocks} | set(completed) != expected:
        raise ResearchError("OCR worker returned incomplete page coverage")
    warnings = response.get("warnings", [])
    if not isinstance(warnings, list) or any(not isinstance(value, str) for value in warnings):
        raise ResearchError("Invalid OCR warnings")
    blocks.sort(key=lambda block: block.page_number)
    return blocks, warnings


def extract_pdf_with_worker(
    pdf_path: Path,
    pages: list[PageImage],
    worker_cmd: str | None = None,
    allow_fallback: bool = False,
) -> tuple[str, list[OCRBlock], list[str]]:
    """Execute the configured OCR worker or physical page-aware text extractor."""
    cmd = worker_cmd or os.environ.get("LIXITY_OCR_WORKER")
    fallback = allow_fallback or os.environ.get("LIXITY_OCR_FALLBACK", "").lower() in ("1", "true", "yes")
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

            worker_error: str | None = None
            try:
                proc = subprocess.run(  # noqa: S603
                    [cmd, str(req_file)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=worker_timeout(),
                )
                if proc.returncode == 0:
                    resp = json.loads(proc.stdout)
                    blocks, warnings = _worker_blocks(resp, pages)
                    full_text = "\n\n".join(b.text for b in blocks)
                    return full_text, blocks, warnings
                worker_error = f"OCR worker exited with code {proc.returncode}"
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
                worker_error = f"OCR worker failed or timed out: {exc}"

            if not fallback:
                if worker_error and "exited with code" in worker_error:
                    raise ResearchError(f"{worker_error}; no capture was retained")
                raise ResearchError("OCR worker failed or timed out; no partial capture was retained")

            warnings.append(f"OCR worker failed ({worker_error}); fallback to native poppler pdftotext extraction.")

    # 2. Local fallback using system pdftotext with per-page tracking
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        blocks = []
        page_count = len(pages) if pages else get_pdf_page_count(pdf_path)
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
    allow_fallback: bool = False,
) -> OCRExtractionResult:
    """Full extraction pipeline for a PDF document.

    Renders pages, executes the OCR extraction boundary, records spans and warnings.
    """
    if not pdf_path.is_file():
        raise ResearchError(f"PDF document does not exist: {pdf_path}")

    # Step 1 & 2: Render pages
    pages = render_pdf_pages(pdf_path)

    # Step 3 & 4: Execute OCR extraction boundary
    full_text, blocks, warnings = extract_pdf_with_worker(
        pdf_path, pages, worker_cmd=worker_cmd, allow_fallback=allow_fallback
    )

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


def probe_ocr_worker(worker_cmd: str, timeout: int = 15) -> dict[str, Any]:
    """Execute a synthetic single-page probe against a configured worker executable."""
    resolved = shutil.which(worker_cmd)
    target = resolved or str(Path(worker_cmd).expanduser().resolve())
    if not (Path(target).is_file() and os.access(target, os.X_OK)):
        return {"ok": False, "error": f"Worker '{worker_cmd}' is not executable"}

    synthetic_pdf = (
        b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 23 >> stream\nBT /F1 12 Tf (OK) Tj ET\nendstream endobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000212 00000 n \n"
        b"trailer << /Size 5 /Root 1 0 R >>\nstartxref\n285\n%%EOF\n"
    )

    with tempfile.TemporaryDirectory(prefix="lixity-ocr-probe-") as tmpdir:
        tmp_path = Path(tmpdir)
        pdf_file = tmp_path / "probe.pdf"
        pdf_file.write_bytes(synthetic_pdf)
        req_file = tmp_path / "probe_request.json"

        pages = render_pdf_pages(pdf_file)
        if not pages:
            fake_bytes = b"synthetic-probe-png"
            pages = [PageImage(page_number=1, image_bytes=fake_bytes, sha256=hashlib.sha256(fake_bytes).hexdigest())]

        req_data = {
            "model_snapshot": MODEL_SNAPSHOT,
            "recipe_revision": INTEGRATION_RECIPE_REVISION,
            "pdf_path": str(pdf_file.resolve()),
            "pages": [{"page_number": p.page_number, "sha256": p.sha256} for p in pages],
            "probe": True,
        }
        req_file.write_text(json.dumps(req_data), encoding="utf-8")

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(  # noqa: S603
                [target, str(req_file)],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
            if proc.returncode != 0:
                err_msg = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
                return {
                    "ok": False,
                    "error": f"Worker exited with code {proc.returncode}: {err_msg}",
                    "latency_ms": elapsed_ms,
                }
            resp = json.loads(proc.stdout)
            blocks, warnings = _worker_blocks(resp, pages)
            return {
                "ok": True,
                "latency_ms": elapsed_ms,
                "blocks_count": len(blocks),
                "warnings": warnings,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Worker probe timed out after {timeout}s", "latency_ms": round(timeout * 1000, 1)}
        except (OSError, json.JSONDecodeError, ResearchError) as exc:
            return {"ok": False, "error": f"Worker probe failed: {exc}", "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def get_ocr_diagnostics(worker_cmd: str | None = None, *, probe: bool = False) -> dict[str, Any]:
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

    if cmd:
        try:
            worker_timeout()
        except ResearchError as error:
            status = "misconfigured_worker"
            guidance.append(str(error))

    probe_info: dict[str, Any] | None = None
    if probe:
        if cmd and worker_executable:
            probe_info = probe_ocr_worker(cmd)
            if not probe_info["ok"]:
                guidance.append(f"Worker probe failed: {probe_info['error']}")
            else:
                status = "ready (probed)"
        elif cmd and not worker_executable:
            probe_info = {"ok": False, "error": f"Configured worker '{cmd}' is not executable"}
        else:
            probe_info = {"ok": False, "error": "No OCR worker configured (LIXITY_OCR_WORKER is unset)"}

    result: dict[str, Any] = {
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
    if probe:
        result["probe"] = probe_info
    return result
