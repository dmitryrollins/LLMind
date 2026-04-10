"""OpenAI GPT vision client for LLMind."""
from __future__ import annotations

import base64
import os

try:
    import openai as _openai_sdk
except ImportError:
    _openai_sdk = None  # type: ignore[assignment]

from llmind.models import ExtractionResult
from llmind.vision import EXTRACTION_PROMPT, _detect_media_type, _parse_response


def query_openai(
    image_bytes: bytes,
    model: str = "gpt-4o-mini",
) -> ExtractionResult:
    """Send image to OpenAI GPT vision model, return ExtractionResult."""
    if _openai_sdk is None:
        raise RuntimeError(
            "OpenAI SDK not installed. Run: pip install 'llmind-cli[openai]'"
        )
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

    media_type = _detect_media_type(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode()

    try:
        client = _openai_sdk.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{b64}",
                        },
                    },
                ],
            }],
        )
        return _parse_response(response.choices[0].message.content)
    except Exception as exc:
        raise RuntimeError(f"OpenAI API error: {exc}") from exc
