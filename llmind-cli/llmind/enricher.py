"""Enricher pipeline: orchestrates the full LLMind enrichment flow for a single file.

Steps:
1. Safety check
2. Compute SHA-256 checksum
3. Freshness check (skip if already enriched with same checksum)
4. Load image bytes (PDF: convert pages via pdf2image)
5. Query vision provider
6. Build Layer dataclass
7. Read existing layers from XMP (if any)
8. Append new layer to history
9. Sign the layer (if key provided)
10. Build XMP string
11. Inject XMP into file
12. Return EnrichResult
"""
from __future__ import annotations

import dataclasses
import time
from datetime import datetime, timezone
from pathlib import Path

from llmind.crypto import derive_key_id, sha256_file, sign_layer
from llmind.injector import inject
from llmind.models import EnrichResult, Layer
from llmind.vision import query_image, query_pdf, PROVIDER_DEFAULTS
from llmind.reader import is_fresh, read as read_meta
from llmind.safety import is_safe_file
from llmind.xmp import build_xmp, layer_to_dict


def enrich(
    path: Path,
    model: str | None = None,
    base_url: str = "http://localhost:11434/api/chat",
    creation_key: str | None = None,
    generator: str = "llmind-cli/0.1.0",
    force: bool = False,
    provider: str = "ollama",
) -> EnrichResult:
    """Enrich a file with LLMind semantic XMP metadata.

    Returns EnrichResult with success/skipped/error status.
    Never raises — all exceptions are captured into EnrichResult.error.

    Args:
        path: Path to the image or PDF file.
        model: Model identifier. Defaults to provider-specific default if None.
        base_url: Ollama API endpoint URL (used only for ollama provider).
        creation_key: 64-char hex key for signing. Omit to skip signing.
        generator: Generator string written into the layer.
        force: If True, re-enrich even if the file is already fresh.
        provider: Vision AI provider ("ollama", "anthropic", "openai").

    Returns:
        EnrichResult describing the outcome of the enrichment attempt.
    """
    start = time.monotonic()
    try:
        return _enrich(path, model, base_url, creation_key, generator, force, start, provider)
    except Exception as exc:
        elapsed = time.monotonic() - start
        return EnrichResult(
            path=path,
            success=False,
            skipped=False,
            version=None,
            regions=0,
            figures=0,
            tables=0,
            elapsed=elapsed,
            error=str(exc),
        )


def _enrich(
    path: Path,
    model: str | None,
    base_url: str,
    creation_key: str | None,
    generator: str,
    force: bool,
    start: float,
    provider: str = "ollama",
) -> EnrichResult:
    """Internal enrichment logic — may raise; caller wraps exceptions."""
    if not is_safe_file(path):
        raise ValueError(f"Unsafe file: {path}")

    checksum = sha256_file(path)

    if not force and is_fresh(path, checksum):
        return EnrichResult(
            path=path,
            success=False,
            skipped=True,
            version=None,
            regions=0,
            figures=0,
            tables=0,
            elapsed=0.0,
            error=None,
        )

    # Query vision provider
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        image_pages = _pdf_to_images(path)
        extraction = query_pdf(image_pages, provider=provider, model=model, base_url=base_url)
    else:
        extraction = query_image(path.read_bytes(), provider=provider, model=model, base_url=base_url)

    resolved_model = model or PROVIDER_DEFAULTS.get(provider, "")

    # Read existing layers
    existing_meta = read_meta(path)
    existing_layers: list[Layer] = list(existing_meta.layers) if existing_meta else []
    version = len(existing_layers) + 1

    # Build new layer
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    layer = Layer(
        version=version,
        timestamp=timestamp,
        generator=generator,
        generator_model=resolved_model,
        checksum=checksum,
        language=extraction.language,
        description=extraction.description,
        text=extraction.text,
        structure=extraction.structure,
        key_id=derive_key_id(creation_key) if creation_key else "",
        signature=None,
    )

    # Sign layer if key provided
    if creation_key:
        layer_dict = layer_to_dict(layer, include_signature=False)
        sig = sign_layer(creation_key, layer_dict)
        layer = dataclasses.replace(layer, signature=sig)

    # Build XMP and inject into file
    all_layers = existing_layers + [layer]
    xmp = build_xmp(all_layers)
    inject(path, xmp)

    # Rename to <stem>.llmind<suffix>  (e.g. photo.png → photo.llmind.png)
    out_path = path.with_name(path.stem + ".llmind" + path.suffix)
    path.replace(out_path)

    elapsed = time.monotonic() - start
    structure = extraction.structure
    return EnrichResult(
        path=out_path,
        success=True,
        skipped=False,
        version=version,
        regions=len(structure.get("regions", [])),
        figures=len(structure.get("figures", [])),
        tables=len(structure.get("tables", [])),
        elapsed=elapsed,
        error=None,
    )


def _pdf_to_images(path: Path) -> list[bytes]:
    """Convert PDF pages to JPEG bytes using pdf2image.

    Args:
        path: Path to the PDF file.

    Returns:
        List of JPEG-encoded bytes, one per page.
    """
    import io

    from pdf2image import convert_from_path

    pages = convert_from_path(str(path), dpi=150)
    result: list[bytes] = []
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, format="JPEG")
        result.append(buf.getvalue())
    return result
