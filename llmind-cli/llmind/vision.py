"""Shared vision utilities and provider dispatcher."""
from __future__ import annotations

import json

from llmind.models import ExtractionResult

EXTRACTION_PROMPT = """Analyze this image and respond with a JSON object containing:
- "language": detected language code (e.g. "en", "fr", "de")
- "description": a concise 1-2 sentence description of the image content
- "text": all visible text extracted from the image, verbatim
- "structure": an object with:
  - "type": document type ("document", "photo", "diagram", "chart", "form", "other")
  - "regions": list of {"label": str, "type": str} for identified content regions
  - "figures": list of {"caption": str} for any figures/images within the document
  - "tables": list of {"headers": [str], "rows": int} for any tables

Respond with JSON only, no markdown, no explanation."""

PROVIDER_DEFAULTS: dict[str, str] = {
    "ollama": "qwen2.5-vl:7b",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from model response."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
    if text.endswith("```"):
        text = text[:text.rindex("```")]
    return text.strip()


def _coerce_str(value: object, default: str = "") -> str:
    """Coerce a model response value to str — handles lists returned by some Ollama models."""
    if value is None:
        return default
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _parse_response(content: str) -> ExtractionResult:
    """Parse model JSON response into ExtractionResult. Raises ValueError on bad JSON."""
    try:
        data = json.loads(_strip_fences(content))
        return ExtractionResult(
            language=_coerce_str(data.get("language"), "en"),
            description=_coerce_str(data.get("description")),
            text=_coerce_str(data.get("text")),
            structure=data.get("structure") or {},
        )
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Invalid model response: {exc}") from exc


def _detect_media_type(image_bytes: bytes) -> str:
    """Detect image MIME type from magic bytes."""
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[:4] in (b"GIF8", b"GIF9"):
        return "image/gif"
    return "image/jpeg"  # safe default


def query_image(
    image_bytes: bytes,
    provider: str = "ollama",
    model: str | None = None,
    base_url: str = "http://localhost:11434/api/chat",
    retries: int = 3,
    retry_delay: float = 1.0,
) -> ExtractionResult:
    """Dispatch image query to the appropriate provider."""
    resolved_model = model or PROVIDER_DEFAULTS.get(provider, "")
    if provider == "ollama":
        from llmind.ollama import query_ollama
        return query_ollama(image_bytes, model=resolved_model, base_url=base_url, retries=retries, retry_delay=retry_delay)
    elif provider == "anthropic":
        from llmind.anthropic_client import query_anthropic
        return query_anthropic(image_bytes, model=resolved_model)
    elif provider == "openai":
        from llmind.openai_client import query_openai
        return query_openai(image_bytes, model=resolved_model)
    elif provider == "gemini":
        from llmind.gemini_client import query_gemini
        return query_gemini(image_bytes, model=resolved_model)
    else:
        raise ValueError(f"Unknown provider: {provider!r}. Choose: ollama, anthropic, openai, gemini")


def query_pdf(
    page_image_bytes_list: list[bytes],
    provider: str = "ollama",
    model: str | None = None,
    base_url: str = "http://localhost:11434/api/chat",
    retries: int = 3,
    retry_delay: float = 1.0,
) -> ExtractionResult:
    """Query all PDF pages and merge results."""
    results = [
        query_image(page, provider=provider, model=model, base_url=base_url, retries=retries, retry_delay=retry_delay)
        for page in page_image_bytes_list
    ]
    if len(results) == 1:
        return results[0]
    merged_text = "\n".join(f"═══ PAGE {i+1} ═══\n{r.text}" for i, r in enumerate(results))
    first = results[0]
    return ExtractionResult(
        language=first.language,
        description=first.description,
        text=merged_text,
        structure=first.structure,
    )
