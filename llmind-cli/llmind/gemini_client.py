"""Google Gemini vision client for LLMind."""
from __future__ import annotations

import base64
import os

try:
    import google.genai as _genai_sdk
except ImportError:
    _genai_sdk = None  # type: ignore[assignment]

from llmind.models import ExtractionResult
from llmind.vision import EXTRACTION_PROMPT, _detect_media_type, _parse_response


def query_gemini(
    image_bytes: bytes,
    model: str = "gemini-2.5-flash",
) -> ExtractionResult:
    """Send image to Google Gemini vision model, return ExtractionResult."""
    if _genai_sdk is None:
        raise RuntimeError(
            "Google GenAI SDK not installed. Run: pip install 'llmind-cli[gemini]'"
        )
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

    media_type = _detect_media_type(image_bytes)
    b64 = base64.standard_b64encode(image_bytes).decode()

    try:
        client = _genai_sdk.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=[
                _genai_sdk.types.Part.from_bytes(data=image_bytes, mime_type=media_type),
                EXTRACTION_PROMPT,
            ],
        )
        return _parse_response(response.text)
    except Exception as exc:
        raise RuntimeError(f"Gemini API error: {exc}") from exc
