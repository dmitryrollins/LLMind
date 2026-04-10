from __future__ import annotations

import base64
import json
import time

import requests

from llmind.models import ExtractionResult

OLLAMA_URL = "http://localhost:11434/api/chat"

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


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from text if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
    if text.endswith("```"):
        text = text[:text.rindex("```")]
    return text.strip()


def _parse_response(content: str) -> ExtractionResult:
    """Parse model response JSON into ExtractionResult.

    The model may wrap its JSON in markdown fences. Strip them before parsing.
    Raises ValueError if JSON is malformed.
    """
    cleaned = _strip_fences(content)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON from model: {e}") from e

    return ExtractionResult(
        language=data["language"],
        description=data["description"],
        text=data["text"],
        structure=data["structure"],
    )


def query_ollama(
    image_bytes: bytes,
    model: str = "qwen2.5-vl:7b",
    base_url: str = OLLAMA_URL,
    retries: int = 3,
    retry_delay: float = 1.0,
) -> ExtractionResult:
    """Send image bytes to Ollama, return ExtractionResult.

    Retries up to `retries` times with exponential backoff on connection errors.
    Raises RuntimeError if all retries exhausted or response is malformed.
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": EXTRACTION_PROMPT,
                "images": [image_b64],
            }
        ],
    }

    for attempt in range(retries):
        try:
            resp = requests.post(base_url, json=payload, timeout=120)
            resp.raise_for_status()
            return _parse_response(resp.json()["message"]["content"])
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == retries - 1:
                raise RuntimeError(
                    f"Ollama unreachable after {retries} attempts: {e}"
                ) from e
            time.sleep(retry_delay * (2**attempt))
        except (KeyError, requests.HTTPError) as e:
            raise RuntimeError(f"Ollama error: {e}") from e

    # Unreachable, but satisfies type checkers
    raise RuntimeError(f"Ollama unreachable after {retries} attempts")


def query_ollama_pdf(
    page_image_bytes_list: list[bytes],
    model: str = "qwen2.5-vl:7b",
    base_url: str = OLLAMA_URL,
    retries: int = 3,
    retry_delay: float = 1.0,
) -> ExtractionResult:
    """Query Ollama for each page of a PDF, then merge results.

    Each page is sent separately. Results merged with '═══ PAGE N ═══' separators.
    Returns a single ExtractionResult with merged text and first page's metadata.
    """
    results = [
        query_ollama(
            page,
            model=model,
            base_url=base_url,
            retries=retries,
            retry_delay=retry_delay,
        )
        for page in page_image_bytes_list
    ]

    if len(results) == 1:
        return results[0]

    merged_text = "\n".join(
        f"═══ PAGE {i + 1} ═══\n{r.text}" for i, r in enumerate(results)
    )
    first = results[0]
    return ExtractionResult(
        language=first.language,
        description=first.description,
        text=merged_text,
        structure=first.structure,
    )
