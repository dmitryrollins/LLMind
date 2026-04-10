from __future__ import annotations

import base64
import time

import requests

from llmind.models import ExtractionResult
from llmind.vision import EXTRACTION_PROMPT, _parse_response, _strip_fences  # noqa: F401 re-export

OLLAMA_URL = "http://localhost:11434/api/chat"


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
