# LLMind — File Enrichment Engine

> Embed a semantic intelligence layer inside standard files. The file stays normal. The metadata makes it machine-readable.

---

## What it does

LLMind takes a standard **JPEG, PNG, PDF, MP3, WAV, or M4A** file and enriches it with a structured metadata layer containing:

- **Extracted text** — every word, badge, watermark, label (images/PDF) or spoken-word transcript (audio)
- **Visual description** or **audio summary** — natural-language description
- **Document structure** (image/PDF) or **timestamped segments** (audio) — mapped as JSON

All of this is embedded as **XMP metadata** directly inside the file's binary — no external database, no sidecar file. The enriched file opens normally in any viewer or editor.

---

## How it works

1. **Upload** a JPEG, PNG, or PDF
2. **Configure** your Anthropic API key (used in-browser only, never stored)
3. **Convert** — the file is analyzed by Claude's vision model
4. **Download** the enriched `.llmind` file and your creation key

---

## Audio support (CLI-only)

Audio files are transcribed and enriched with:

- Full transcript (`llmind:text`)
- 1–2 sentence summary (`llmind:description`)
- Timestamped segments (`llmind:segments`)
- Duration in seconds (`llmind:duration_seconds`)
- Media type marker (`llmind:media_type="audio"`)

Supported providers: OpenAI Whisper, Gemini, local `faster-whisper`.
Install the local provider with: `pip install -e .[whisper-local]`.

---

## Install the CLI

The CLI ships as a Python package. Install it with `pipx` (recommended) or
`uv` — both put it on your `PATH` in an isolated environment without touching
your system Python.

> **Requires** Python 3.11+. PDF rendering also needs `poppler-utils` on your
> system (`brew install poppler` on macOS, `apt install poppler-utils` on
> Debian/Ubuntu). Image and audio support work out of the box.

### Pick the providers you want

The core install handles file I/O, signing, and metadata. Cloud and local
backends are opt-in extras so you only pull in what you'll use:

| Extra            | What you get                                  |
| ---------------- | --------------------------------------------- |
| `anthropic`      | Claude vision (recommended default)           |
| `openai`         | GPT-4o vision + Whisper transcription         |
| `gemini`         | Gemini 2.0 vision + audio                     |
| `whisper-local`  | Offline Whisper via `faster-whisper`          |
| `embeddings`     | VoyageAI embeddings for semantic search       |
| `all`            | Everything above                              |

### With pipx

```bash
# install pipx if you don't have it: brew install pipx && pipx ensurepath
pipx install 'llmind-cli[anthropic]'
```

### With uv

```bash
# install uv if you don't have it: brew install uv
uv tool install 'llmind-cli[anthropic]'
```

Combine extras with commas — e.g. `'llmind-cli[anthropic,whisper-local]'` — or
use `[all]` for everything.

### From source (development)

```bash
cd llmind-cli
pip install -e '.[all,dev]'
```

---

## Key features

- **Immutable layer history** — every enrichment is a version. Nothing is overwritten. Previous layers cannot be modified without the creation key.
- **HMAC-SHA256 signing** — each layer is cryptographically signed. Tamper-evident by design.
- **SHA-256 checksum** — binds the metadata to the exact file content. A changed file = invalid layer.
- **In-browser only** — your API key is sent directly to `api.anthropic.com` and is never stored anywhere.
- **Zero backend** — pure client-side React app. No server processes your files.

---

## Tech stack

- **React + Vite** — frontend framework and build tool
- **Web Crypto API** — key generation, HMAC signing, SHA-256 hashing
- **Anthropic Claude** — vision model for text extraction and description
- **XMP** — metadata standard for JPEG (APP1), PNG (iTXt), and PDF injection

---

## Deployment

Deployed via [Railway](https://railway.app). The app is a static build served by `vite preview`.

```bash
npm install
npm run build
npm run preview
```

---

## Detecting an LLMind layer

Read the file's XMP metadata and look for the `llmind:version` field in namespace `https://llmind.org/ns/1.0/`.

```xml
<rdf:Description rdf:about=""
  xmlns:llmind="https://llmind.org/ns/1.0/"
  llmind:version="1"
  llmind:checksum="abc123..."
  llmind:signature="..."
  llmind:key_id="...">
  <llmind:text>All extracted text...</llmind:text>
  <llmind:description>Visual description...</llmind:description>
  <llmind:structure>{"type":"document",...}</llmind:structure>
</rdf:Description>
```

If `llmind:signature` validates and `llmind:checksum` matches the file hash — the layer is authentic and fresh. Skip OCR and vision inference entirely.

---

## License

MIT
