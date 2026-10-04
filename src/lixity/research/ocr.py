"""Custom worker boundary and native PDF extraction for research archives.

Model and Baidu source revisions are requested identifiers, not attestations
of the deployed runtime. An external adapter must implement this protocol;
upstream inference entrypoints do not implement it directly.

Page images, block coordinates and warnings exist only in the runtime result.
The research API retains original PDF bytes and extracted UTF-8 text, with
character-span passages; it does not persist audited page/box provenance.
See docs/research/OCR_INTEGRATION.md for upstream compatibility and limitations.
"""

import base64
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
from typing import Any, Literal

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
    model_snapshot: str | None = MODEL_SNAPSHOT
    recipe_revision: str | None = INTEGRATION_RECIPE_REVISION
    implementation_id: Literal["baidu-unlimited-ocr/1", "tesseract-cli/1", "poppler-native/1"] = "baidu-unlimited-ocr/1"


def render_pdf_pages(pdf_path: Path, *, dpi: int = 150, timeout: int | None = None) -> list[PageImage]:
    """Render physical PDF pages to PNG image streams using system pdftoppm.

    Maps physical 1-indexed page numbers to image bytes and SHA-256 digests.
    """
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return []

    with tempfile.TemporaryDirectory(prefix="lixity-pdf-pages-") as tmpdir:
        out_prefix = Path(tmpdir) / "page"
        cmd = [pdftoppm, "-png", "-r", str(dpi), str(pdf_path), str(out_prefix)]
        try:
            res = subprocess.run(cmd, capture_output=True, check=False, timeout=timeout)  # noqa: S603
            if res.returncode != 0:
                return []
        except (OSError, subprocess.SubprocessError):
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


def get_pdf_page_count(pdf_path: Path, *, timeout: float | None = None) -> int | None:
    """Determine the physical page count of a PDF, or ``None`` if undeterminable.

    Tries Poppler's ``pdfinfo`` first, then a raw scan for the page-tree
    ``/Count``. The raw scan cannot see a page tree held in a compressed
    object stream, which is how most modern producers emit it.

    Returning ``None`` rather than a guess matters: a caller that treats this
    as a page count will extract only that many pages, so defaulting to 1
    silently truncates a multi-page document while still succeeding.
    """
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo:
        try:
            res = subprocess.run(  # noqa: S603
                [pdfinfo, str(pdf_path)], capture_output=True, text=True, check=False,
                timeout=timeout if timeout is not None else worker_timeout(),
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if line.startswith("Pages:"):
                        count_str = line.split(":", 1)[1].strip()
                        if count_str.isdigit():
                            return max(1, int(count_str))
        except (OSError, subprocess.SubprocessError):
            pass

    try:
        raw = pdf_path.read_bytes()
        match = re.search(rb"/Type\s*/Pages.*?/Count\s+(\d+)", raw, re.DOTALL)
        if match:
            return max(1, int(match.group(1)))
    except OSError:
        pass

    return None


def worker_timeout() -> int:
    try:
        seconds = int(os.environ.get("LIXITY_OCR_TIMEOUT", "120"))
    except ValueError as error:
        raise ResearchError("LIXITY_OCR_TIMEOUT must be an integer from 1 to 3600 seconds") from error
    if not 1 <= seconds <= 3600:
        raise ResearchError("LIXITY_OCR_TIMEOUT must be an integer from 1 to 3600 seconds")
    return seconds


def _ocr_backend(worker_cmd: str | None = None) -> str:
    """An explicit executable argument preserves the existing worker override."""
    if worker_cmd:
        return "worker"
    backend = os.environ.get("LIXITY_OCR_BACKEND", "").strip().lower()
    if not backend:
        return "worker" if os.environ.get("LIXITY_OCR_WORKER") else "native"
    if backend not in {"native", "worker", "tesseract"}:
        raise ResearchError("LIXITY_OCR_BACKEND must be native, worker or tesseract")
    return backend


def _tesseract_languages() -> list[str]:
    """Validate the requested codes independently of local engine readiness."""
    languages = os.environ.get("LIXITY_OCR_LANGUAGES", "eng").split("+")
    if not languages or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)?", value)
                            for value in languages):
        raise ResearchError("LIXITY_OCR_LANGUAGES must contain Tesseract language codes, for example deu+eng")
    return languages


def _tesseract_settings() -> tuple[str, list[str], list[str]]:
    languages = _tesseract_languages()
    timeout = worker_timeout()
    executable = shutil.which("tesseract")
    if not executable:
        raise ResearchError("Tesseract is not installed or is not on PATH. Install it and the requested language data locally.")
    try:
        result = subprocess.run(  # noqa: S603
            [executable, "--list-langs"], capture_output=True, text=True, encoding="utf-8",
            check=False, timeout=min(15, timeout),
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        raise ResearchError("Cannot inspect Tesseract language data; check the executable and TESSDATA_PREFIX") from error
    if result.returncode != 0:
        raise ResearchError("Cannot inspect Tesseract language data; check TESSDATA_PREFIX and local installation")
    available = [line.strip() for line in result.stdout.splitlines()
                 if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)?", line.strip())]
    return executable, languages, available


def _extract_tesseract(pages: list[PageImage], *, timeout: int | None = None) -> tuple[str, list[OCRBlock], list[str]]:
    """Run a locally installed CLI on every rendered page, without a daemon."""
    executable, languages, available = _tesseract_settings()
    missing = [language for language in languages if language not in available]
    if missing:
        raise ResearchError(f"Tesseract language data missing: {', '.join(missing)}. Install these languages or change LIXITY_OCR_LANGUAGES.")
    if not pages or [page.page_number for page in pages] != list(range(1, len(pages) + 1)):
        raise ResearchError("Tesseract requires all rendered PDF pages; check Poppler pdftoppm")
    deadline = time.monotonic() + (timeout or worker_timeout())
    blocks: list[OCRBlock] = []
    warnings: list[str] = []
    for page in pages:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ResearchError("Tesseract timed out; no partial capture was retained")
        try:
            result = subprocess.run(  # noqa: S603
                [executable, "stdin", "stdout", "-l", "+".join(languages), "--psm", "3", "--dpi", "300"],
                input=page.image_bytes, capture_output=True, check=False, timeout=remaining,
            )
        except subprocess.TimeoutExpired as error:
            raise ResearchError("Tesseract timed out; no partial capture was retained") from error
        except OSError as error:
            raise ResearchError("Tesseract could not run; no partial capture was retained") from error
        diagnostic = result.stderr.decode("utf-8", errors="replace").strip()[:500]
        if result.returncode != 0:
            raise ResearchError(f"Tesseract failed on page {page.page_number}: {diagnostic or result.returncode}; no partial capture was retained")
        if diagnostic:
            warnings.append(f"Tesseract page {page.page_number}: {diagnostic}")
        try:
            text = result.stdout.decode("utf-8").strip()
        except UnicodeDecodeError as error:
            raise ResearchError("Tesseract returned invalid UTF-8; no partial capture was retained") from error
        if not text:
            warnings.append(f"No text recognized on page {page.page_number}; check whether it is blank or unreadable.")
        blocks.extend(OCRBlock(page_number=page.page_number, text=paragraph.strip())
                      for paragraph in text.split("\n\n") if paragraph.strip())
        if len(blocks) > 5000:
            raise ResearchError("Tesseract returned more than 5000 paragraphs; no capture was retained")
    return "\n\n".join(block.text for block in blocks), blocks, warnings


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
    text, blocks, warnings, _ = _extract_pdf_with_backend(pdf_path, pages, worker_cmd, allow_fallback)
    return text, blocks, warnings


def _extract_pdf_with_backend(
    pdf_path: Path,
    pages: list[PageImage],
    worker_cmd: str | None = None,
    allow_fallback: bool = False,
) -> tuple[str, list[OCRBlock], list[str], Literal["baidu-unlimited-ocr/1", "tesseract-cli/1", "poppler-native/1"]]:
    backend = _ocr_backend(worker_cmd)
    cmd = worker_cmd or os.environ.get("LIXITY_OCR_WORKER")
    fallback = allow_fallback or os.environ.get("LIXITY_OCR_FALLBACK", "").lower() in ("1", "true", "yes")
    warnings: list[str] = []
    if backend == "tesseract":
        try:
            text, blocks, warnings = _extract_tesseract(pages)
            if not text.strip():
                raise ResearchError("Tesseract produced no readable text; no capture was retained")
            return text, blocks, warnings, "tesseract-cli/1"
        except ResearchError as error:
            if not fallback:
                raise
            warnings.append(f"Tesseract failed ({error}); fallback to native poppler pdftotext extraction.")
    if backend == "worker" and not cmd:
        raise ResearchError("LIXITY_OCR_BACKEND=worker requires LIXITY_OCR_WORKER")

    # 1. External self-hosted worker invocation if configured
    if backend == "worker" and cmd:
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
                    return full_text, blocks, warnings, "baidu-unlimited-ocr/1"
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
        timeout = worker_timeout()
        deadline = time.monotonic() + timeout
        blocks = []
        page_count = len(pages) if pages else get_pdf_page_count(pdf_path, timeout=timeout)
        if page_count is None:
            raise ResearchError(
                "Cannot determine the page count of this PDF, so the native extractor "
                "would capture only part of it. Poppler's pdfinfo is not available and "
                "the page tree is not readable in the raw file (it is probably in a "
                "compressed object stream). Install Poppler, or configure "
                "LIXITY_OCR_WORKER with --allow-retention to use an OCR worker instead."
            )
        for p_idx in range(1, page_count + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ResearchError("Native PDF extraction timed out; no partial capture was retained")
            cmd_args = [pdftotext, "-f", str(p_idx), "-l", str(p_idx), str(pdf_path), "-"]
            try:
                sub = subprocess.run(cmd_args, capture_output=True, check=False, timeout=remaining)  # noqa: S603
                if sub.returncode == 0:
                    p_text = sub.stdout.decode("utf-8", errors="replace").strip()
                    if p_text:
                        # Split by double newline into distinct paragraphs
                        for para in p_text.split("\n\n"):
                            cleaned = para.strip()
                            if cleaned:
                                blocks.append(OCRBlock(page_number=p_idx, text=cleaned))
            except subprocess.TimeoutExpired as error:
                raise ResearchError("Native PDF extraction timed out; no partial capture was retained") from error
            except OSError:
                warnings.append(f"Native text extraction failed on page {p_idx}; check the original PDF.")
        extracted_pages = {block.page_number for block in blocks}
        for page_number in range(1, page_count + 1):
            if page_number not in extracted_pages:
                warnings.append(f"No native text extracted from page {page_number}; it may be blank or require OCR. Check the original PDF.")

        if blocks:
            full_text = "\n\n".join(b.text for b in blocks)
            return full_text, blocks, warnings, "poppler-native/1"

    raise ResearchError(
        "PDF text extraction failed: no readable text found. For scans, install local Tesseract and set "
        "LIXITY_OCR_BACKEND=tesseract, or configure LIXITY_OCR_WORKER."
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
    backend = _ocr_backend(worker_cmd)
    pages = (render_pdf_pages(pdf_path, dpi=300, timeout=worker_timeout())
             if backend == "tesseract" else render_pdf_pages(pdf_path, timeout=worker_timeout()))

    # Step 3 & 4: Execute OCR extraction boundary
    full_text, blocks, warnings, implementation_id = _extract_pdf_with_backend(
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
        implementation_id=implementation_id,
        model_snapshot=MODEL_SNAPSHOT if implementation_id == IMPLEMENTATION_ID else None,
        recipe_revision=INTEGRATION_RECIPE_REVISION if implementation_id == IMPLEMENTATION_ID else None,
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

        pages = render_pdf_pages(pdf_file, timeout=timeout)
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
    backend_error: str | None = None
    try:
        backend = _ocr_backend(worker_cmd)
    except ResearchError as error:
        backend, backend_error = "invalid", str(error)
    if backend != "worker":
        cmd = None

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
            "Native PDF extraction is available via Poppler. For scans, install local Tesseract and "
            "set LIXITY_OCR_BACKEND=tesseract and LIXITY_OCR_LANGUAGES=deu+eng, or configure LIXITY_OCR_WORKER."
        )
    elif pdftotext_path and not pdftoppm_path:
        status = "partial"
        guidance.append("pdftoppm is missing. Install poppler-utils for page rasterization and coordinate mapping.")
    else:
        status = "missing_dependencies"
        guidance.append("Install poppler-utils (apt install poppler-utils / brew install poppler) for PDF text extraction.")
        guidance.append("For scans, install local Tesseract and select LIXITY_OCR_BACKEND=tesseract, or configure LIXITY_OCR_WORKER.")

    if cmd or backend == "native":
        try:
            worker_timeout()
        except ResearchError as error:
            status = "misconfigured_worker" if cmd else "misconfigured_backend"
            guidance.append(str(error))

    probe_info: dict[str, Any] | None = None
    if probe and backend not in {"tesseract", "invalid"}:
        if cmd and worker_executable:
            probe_info = probe_ocr_worker(cmd)
            if not probe_info["ok"]:
                status = "misconfigured_worker"
                guidance.append(f"Worker probe failed: {probe_info['error']}")
            elif status == "ready":
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
        "backend": backend,
        "guidance": guidance,
    }
    if backend == "native":
        result.update({"implementation_id": "poppler-native/1", "model_snapshot": None,
                       "recipe_revision": None, "recipe_date": None})
    if backend == "worker" and not cmd:
        result["status"] = "misconfigured_worker"
        guidance.append("LIXITY_OCR_BACKEND=worker requires LIXITY_OCR_WORKER")
    if backend in {"tesseract", "invalid"}:
        guidance = []
        result.update({"status": "misconfigured_backend", "guidance": guidance,
                       "model_snapshot": None, "recipe_revision": None, "recipe_date": None,
                       "implementation_id": "tesseract-cli/1" if backend == "tesseract" else None,
                       "tesseract_available": bool(shutil.which("tesseract")) if backend == "tesseract" else False,
                       "tesseract_path": shutil.which("tesseract") if backend == "tesseract" else None,
                       "requested_languages": [], "available_languages": [], "missing_languages": []})
        try:
            if backend_error:
                raise ResearchError(backend_error)
            result["requested_languages"] = _tesseract_languages()
            executable, languages, available = _tesseract_settings()
            missing = [language for language in languages if language not in available]
            result.update({"tesseract_path": executable, "requested_languages": languages,
                           "available_languages": available, "missing_languages": missing})
            if missing:
                guidance.append(f"Tesseract language data missing: {', '.join(missing)}. Install it locally or change LIXITY_OCR_LANGUAGES.")
            elif not pdftoppm_path:
                result["status"] = "partial"
                guidance.append("pdftoppm is missing. Install Poppler for PDF page rendering.")
            else:
                result["status"] = "ready"
                guidance.append("Local Tesseract and the requested language data are available. Recognition quality is not verified; review a permitted scan.")
            if probe and not missing:
                started = time.perf_counter()
                # A blank synthetic PNG exercises engine startup, not recognition accuracy.
                png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAAAAACPAi4CAAAAKUlEQVR4nO3MQREAAAwCIPuX1hD77SAA6VEEAoFAIBAIBAKBQCAQfA8Gpwvw4pr3blgAAAAASUVORK5CYII=")
                _, blocks, probe_warnings = _extract_tesseract(
                    [PageImage(1, png, hashlib.sha256(png).hexdigest())], timeout=min(15, worker_timeout()))
                probe_info = {"ok": True, "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                              "blocks_count": len(blocks), "warnings": probe_warnings}
                if result["status"] == "ready":
                    result["status"] = "ready (probed)"
        except ResearchError as error:
            result["status"] = "misconfigured_backend"
            guidance.append(str(error))
            if probe:
                probe_info = {"ok": False, "error": str(error)}
        if probe and probe_info is None:
            probe_info = {"ok": False, "error": "; ".join(guidance)}
    if probe:
        result["probe"] = probe_info
    return result
