"""Embedding generation and similarity search for LLMind files.

Supports four providers:
  - ollama   : nomic-embed-text (local, default)
  - openai   : text-embedding-3-small
  - voyage   : voyage-3 (Anthropic's embedding partner)
  - gemini   : text-embedding-004 (Google Gemini)

The embedding vector is stored in the XMP as a JSON array under
``llmind:embedding``, alongside a ``llmind:embedding_model`` attribute.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Sequence

import requests


# ── Provider defaults ─────────────────────────────────────────────────────────

EMBEDDING_DEFAULTS: dict[str, str] = {
    "ollama": "nomic-embed-text",
    "openai": "text-embedding-3-small",
    "voyage": "voyage-3.5",
    # "anthropic" routes to Voyage AI — Anthropic's recommended embedding partner.
    # Requires a Voyage API key from https://www.voyageai.com  (free tier available).
    # Your sk-ant-... Anthropic key will NOT work here.
    "anthropic": "voyage-3.5",
    "gemini": "text-embedding-004",
}


# ── Embedding generation ──────────────────────────────────────────────────────

def embed_text(
    text: str,
    provider: str = "ollama",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str = "http://localhost:11434/api/embeddings",
) -> list[float]:
    """Return a normalised embedding vector for *text*.

    Args:
        text:     The text to embed (description or query).
        provider: One of ``"ollama"``, ``"openai"``, ``"voyage"``, ``"anthropic"``,
                  ``"gemini"``.
                  ``"anthropic"`` is an alias for ``"voyage"`` — Anthropic does not
                  offer their own embedding API; they recommend Voyage AI.
                  Get a free key at https://www.voyageai.com.
                  ``"gemini"`` uses Google's text-embedding-004 model.
                  Get a free key at https://aistudio.google.com/apikey.
        model:    Override the provider default model.
        api_key:  Required for openai / voyage / anthropic providers.
        base_url: Ollama API endpoint (ignored for other providers).

    Returns:
        A list of floats (L2-normalised).

    Raises:
        ValueError: On unsupported provider or API errors.
    """
    # anthropic is an alias — routes to Voyage AI
    if provider == "anthropic":
        provider = "voyage"

    resolved = model or EMBEDDING_DEFAULTS.get(provider)
    if resolved is None:
        raise ValueError(f"Unknown embedding provider: {provider!r}")

    if provider == "ollama":
        return _embed_ollama(text, resolved, base_url)
    elif provider == "openai":
        return _embed_openai(text, resolved, api_key)
    elif provider == "voyage":
        return _embed_voyage(text, resolved, api_key)
    elif provider == "gemini":
        return _embed_gemini(text, resolved, api_key)
    else:
        raise ValueError(f"Unsupported embedding provider: {provider!r}")


def _embed_ollama(text: str, model: str, base_url: str) -> list[float]:
    import requests
    resp = requests.post(
        base_url,
        json={"model": model, "prompt": text},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    vec = data.get("embedding") or data.get("embeddings", [[]])[0]
    return _normalise(vec)


def _embed_openai(text: str, model: str, api_key: str | None) -> list[float]:
    if not api_key:
        raise ValueError("api_key is required for the openai embedding provider")
    import requests
    resp = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "input": text},
        timeout=60,
    )
    resp.raise_for_status()
    vec = resp.json()["data"][0]["embedding"]
    return _normalise(vec)


def _embed_voyage(text: str, model: str, api_key: str | None) -> list[float]:
    """Voyage AI embeddings — Anthropic's recommended embedding partner.
    
    Get a free API key at https://www.voyageai.com
    Note: this requires a Voyage API key (pa-...), NOT your Anthropic key (sk-ant-...).
    """
    if not api_key:
        raise ValueError(
            "A Voyage AI API key is required (get one free at https://voyageai.com).\n"
            "Note: your Anthropic sk-ant-... key will NOT work here — Voyage is a "
            "separate service recommended by Anthropic for embeddings."
        )
    # Try the voyageai SDK first (pip install voyageai), fall back to HTTP
    try:
        import voyageai
        client = voyageai.Client(api_key=api_key)
        result = client.embed([text], model=model, input_type="document")
        return _normalise(result.embeddings[0])
    except ImportError:
        pass

    # HTTP fallback (no extra dependency needed)
    import time
    import requests
    for attempt in range(8):
        resp = requests.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": [text], "input_type": "document"},
            timeout=60,
        )
        if resp.status_code == 429:
            wait = min(60, 5 * (2 ** attempt))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        vec = resp.json()["data"][0]["embedding"]
        time.sleep(0.5)  # throttle to stay under rate limit
        return _normalise(vec)
    resp.raise_for_status()
    return []


def _embed_gemini(text: str, model: str, api_key: str | None) -> list[float]:
    """Google Gemini embeddings via REST API.

    Uses the same GEMINI_API_KEY as the vision client.
    Get an API key at https://aistudio.google.com/apikey
    """
    if not api_key:
        import os
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is required for Gemini embeddings.\n"
            "Get a free key at https://aistudio.google.com/apikey"
        )
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
            },
            timeout=60,
        )
        resp.raise_for_status()
        vec = resp.json()["embedding"]["values"]
        return _normalise(vec)
    except Exception as exc:
        raise ValueError(f"Gemini embedding error: {exc}") from exc


# ── Similarity ────────────────────────────────────────────────────────────────

def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Return cosine similarity in [-1, 1] between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── XMP embedding patch ───────────────────────────────────────────────────────

def read_embedding_from_xmp(xmp_string: str) -> list[float] | None:
    """Extract ``llmind:embedding`` vector from an XMP string, or None."""
    import xml.etree.ElementTree as ET
    from llmind.xmp import LLMIND_NS, RDF_NS

    body = xmp_string
    if body.startswith("<?xpacket"):
        body = body[body.index("?>") + 2:]
    if body.rstrip().endswith("?>"):
        body = body[: body.rindex("<?")]

    try:
        root = ET.fromstring(body.strip())
    except ET.ParseError:
        return None

    rdf_ns = f"{{{RDF_NS}}}"
    ll_ns = f"{{{LLMIND_NS}}}"
    for elem in root.iter():
        if elem.tag == f"{rdf_ns}Description":
            raw = elem.attrib.get(f"{ll_ns}embedding")
            if raw:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
            # also check child element form
            child = elem.find(f"{ll_ns}embedding")
            if child is not None and child.text:
                try:
                    return json.loads(child.text)
                except json.JSONDecodeError:
                    return None
    return None


def patch_xmp_embedding(
    xmp_string: str,
    vector: list[float],
    model: str,
) -> str:
    """Inject / replace the ``llmind:embedding`` attribute in an XMP string.

    Works by simple string replacement on the closing ``>`` of the
    rdf:Description element rather than full re-serialisation, so the rest of
    the XMP is preserved verbatim.
    """
    import re
    from llmind.xmp import LLMIND_NS

    vec_json = json.dumps(vector, separators=(",", ":"))

    # Remove any existing embedding fields first
    xmp_string = re.sub(
        r'\s*llmind:embedding="[^"]*"', "", xmp_string
    )
    xmp_string = re.sub(
        r'\s*llmind:embedding_model="[^"]*"', "", xmp_string
    )

    # Insert before the closing > of the rdf:Description opening tag
    embed_attrs = (
        f'\n    llmind:embedding="{vec_json}"'
        f'\n    llmind:embedding_model="{model}"'
    )
    # The description tag ends with '>' and has attributes before it;
    # find the first '>' after 'rdf:Description'
    tag_start = xmp_string.find("rdf:Description")
    if tag_start == -1:
        return xmp_string  # can't patch — return as-is
    close_angle = xmp_string.index(">", tag_start)
    # Make sure we insert before the '>'
    xmp_string = xmp_string[:close_angle] + embed_attrs + xmp_string[close_angle:]
    return xmp_string


# ── Keyword scoring ───────────────────────────────────────────────────────────

def keyword_score(query: str, text: str) -> float:
    """Return a keyword relevance score in [0, 1] for *query* against *text*.

    Scoring tiers:
      1.0  — exact whole-phrase word-boundary match
      0.7  — all query words present (but not as a contiguous phrase)
      0.3–0.6 — partial word overlap (fraction of query words found)
      0.15 — substring containment for words ≥ 3 chars
      0.0  — no match
    """
    import re

    if not query or not text:
        return 0.0

    query_lower = query.lower()
    text_lower = text.lower()

    # Tier 1: exact phrase with word boundaries
    if re.search(r"\b" + re.escape(query_lower) + r"\b", text_lower):
        return 1.0

    query_words = set(query_lower.split())
    text_words = set(text_lower.split())
    if not query_words:
        return 0.0

    matched = query_words & text_words
    overlap_ratio = len(matched) / len(query_words)

    # Tier 2: all words present
    if overlap_ratio == 1.0:
        return 0.7

    # Tier 3: partial word overlap
    if overlap_ratio > 0.0:
        return 0.3 + (overlap_ratio * 0.3)

    return 0.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    if mag == 0:
        return vec
    return [x / mag for x in vec]
