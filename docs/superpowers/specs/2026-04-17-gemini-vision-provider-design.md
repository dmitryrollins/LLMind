# Gemini Vision Provider — Design Spec

**Date:** 2026-04-17
**Status:** Approved
**Scope:** Add Google Gemini as a vision provider across CLI, React frontend

---

## Goal

Add Google Gemini as a fourth vision provider for text extraction, alongside Anthropic, OpenAI, and Ollama. All Gemini models available; default is `gemini-2.0-flash`. Auth via simple `GEMINI_API_KEY` — no OAuth or Google sign-in required.

## Motivation

Google Gemini models perform well on text-heavy documents (receipts, contracts, forms). Adding Gemini gives users another high-quality option, especially for text extraction tasks.

---

## 1. CLI — `gemini_client.py` (new file)

**Path:** `llmind-cli/llmind/gemini_client.py`

Follow the exact pattern of `anthropic_client.py`:

- Optional import of `google-genai` SDK (`google.genai`)
- If not installed, raise `RuntimeError` with install instructions
- Read `GEMINI_API_KEY` from environment
- Accept `image_bytes: bytes` and `model: str` parameters
- Detect media type via `_detect_media_type()`
- Send base64 image + `EXTRACTION_PROMPT` to Gemini `generateContent` API
- Parse response text through `_parse_response()`
- Return `ExtractionResult`

**Error handling:** Wrap API call in try/except, raise `RuntimeError(f"Gemini API error: {exc}")`.

## 2. CLI — Vision dispatcher (`vision.py`)

- Add to `PROVIDER_DEFAULTS`: `"gemini": "gemini-2.0-flash"`
- Add `elif provider == "gemini"` branch in `query_image()`:
  ```python
  elif provider == "gemini":
      from llmind.gemini_client import query_gemini
      return query_gemini(image_bytes, model=resolved_model)
  ```
- Update error message to include `gemini` in the list of valid providers

## 3. CLI — Commands (`cli.py`)

Add `"gemini"` to `click.Choice` lists in these 3 commands:

- `enrich` — `type=click.Choice(["ollama", "anthropic", "openai", "gemini"])`
- `reenrich` — same
- `watch` — same

No changes to `embed`, `search`, `read`, `verify`, `strip`, `history` (they don't use vision providers).

## 4. CLI — Dependencies (`pyproject.toml`)

```toml
[project.optional-dependencies]
gemini = ["google-genai>=1.0.0"]
all-providers = ["anthropic>=0.40.0", "openai>=1.50.0", "google-genai>=1.0.0"]
```

## 5. React Frontend (`llmind-converter.jsx`)

### Provider selector

Add a fourth card to the vision provider selector:

```javascript
{ id: "gemini", label: "Gemini Flash", sub: "Google" }
```

### API key input

When `provider === "gemini"`:
- Placeholder: `"AIza..."`
- Help text: "Your key is used in-browser only. It is sent directly to generativelanguage.googleapis.com and never touches our servers. Not stored anywhere."

### API call

Direct REST call (no SDK in browser):

```
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={apiKey}
Content-Type: application/json

{
  "contents": [{
    "parts": [
      { "inlineData": { "mimeType": "{mediaType}", "data": "{base64}" } },
      { "text": "{EXTRACTION_PROMPT}" }
    ]
  }]
}
```

Default model in frontend: `gemini-2.0-flash`.

### Response parsing

Extract text from Gemini response structure:
```javascript
const text = response.candidates[0].content.parts[0].text;
// Then parse JSON same as other providers
```

Set `generator_model` to the selected Gemini model name.

## 6. Environment

- Add `GEMINI_API_KEY=` to `.env.example` (CLI)
- No changes to `.env` (user adds their own key)
- No changes to FastAPI backend (does not perform vision extraction)

## 7. Files Changed

| File | Change |
|------|--------|
| `llmind-cli/llmind/gemini_client.py` | **New** — Gemini vision client (~55 lines) |
| `llmind-cli/llmind/vision.py` | Add gemini to defaults + dispatcher |
| `llmind-cli/llmind/cli.py` | Add "gemini" to 3 Choice lists |
| `llmind-cli/pyproject.toml` | Add gemini optional dep |
| `llmind-converter.jsx` | Add Gemini provider card + API call |
| `.env.example` (if exists) | Add GEMINI_API_KEY entry |

## 8. Not in scope

- Gemini embeddings (existing embedding providers are sufficient)
- Google Cloud / Vertex AI auth
- Gemini-specific prompt tuning (use same `EXTRACTION_PROMPT`)
- FastAPI backend changes
