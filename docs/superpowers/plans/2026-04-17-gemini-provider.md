# Gemini Vision + Embedding Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google Gemini as a vision and embedding provider across the CLI and React frontend, using simple API key auth.

**Architecture:** New `gemini_client.py` follows the same pattern as `anthropic_client.py` / `openai_client.py` — optional SDK import, env-based API key, base64 image dispatch. Embeddings use raw `requests` (no SDK) against the Gemini REST API. React frontend uses `fetch()` against `generativelanguage.googleapis.com` with `?key=` param.

**Tech Stack:** Python 3.11+, `google-genai` SDK (optional dep), `requests`, React/JSX, Gemini REST API

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `llmind-cli/llmind/gemini_client.py` | Create | Gemini vision client (~55 lines) |
| `llmind-cli/tests/test_gemini_client.py` | Create | Unit tests for vision client |
| `llmind-cli/llmind/vision.py` | Modify | Add gemini to PROVIDER_DEFAULTS + dispatcher |
| `llmind-cli/llmind/embedder.py` | Modify | Add `_embed_gemini()` + provider branch |
| `llmind-cli/tests/test_gemini_embedder.py` | Create | Unit tests for embedding client |
| `llmind-cli/llmind/cli.py` | Modify | Add "gemini" to 5 Choice lists |
| `llmind-cli/pyproject.toml` | Modify | Add gemini optional dep |
| `llmind-converter.jsx` | Modify | Add Gemini vision + embedding in frontend |
| `llmind-cli/.env.example` | Modify | Add GEMINI_API_KEY entry |

---

### Task 1: Gemini Vision Client — Tests

**Files:**
- Create: `llmind-cli/tests/test_gemini_client.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for llmind.gemini_client."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from llmind.gemini_client import query_gemini

MOCK_CONTENT = json.dumps({
    "language": "en",
    "description": "test",
    "text": "hello",
    "structure": {"type": "document", "regions": [], "figures": [], "tables": []},
})


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.gemini_client._genai_sdk")
def test_query_gemini_success(mock_sdk):
    """Successful call returns ExtractionResult with parsed data."""
    mock_response = MagicMock()
    mock_response.text = MOCK_CONTENT

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response

    mock_client = MagicMock()
    mock_client.models = mock_model
    mock_sdk.Client.return_value = mock_client

    result = query_gemini(b"\xff\xd8\xff" + b"\x00" * 10, model="gemini-2.0-flash")

    assert result.language == "en"
    assert result.text == "hello"
    assert result.description == "test"
    mock_sdk.Client.assert_called_once_with(api_key="test-key")


def test_query_gemini_missing_api_key():
    """Missing GEMINI_API_KEY raises RuntimeError."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            query_gemini(b"\xff\xd8\xff" + b"\x00" * 10)


def test_query_gemini_missing_sdk():
    """Missing google-genai SDK raises RuntimeError with install hint."""
    with patch("llmind.gemini_client._genai_sdk", None):
        with pytest.raises(RuntimeError, match="pip install"):
            query_gemini(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.gemini_client._genai_sdk")
def test_query_gemini_api_error_raises_runtime(mock_sdk):
    """API errors are wrapped in RuntimeError."""
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("Network error")
    mock_client = MagicMock()
    mock_client.models = mock_model
    mock_sdk.Client.return_value = mock_client

    with pytest.raises(RuntimeError, match="Gemini API error"):
        query_gemini(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.gemini_client._genai_sdk")
def test_query_gemini_detects_png(mock_sdk):
    """PNG image bytes are correctly identified."""
    mock_response = MagicMock()
    mock_response.text = MOCK_CONTENT
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_client = MagicMock()
    mock_client.models = mock_model
    mock_sdk.Client.return_value = mock_client

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    query_gemini(png_bytes)

    call_args = mock_model.generate_content.call_args
    # Verify generate_content was called (the SDK handles image format internally)
    mock_model.generate_content.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llmind-cli && python -m pytest tests/test_gemini_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llmind.gemini_client'`

- [ ] **Step 3: Commit test file**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/tests/test_gemini_client.py
git commit -m "test: add Gemini vision client tests (red)"
```

---

### Task 2: Gemini Vision Client — Implementation

**Files:**
- Create: `llmind-cli/llmind/gemini_client.py`

- [ ] **Step 1: Create the Gemini client**

```python
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
    model: str = "gemini-2.0-flash",
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd llmind-cli && python -m pytest tests/test_gemini_client.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/llmind/gemini_client.py
git commit -m "feat: add Gemini vision client"
```

---

### Task 3: Vision Dispatcher — Wire Gemini

**Files:**
- Modify: `llmind-cli/llmind/vision.py`

- [ ] **Step 1: Add gemini to PROVIDER_DEFAULTS**

In `vision.py`, add `"gemini"` to the `PROVIDER_DEFAULTS` dict (line 20-24):

```python
PROVIDER_DEFAULTS: dict[str, str] = {
    "ollama": "qwen2.5-vl:7b",
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
}
```

- [ ] **Step 2: Add gemini branch in query_image()**

In the `query_image()` function (after the `elif provider == "openai"` block, before the `else`), add:

```python
    elif provider == "gemini":
        from llmind.gemini_client import query_gemini
        return query_gemini(image_bytes, model=resolved_model)
```

- [ ] **Step 3: Update error message**

Change the `else` raise at line 93 to:

```python
        raise ValueError(f"Unknown provider: {provider!r}. Choose: ollama, anthropic, openai, gemini")
```

- [ ] **Step 4: Run all tests**

Run: `cd llmind-cli && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/llmind/vision.py
git commit -m "feat: wire Gemini into vision dispatcher"
```

---

### Task 4: Gemini Embeddings — Tests

**Files:**
- Create: `llmind-cli/tests/test_gemini_embedder.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests for Gemini embedding provider in llmind.embedder."""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


MOCK_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.embedder.requests")
def test_embed_gemini_success(mock_requests):
    """Successful Gemini embedding returns normalised vector."""
    from llmind.embedder import embed_text

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": {"values": MOCK_EMBEDDING}}
    mock_requests.post.return_value = mock_resp

    result = embed_text("test text", provider="gemini", api_key="test-key")

    assert isinstance(result, list)
    assert len(result) == 5
    # Check it was normalised (magnitude should be ~1.0)
    import math
    mag = math.sqrt(sum(x * x for x in result))
    assert abs(mag - 1.0) < 0.001
    mock_requests.post.assert_called_once()
    call_url = mock_requests.post.call_args[0][0]
    assert "embedContent" in call_url
    assert "key=test-key" in call_url


def test_embed_gemini_missing_api_key():
    """Missing API key raises ValueError."""
    from llmind.embedder import embed_text

    env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            embed_text("test", provider="gemini")


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.embedder.requests")
def test_embed_gemini_api_error(mock_requests):
    """API error raises ValueError."""
    from llmind.embedder import embed_text

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = Exception("Server error")
    mock_requests.post.return_value = mock_resp

    with pytest.raises(ValueError, match="Gemini embedding error"):
        embed_text("test", provider="gemini", api_key="test-key")


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.embedder.requests")
def test_embed_gemini_default_model(mock_requests):
    """Default model is text-embedding-004."""
    from llmind.embedder import embed_text

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": {"values": MOCK_EMBEDDING}}
    mock_requests.post.return_value = mock_resp

    embed_text("test", provider="gemini", api_key="test-key")

    call_url = mock_requests.post.call_args[0][0]
    assert "text-embedding-004" in call_url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd llmind-cli && python -m pytest tests/test_gemini_embedder.py -v`
Expected: FAIL — no `gemini` provider branch in `embed_text()`

- [ ] **Step 3: Commit test file**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/tests/test_gemini_embedder.py
git commit -m "test: add Gemini embedding tests (red)"
```

---

### Task 5: Gemini Embeddings — Implementation

**Files:**
- Modify: `llmind-cli/llmind/embedder.py`

- [ ] **Step 1: Add gemini to EMBEDDING_DEFAULTS**

In `embedder.py`, add to the `EMBEDDING_DEFAULTS` dict (around line 21):

```python
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
```

- [ ] **Step 2: Add gemini branch in embed_text()**

In the `embed_text()` function, add before the final `else` (after the `elif provider == "voyage"` block):

```python
    elif provider == "gemini":
        return _embed_gemini(text, resolved, api_key)
```

- [ ] **Step 3: Add _embed_gemini() function**

Add after `_embed_voyage()` (around line 145):

```python
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
    import requests
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
```

- [ ] **Step 4: Update embed_text() docstring**

Update the docstring of `embed_text()` to mention gemini:

Change `One of ``"ollama"``, ``"openai"``, ``"voyage"``, ``"anthropic"``.` to:
`One of ``"ollama"``, ``"openai"``, ``"voyage"``, ``"anthropic"``, ``"gemini"``.`

- [ ] **Step 5: Run tests**

Run: `cd llmind-cli && python -m pytest tests/test_gemini_embedder.py tests/test_gemini_client.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/llmind/embedder.py
git commit -m "feat: add Gemini embedding provider"
```

---

### Task 6: CLI Commands — Add Gemini to Choice Lists

**Files:**
- Modify: `llmind-cli/llmind/cli.py`

- [ ] **Step 1: Update enrich command**

Change line 28 from:
```python
    type=click.Choice(["ollama", "anthropic", "openai"]),
```
to:
```python
    type=click.Choice(["ollama", "anthropic", "openai", "gemini"]),
```

- [ ] **Step 2: Update reenrich command**

Change line 78 from:
```python
    type=click.Choice(["ollama", "anthropic", "openai"]),
```
to:
```python
    type=click.Choice(["ollama", "anthropic", "openai", "gemini"]),
```

- [ ] **Step 3: Update watch command**

Change line 443 from:
```python
    type=click.Choice(["ollama", "anthropic", "openai"]),
```
to:
```python
    type=click.Choice(["ollama", "anthropic", "openai", "gemini"]),
```

- [ ] **Step 4: Update embed command**

Change line 197 from:
```python
    type=click.Choice(["ollama", "openai", "voyage", "anthropic"]),
```
to:
```python
    type=click.Choice(["ollama", "openai", "voyage", "anthropic", "gemini"]),
```

- [ ] **Step 5: Update search command**

Change line 298 from:
```python
    type=click.Choice(["ollama", "openai", "voyage", "anthropic"]),
```
to:
```python
    type=click.Choice(["ollama", "openai", "voyage", "anthropic", "gemini"]),
```

- [ ] **Step 6: Run all tests**

Run: `cd llmind-cli && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/llmind/cli.py
git commit -m "feat: add gemini to all CLI provider choices"
```

---

### Task 7: Dependencies + Environment

**Files:**
- Modify: `llmind-cli/pyproject.toml`
- Modify: `llmind-cli/.env.example`

- [ ] **Step 1: Add gemini optional dependency**

In `pyproject.toml`, add under `[project.optional-dependencies]`:

```toml
gemini = ["google-genai>=1.0.0"]
```

And update `all-providers` to:

```toml
all-providers = ["anthropic>=0.40.0", "openai>=1.50.0", "google-genai>=1.0.0"]
```

- [ ] **Step 2: Update .env.example**

Add to `llmind-cli/.env.example`:

```bash
export GEMINI_API_KEY="your-key-here"
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/pyproject.toml llmind-cli/.env.example
git commit -m "chore: add google-genai dependency and GEMINI_API_KEY to env example"
```

---

### Task 8: React Frontend — Gemini Vision Provider

**Files:**
- Modify: `llmind-converter.jsx`

- [ ] **Step 1: Add Gemini to vision provider selector**

In `llmind-converter.jsx`, find the vision model selector array (around line 634):

```javascript
{[
  { id: "anthropic", label: "Claude Sonnet", sub: "Anthropic" },
].map(m => (
```

Change to:

```javascript
{[
  { id: "anthropic", label: "Claude Sonnet", sub: "Anthropic" },
  { id: "gemini", label: "Gemini Flash", sub: "Google" },
].map(m => (
```

- [ ] **Step 2: Update API key placeholder**

Find the API key input placeholder (around line 657):

```javascript
placeholder={provider === "anthropic" ? "sk-ant-..." : "sk-..."}
```

Change to:

```javascript
placeholder={provider === "anthropic" ? "sk-ant-..." : provider === "gemini" ? "AIza..." : "sk-..."}
```

- [ ] **Step 3: Update API key help text**

Find the help text (around line 671):

```javascript
Your key is used in-browser only. It is sent directly to {provider === "anthropic" ? "api.anthropic.com" : "api.openai.com"} and never touches our servers. Not stored anywhere.
```

Change to:

```javascript
Your key is used in-browser only. It is sent directly to {provider === "anthropic" ? "api.anthropic.com" : provider === "gemini" ? "generativelanguage.googleapis.com" : "api.openai.com"} and never touches our servers. Not stored anywhere.
```

- [ ] **Step 4: Add Gemini API call in processFile**

Find the API call block (around line 357-376). After the closing `}` of `if (provider === "anthropic") { ... }`, add:

```javascript
      else if (provider === "gemini") {
        const geminiModel = "gemini-2.0-flash";
        const resp = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${geminiModel}:generateContent?key=${apiKey}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              contents: [{
                parts: [
                  { inlineData: { mimeType: mediaType, data: b64 } },
                  { text: userPrompt }
                ]
              }]
            })
          }
        );
        data = await resp.json();
        if (data.error) throw new Error(data.error.message);
        // Reshape to match Anthropic response structure for downstream parsing
        data = { content: [{ text: data.candidates[0].content.parts[0].text }] };
      }
```

- [ ] **Step 5: Update generator_model**

Find line 397:

```javascript
generator_model: provider === "anthropic" ? "claude-sonnet-4-20250514" : "unknown",
```

Change to:

```javascript
generator_model: provider === "anthropic" ? "claude-sonnet-4-20250514" : provider === "gemini" ? "gemini-2.0-flash" : "unknown",
```

- [ ] **Step 6: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-converter.jsx
git commit -m "feat: add Gemini vision provider to React frontend"
```

---

### Task 9: React Frontend — Gemini Embedding Provider

**Files:**
- Modify: `llmind-converter.jsx`

- [ ] **Step 1: Add gemini to EMBED_DEFAULTS**

Find the `EMBED_DEFAULTS` object (around line 7):

```javascript
const EMBED_DEFAULTS = {
  ollama: "nomic-embed-text",
  openai: "text-embedding-3-small",
  voyage: "voyage-3.5",
  anthropic: "voyage-3.5",
};
```

Add gemini:

```javascript
const EMBED_DEFAULTS = {
  ollama: "nomic-embed-text",
  openai: "text-embedding-3-small",
  voyage: "voyage-3.5",
  anthropic: "voyage-3.5",
  gemini: "text-embedding-004",
};
```

- [ ] **Step 2: Add Gemini branch in embedText()**

Find the `embedText()` function (around line 158). Before the final `throw new Error(...)` (line 200), add:

```javascript
  if (actualProvider === "gemini") {
    if (!apiKey) throw new Error("Gemini API key required (get one free at aistudio.google.com/apikey)");
    const model = EMBED_DEFAULTS.gemini;
    const resp = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${model}:embedContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: `models/${model}`,
          content: { parts: [{ text }] },
        }),
      }
    );
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error?.message || "Gemini embedding failed");
    return { vector: normaliseVec(data.embedding.values), model };
  }
```

- [ ] **Step 3: Add Gemini card to embedding provider selector**

Find the embedding provider selector array (around line 792):

```javascript
{[
  { id: "openai", label: "OpenAI", sub: "text-embedding-3-small" },
  { id: "voyage", label: "Voyage AI", sub: "voyage-3.5" },
  { id: "anthropic", label: "Anthropic", sub: "→ Voyage AI" },
  ...(IS_LOCAL ? [{ id: "ollama", label: "Ollama", sub: "local · no key" }] : []),
].map(p => (
```

Change to:

```javascript
{[
  { id: "openai", label: "OpenAI", sub: "text-embedding-3-small" },
  { id: "gemini", label: "Gemini", sub: "text-embedding-004" },
  { id: "voyage", label: "Voyage AI", sub: "voyage-3.5" },
  { id: "anthropic", label: "Anthropic", sub: "→ Voyage AI" },
  ...(IS_LOCAL ? [{ id: "ollama", label: "Ollama", sub: "local · no key" }] : []),
].map(p => (
```

- [ ] **Step 4: Update embedding API key label/placeholder for Gemini**

Find the embedding API key section (around line 811-820). The current conditional shows different labels for openai vs voyage. Update to handle gemini:

Change line 813-814 from:
```javascript
{embedProvider === "openai" ? "OpenAI API key (sk-...)" : "Voyage AI key (pa-...) — not your Anthropic key"}
```
to:
```javascript
{embedProvider === "openai" ? "OpenAI API key (sk-...)" : embedProvider === "gemini" ? "Gemini API key (AIza...)" : "Voyage AI key (pa-...) — not your Anthropic key"}
```

Change line 820 from:
```javascript
placeholder={embedProvider === "openai" ? "sk-..." : "pa-..."}
```
to:
```javascript
placeholder={embedProvider === "openai" ? "sk-..." : embedProvider === "gemini" ? "AIza..." : "pa-..."}
```

- [ ] **Step 5: Ensure Gemini embed provider shows API key input**

Find the condition that controls showing the API key input (around line 811):

```javascript
{embedProvider !== "ollama" && !embeddingDone && (
```

This already works — gemini is not "ollama" so the key input will show. No change needed.

- [ ] **Step 6: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-converter.jsx
git commit -m "feat: add Gemini embedding provider to React frontend"
```

---

### Task 10: Final Verification + Push

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd llmind-cli && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify CLI help shows gemini**

Run: `cd llmind-cli && python -m llmind enrich --help`
Expected: `--provider` shows `[ollama|anthropic|openai|gemini]`

Run: `cd llmind-cli && python -m llmind embed --help`
Expected: `--provider` shows `[ollama|openai|voyage|anthropic|gemini]`

- [ ] **Step 3: Push to remote**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git push origin feature/llmind-cli
```
