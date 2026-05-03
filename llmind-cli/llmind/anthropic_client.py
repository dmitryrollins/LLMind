"""Anthropic Claude vision client for LLMind."""
from __future__ import annotations

import base64
import os

try:
    import anthropic as _anthropic_sdk
except ImportError:
    _anthropic_sdk = None  # type: ignore[assignment]

from llmind.models import ExtractionResult
from llmind.vision import EXTRACTION_PROMPT, _detect_media_type, _parse_response


def query_anthropic(
    image_bytes: bytes,
    model: str = "claude-haiku-4-5-20251001",
) -> ExtractionResult:
    """Send image to Anthropic Claude vision model, return ExtractionResult."""
    if _anthropic_sdk is None:
        raise RuntimeError(
            "Anthropic SDK not installed. Run: pip install 'llmind-cli[anthropic]'"
        )
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

    media_type = _detect_media_type(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode()

    try:
        client = _anthropic_sdk.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }],
        )
        return _parse_response(response.content[0].text)
    except Exception as exc:
        raise RuntimeError(f"Anthropic API error: {exc}") from exc
