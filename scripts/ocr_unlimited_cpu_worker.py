#!/usr/bin/env python3
"""Optional Unlimited-OCR CPU adapter; requires an explicitly prepared runtime.

No dependencies or weights are downloaded by this script. See
docs/research/OCR_INTEGRATION.md for the pinned external runtime and limits.
"""
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_blocks(text, page_number):
    """Remove known layout delimiters, rejecting unhandled model control tokens."""
    parts = re.split(r"<\|det\|>[^<]*<\|/det\|>", text)
    if any(re.search(r"<\|[^>]*\|>", part) for part in parts):
        raise ValueError("Unhandled OCR control token; refusing a polluted capture")
    blocks = [{"page_number": page_number, "text": part.strip()} for part in parts if part.strip()]
    if not blocks:
        raise ValueError("Empty OCR page; refusing incomplete extraction")
    return blocks


def main():
    root = Path(os.environ["LIXITY_UNLIMITED_OCR_HOME"]).expanduser().resolve(strict=True)
    os.environ["HF_HOME"] = str(root / "hf-cache")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["MPLCONFIGDIR"] = str(root / "mpl-cache")
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    sys.path.insert(0, str(root))
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if request.get("model_snapshot") != "07dea832e22aefee32ad281d4b80551282e1c168":
        raise ValueError("Unsupported requested model snapshot")
    if request.get("recipe_revision") != "d49ff64afffc1f47ab563dc1c589bc2f78808fa4":
        raise ValueError("Unsupported requested recipe")
    pdf = Path(request["pdf_path"]).resolve(strict=True)
    weights = root / "model/model-00001-of-000001.safetensors"
    with weights.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != "2bc48a7a110061ea58fff65d3169367eebe3aee371ca6968dc2219c1b2855fc6":
            raise ValueError("Model weights checksum mismatch")
    import torch
    from infer_transformers import load_model
    torch.set_num_threads(4)
    torch.set_num_interop_threads(2)
    with contextlib.redirect_stdout(sys.stderr):
        tokenizer, model = load_model(str(root / "model"), "cpu")
    original_generate = model.generate
    def checked_generate(*args, **kwargs):
        result = original_generate(*args, **kwargs)
        if int(result[0, -1]) != tokenizer.eos_token_id:
            raise ValueError("OCR generation stopped before end-of-sequence; refusing partial output")
        return result
    model.generate = checked_generate
    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise ValueError("pdftoppm is required")
    blocks = []
    with tempfile.TemporaryDirectory(prefix="lixity-cpu-pages-") as directory:
        subprocess.run([renderer, "-png", "-r", "150", str(pdf), str(Path(directory)/"page")],  # noqa: S603
                       check=True, capture_output=True, timeout=120)
        images = sorted(Path(directory).glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
        expected = request.get("pages", [])
        if not images or len(images) != len(expected):
            raise ValueError("Page coverage mismatch")
        for number, image in enumerate(images, 1):
            if expected[number-1]["page_number"] != number or hashlib.sha256(image.read_bytes()).hexdigest() != expected[number-1]["sha256"]:
                raise ValueError("Rendered page checksum mismatch")
            with torch.inference_mode(), contextlib.redirect_stdout(sys.stderr):
                text = model.infer(tokenizer, prompt="<image>document parsing.", image_file=str(image),
                                   output_path=directory, base_size=1024, image_size=1024, crop_mode=False,
                                   no_repeat_ngram_size=35, ngram_window=128, max_length=4096,
                                   save_results=False, eval_mode=True)
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Empty OCR page; refusing incomplete extraction")
            blocks.extend(extract_blocks(text, number))
    print(json.dumps({"blocks": blocks, "warnings": ["Experimental CPU port using upstream open PR #56; no recognition-confidence estimate."]}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
