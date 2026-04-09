# LLMind CLI — Design Spec

**Date:** 2026-04-09
**Branch:** feature/llmind-cli
**Status:** Approved

---

## Overview

A Python CLI tool (`llmind`) that enriches JPEG, PNG, and PDF files with a semantic XMP metadata layer. Uses a local Ollama vision model (`qwen2.5-vl:7b` by default) instead of a cloud API. Produces the same XMP format and cryptographic conventions as the existing browser-based LLMind React app.

The enriched file opens normally in any viewer. The metadata is invisible to humans but fully readable by any LLM pipeline that knows the `llmind:` XMP namespace.

---

## Approach

**Approach B — Proper package, synchronous I/O.**

- `pyproject.toml` with `[project.scripts] llmind = "llmind.cli:main"`
- `pipx install .` gives a global `llmind` command
- Synchronous Ollama calls — the bottleneck is the local GPU, not I/O; async adds complexity with no throughput benefit
- 9 modules + `safety.py`, all independently testable

---

## Architecture

### Module Layout

```
llmind-cli/                  # repo subdirectory (alongside React app)
├── pyproject.toml
├── README-cli.md
├── llmind/
│   ├── __init__.py          # version = "0.1.0"
│   ├── cli.py               # Click entry point — commands, flags, Rich output
│   ├── enricher.py          # Orchestrates enrichment pipeline
│   ├── injector.py          # XMP byte injection per format
│   ├── reader.py            # Reads LLMind XMP layer from file
│   ├── verifier.py          # Checksum + HMAC signature verification
│   ├── watcher.py           # watchdog integration, watch modes
│   ├── crypto.py            # Key generation, HMAC-SHA256, SHA-256
│   ├── xmp.py               # Build and parse XMP XML strings
│   ├── ollama.py            # Ollama HTTP client with retry
│   ├── models.py            # Frozen dataclasses: Layer, KeyFile, LLMindMeta, etc.
│   └── safety.py            # is_safe_file() — system/hidden file guard
└── tests/
    ├── conftest.py
    ├── test_crypto.py
    ├── test_xmp.py
    ├── test_injector.py
    ├── test_reader.py
    ├── test_verifier.py
    ├── test_enricher.py
    ├── test_safety.py
    └── test_cli.py
```

### Module Responsibilities

| Module | Responsibility | Knows about |
|--------|---------------|-------------|
| `cli.py` | Commands, flags, Rich output formatting | All modules |
| `enricher.py` | Orchestrate enrichment pipeline | ollama, crypto, xmp, injector, reader, safety |
| `injector.py` | Inject/remove XMP bytes in file formats | File bytes only, not LLMind semantics |
| `reader.py` | Extract LLMind XMP from file | File bytes, xmp, models |
| `verifier.py` | Checksum and signature checks | crypto, reader, models |
| `watcher.py` | watchdog events, debounce, watch modes | enricher, safety |
| `crypto.py` | Key gen, HMAC, SHA-256, key_id | stdlib only |
| `xmp.py` | Build XML string, parse XML string | models |
| `ollama.py` | HTTP calls to Ollama, retry, base64 | requests, models |
| `models.py` | Data structures | stdlib only |
| `safety.py` | File safety predicate | pathlib only |

**Key boundary rule:** `injector.py` knows nothing about LLMind semantics. `xmp.py` knows nothing about files. Each unit is independently testable.

### Data Flow — `enrich`

```
cli.py
  └─► enricher.enrich_file(path, opts)
        ├─► safety.is_safe_file()           # guard — skip hidden/system files
        ├─► crypto.sha256_file()            # checksum raw bytes
        ├─► reader.is_fresh(path, checksum) # skip if layer exists + checksum matches + no --force
        ├─► ollama.extract(path, model)     # vision call(s) → ExtractionResult
        ├─► crypto.generate_key()           # 256-bit creation key (v1 only)
        ├─► crypto.sign_layer()             # HMAC-SHA256(key, JSON)
        ├─► xmp.build_xmp()                # XML string
        ├─► injector.inject(path, xmp)     # format-specific byte injection
        └─► crypto.save_key_file()         # .llmind-keys/<filename>.key
```

---

## Data Models (`models.py`)

All frozen dataclasses (immutable):

```python
@dataclass(frozen=True)
class ExtractionResult:
    language: str
    description: str
    text: str
    structure: dict          # mutable field — do not reassign or mutate in place

@dataclass(frozen=True)
class Layer:
    version: int
    timestamp: str           # ISO 8601 UTC
    generator: str           # "llmind-cli/0.1"
    generator_model: str
    checksum: str            # SHA-256 hex of original file bytes
    language: str
    description: str
    text: str
    structure: dict
    signature: str | None    # None if unsigned (v2+ without --key)
    key_id: str              # first 16 hex chars of SHA-256(creation_key)

@dataclass(frozen=True)
class KeyFile:
    key_id: str
    creation_key: str        # 64 hex chars (256-bit)
    created: str             # ISO 8601
    file: str                # original filename
    note: str                # "Required to modify or delete layers. Not recoverable."

@dataclass(frozen=True)
class LLMindMeta:
    layers: list[Layer]      # full history, index 0 = v1
    current: Layer           # layers[-1]
    layer_count: int
    immutable: bool
```

---

## Enrichment Pipeline

### Single File

1. `safety.is_safe_file()` — abort if hidden, system, or unsupported
2. Read raw bytes → `crypto.sha256_file()` → checksum
3. `reader.is_fresh(path, checksum)` — skip if layer exists + checksum matches (unless `--force`)
4. Detect append mode: existing layer present + `--key` provided → v2+, else new enrichment
5. `ollama.extract()` → `ExtractionResult`
6. Build `Layer`, sign with `crypto.sign_layer()`
7. `xmp.build_xmp()` → XML string
8. `injector.inject()` → write enriched file
9. `crypto.save_key_file()` → `.llmind-keys/<filename>.key`

### Multi-Page PDF

- Convert each page to image via `pdf2image`
- Send each page image to Ollama separately
- Merge results:
  - `description`: joined per-page descriptions
  - `text`: joined with `═══ PAGE N ═══` separators
  - `structure`: `{"type": "...", "pages": [...], "regions": [...]}` — completeness over speed
  - `language`: union of all detected ISO codes
- Single `Layer` written to file

### Directory Enrichment

- Walk files (optionally `--recursive`)
- Filter via `safety.is_safe_file()`
- Rich progress bar: `[1/47] beach_sunset.jpg ........ ✓ 12 regions (4.2s)`
- Skip errors gracefully, continue batch
- Summary table at end: files enriched, skipped, errors, total overhead
- Keys saved to `<dir>/.llmind-keys/`

### Ollama Client (`ollama.py`)

- Endpoint: `POST {ollama_url}/api/chat`
- Payload: base64-encoded file in `images` array, extraction prompt in `content`
- `stream: false`, `temperature: 0.1`, `num_predict: 8000`
- Retry: 3× with exponential backoff (1s, 2s, 4s)
- On malformed JSON from model: retry once with stricter prompt, then skip with warning
- Raises `OllamaConnectionError` after exhausted retries

---

## Per-Format XMP Injection (`injector.py`)

Pure byte manipulation — no LLMind semantics.

### JPEG
- Scan existing APP1 markers for XMP namespace `http://ns.adobe.com/xap/1.0/\0`
- Remove existing LLMind XMP if present (handles re-enrichment cleanly)
- Insert new APP1 block at offset 2 (after SOI `FF D8`)
- Format: `FF E1` + 2-byte big-endian length + namespace + XMP bytes
- All other markers (EXIF, ICC, APP0, etc.) untouched

### PNG
- Find end of IHDR chunk
- Remove existing `iTXt` chunk with keyword `XML:com.adobe.xmp` if present
- Insert new `iTXt` chunk after IHDR
- Compute CRC32 over chunk type + data
- All other chunks untouched

### PDF
- `pikepdf.open()` → replace `pdf.Root["/Metadata"]` stream
- Set `/Type /Metadata` and `/Subtype /XML`
- `pdf.save(output_path)` — pikepdf handles cross-references
- Original page content untouched

### Reader (`reader.py`)

- JPEG: walk APP1 markers → find XMP namespace → extract XML
- PNG: walk chunks → find `iTXt` with `XML:com.adobe.xmp` keyword
- PDF: `pdf.Root["/Metadata"]` stream → decode → parse XML
- Parse via `xml.etree.ElementTree` (stdlib)
- `has_llmind_layer(path) → bool` — lightweight check, returns True if `llmind:version` present

---

## CLI Commands & Flags

```
llmind enrich <path>
    --recursive, -r
    --model, -m          (default: qwen2.5-vl:7b)
    --ollama-url         (default: http://localhost:11434)
    --key <path>         (for appending v2+ layers)
    --force
    --dry-run
    --output-dir <path>
    --verbose, -v
    --quiet, -q

llmind read <file>
    --format [text|json|yaml]   (default: text)

llmind verify <path>
    --recursive, -r
    --key <path>
    --verbose, -v

llmind strip <file>
    --key <path>         (required — must match file's llmind:key_id)

llmind watch <directory>
    --mode [new|backfill|existing]   (default: new)
    --recursive, -r
    --model, -m
    --ollama-url
    --log-file <path>
    --verbose, -v

llmind history <file>
    --format [text|json|yaml]   (default: text)
```

### Strip Command

1. Load key file from `--key <path>`
2. Read `llmind:key_id` from file
3. Verify `key_id` matches — abort with error if mismatch
4. Remove LLMind XMP block via injector, write cleaned file in-place
5. Print original vs. stripped file sizes

---

## Watch Mode (`watcher.py`)

| `--mode` | Behavior |
|----------|----------|
| `new` (default) | Start watchdog only; skip all pre-existing files |
| `backfill` | Run `enrich_directory()` first, then start watchdog |
| `existing` | Run `enrich_directory()` only, no watchdog |

- watchdog `FileCreatedEvent` + `FileModifiedEvent` (with 2s debounce — editors write in multiple flushes)
- Re-checks `is_safe_file()` on each event
- Graceful shutdown on `Ctrl+C` — finishes current file before exiting
- Optional `--log-file` for persistent activity log

---

## Safety Filter (`safety.py`)

`is_safe_file(path: Path) -> bool` — returns False if any condition:

- Filename starts with `.`
- Any path component starts with `.` (hidden directory)
- Filename in blocklist: `Thumbs.db`, `desktop.ini`, `.DS_Store`, `Icon\r`
- Extension not in `{.jpg, .jpeg, .png, .pdf}`
- Path contains `.llmind-keys` component
- File is a symlink
- File size is 0 bytes

---

## Cryptography (`crypto.py`)

All stdlib (`hashlib`, `hmac`, `secrets`, `json`):

| Function | Implementation |
|----------|---------------|
| `generate_key()` | `secrets.token_hex(32)` — 256-bit hex string |
| `key_id(key)` | `sha256(key.encode())[:16]` — first 16 hex chars |
| `sha256_file(path)` | `hashlib.sha256(bytes).hexdigest()` |
| `sign_layer(key, layer)` | `hmac.new(key, JSON.dumps(layer, sort_keys=True), sha256).hexdigest()` |
| `verify_signature(key, layer)` | Re-derive and compare in constant time |
| `save_key_file(path, keyfile)` | Write JSON to `.llmind-keys/<filename>.key` |

Keys are never stored inside the file — only `key_id` (fingerprint) is embedded in XMP.

---

## XMP Format (`xmp.py`)

```xml
<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
      xmlns:llmind="https://llmind.org/ns/1.0/"
      llmind:version="1"
      llmind:format_version="1.0"
      llmind:generator="llmind-cli/0.1"
      llmind:generator_model="qwen2.5-vl:7b"
      llmind:timestamp="2026-04-09T13:00:00Z"
      llmind:language="en"
      llmind:checksum="sha256hex..."
      llmind:key_id="first16hexchars"
      llmind:signature="hmac-sha256hex..."
      llmind:layer_count="1"
      llmind:immutable="true"
    >
      <llmind:description>XML-escaped description</llmind:description>
      <llmind:text>XML-escaped full extracted text</llmind:text>
      <llmind:structure>XML-escaped JSON string of structure</llmind:structure>
      <llmind:history>XML-escaped JSON array of all layers</llmind:history>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
```

All string values XML-escaped: `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`, `"` → `&quot;`

---

## Packaging

```toml
[project]
name = "llmind-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pillow>=10.0",
    "pikepdf>=8.0",
    "watchdog>=3.0",
    "requests>=2.31",
    "pdf2image>=1.16",
    "rich>=13.0"
]

[project.scripts]
llmind = "llmind.cli:main"

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov>=4.0", "responses>=0.23"]
```

**Install:**
```bash
pipx install .        # global llmind command
pip install -e .      # editable dev install
```

---

## Testing

Target: **80%+ coverage** via `pytest-cov`

| Test file | Approach |
|-----------|----------|
| `test_crypto.py` | Pure unit tests — deterministic inputs/outputs |
| `test_xmp.py` | Build → parse round-trip, XML-escape edge cases |
| `test_injector.py` | Inject into minimal real JPEG/PNG/PDF fixtures → read back → assert round-trip |
| `test_reader.py` | Parse known XMP bytes → assert `LLMindMeta` fields |
| `test_verifier.py` | Fresh file → valid; modified file → stale; wrong key → invalid |
| `test_enricher.py` | Mock `ollama.extract()` via `responses` — assert layer built, key saved, checksum correct |
| `test_safety.py` | Parametrized: hidden files, system files, symlinks, zero-byte files, valid files |
| `test_cli.py` | Click `CliRunner` for all commands — `tmp_path` fixtures, no real file system side effects |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Ollama not running | `OllamaConnectionError` after 3 retries — warn, skip file, continue batch |
| Malformed JSON from model | Retry once with stricter prompt, then skip with warning |
| File permission error | Skip with warning, continue batch |
| Unsupported file type | Caught by `safety.is_safe_file()` — skip silently |
| Wrong key on strip | Abort immediately with clear error message |
| Zero-byte file | Caught by `safety.is_safe_file()` — skip silently |
| PDF conversion failure (poppler missing) | Clear error message with install instructions |

---

## Key File Location

- In-place enrichment: `<same_dir>/.llmind-keys/<filename>.key`
- `--output-dir` mode: `<output_dir>/.llmind-keys/<filename>.key`
- Watch mode: same as in-place per file
- `.llmind-keys/` is added to `.gitignore` automatically on first write
