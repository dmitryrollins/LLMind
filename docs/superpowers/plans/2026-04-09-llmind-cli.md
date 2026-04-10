# LLMind CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `pipx`-installable Python CLI that enriches JPEG/PNG/PDF files with signed XMP metadata using a local Ollama vision model.

**Architecture:** Approach B — proper package with `pyproject.toml`, synchronous I/O, 10 focused modules. `cli.py` owns all user-facing output; `enricher.py` orchestrates the pipeline; `injector.py` and `reader.py` are pure byte-manipulation units with no LLMind semantics.

**Tech Stack:** Python 3.11+, Click, Pillow, pikepdf, watchdog, requests, pdf2image, Rich, pytest, responses

---

## File Map

| File | Role |
|------|------|
| `llmind-cli/pyproject.toml` | Package metadata, entry point, dependencies |
| `llmind-cli/llmind/__init__.py` | `__version__ = "0.1.0"` |
| `llmind-cli/llmind/models.py` | Frozen dataclasses: Layer, KeyFile, LLMindMeta, ExtractionResult, EnrichResult, VerifyResult |
| `llmind-cli/llmind/safety.py` | `is_safe_file(path) -> bool` |
| `llmind-cli/llmind/crypto.py` | Key gen, HMAC-SHA256, SHA-256, key_id derivation, key file I/O |
| `llmind-cli/llmind/xmp.py` | `build_xmp()` → XML string; `parse_xmp()` → LLMindMeta; `layer_to_dict()` |
| `llmind-cli/llmind/injector.py` | `inject(src, xmp, out)` and `remove_llmind_xmp(src, out)` — JPEG/PNG/PDF |
| `llmind-cli/llmind/reader.py` | `read_llmind_meta()`, `has_llmind_layer()`, `is_fresh()` — JPEG/PNG/PDF |
| `llmind-cli/llmind/ollama.py` | HTTP client, retry logic, PDF multi-page merge |
| `llmind-cli/llmind/enricher.py` | `enrich_file()`, `enrich_directory()` |
| `llmind-cli/llmind/verifier.py` | `verify_file()`, `verify_directory()` |
| `llmind-cli/llmind/watcher.py` | watchdog integration, three watch modes |
| `llmind-cli/llmind/cli.py` | Click group: enrich, read, verify, strip, watch, history |
| `llmind-cli/tests/conftest.py` | Shared fixtures: minimal JPEG/PNG/PDF files, sample Layer |
| `llmind-cli/tests/test_models.py` | Dataclass instantiation, frozen enforcement |
| `llmind-cli/tests/test_safety.py` | Parametrized safe/unsafe path cases |
| `llmind-cli/tests/test_crypto.py` | Key gen, sign, verify, sha256, key_id |
| `llmind-cli/tests/test_xmp.py` | build → parse round-trip, XML-escape edge cases |
| `llmind-cli/tests/test_injector.py` | Inject → read round-trip for each format |
| `llmind-cli/tests/test_reader.py` | is_fresh, has_llmind_layer, read_llmind_meta |
| `llmind-cli/tests/test_ollama.py` | Mocked HTTP: success, retry, JSON retry, PDF merge |
| `llmind-cli/tests/test_enricher.py` | Mocked ollama.extract, asserts layer/key written |
| `llmind-cli/tests/test_verifier.py` | Fresh/stale/wrong-key scenarios |
| `llmind-cli/tests/test_watcher.py` | Mode logic unit tests |
| `llmind-cli/tests/test_cli.py` | Click CliRunner for all commands |

---

## Task 1: Project Scaffold

**Files:**
- Create: `llmind-cli/pyproject.toml`
- Create: `llmind-cli/llmind/__init__.py`
- Create: `llmind-cli/llmind/cli.py` (stub)
- Create: `llmind-cli/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
mkdir -p llmind-cli/llmind
mkdir -p llmind-cli/tests
touch llmind-cli/tests/__init__.py
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
# llmind-cli/pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

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
    "rich>=13.0",
    "pyyaml>=6.0",
]

[project.scripts]
llmind = "llmind.cli:main"

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov>=4.0", "responses>=0.23"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Write `llmind/__init__.py`**

```python
# llmind-cli/llmind/__init__.py
__version__ = "0.1.0"
```

- [ ] **Step 4: Write CLI stub so the entry point resolves**

```python
# llmind-cli/llmind/cli.py
import click


@click.group()
@click.version_option()
def main() -> None:
    """LLMind — semantic file enrichment engine."""
    pass
```

- [ ] **Step 5: Install in editable mode**

```bash
cd llmind-cli
pip install -e ".[dev]"
```

Expected: `Successfully installed llmind-cli-0.1.0`

- [ ] **Step 6: Verify entry point works**

```bash
llmind --version
```

Expected: `llmind-cli, version 0.1.0`

- [ ] **Step 7: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/
git commit -m "feat: scaffold llmind-cli package"
```

---

## Task 2: Data Models

**Files:**
- Create: `llmind-cli/llmind/models.py`
- Create: `llmind-cli/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# llmind-cli/tests/test_models.py
import pytest
from llmind.models import ExtractionResult, KeyFile, Layer, LLMindMeta


def test_layer_instantiation():
    layer = Layer(
        version=1,
        timestamp="2026-04-09T12:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum="a" * 64,
        language="en",
        description="A test image",
        text="Hello world",
        structure={"type": "test", "regions": [], "figures": [], "tables": []},
        key_id="abcdef1234567890",
    )
    assert layer.version == 1
    assert layer.signature is None


def test_layer_is_frozen():
    layer = Layer(
        version=1, timestamp="t", generator="g", generator_model="m",
        checksum="c" * 64, language="en", description="d", text="t",
        structure={}, key_id="k",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        layer.version = 2  # type: ignore


def test_key_file_has_default_note():
    kf = KeyFile(
        key_id="abc", creation_key="k" * 64,
        created="2026-04-09T12:00:00Z", file="photo.jpg",
    )
    assert "Not recoverable" in kf.note


def test_llmind_meta_current_is_last_layer():
    layer1 = Layer(version=1, timestamp="t", generator="g", generator_model="m",
                   checksum="c" * 64, language="en", description="d", text="t",
                   structure={}, key_id="k")
    layer2 = Layer(version=2, timestamp="t", generator="g", generator_model="m",
                   checksum="c" * 64, language="en", description="d2", text="t2",
                   structure={}, key_id="k")
    meta = LLMindMeta(layers=(layer1, layer2), current=layer2, layer_count=2, immutable=True)
    assert meta.current.version == 2
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd llmind-cli && pytest tests/test_models.py -v
```

Expected: `ImportError: cannot import name 'Layer' from 'llmind.models'`

- [ ] **Step 3: Write `models.py`**

```python
# llmind-cli/llmind/models.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple
from pathlib import Path


@dataclass(frozen=True)
class ExtractionResult:
    language: str
    description: str
    text: str
    structure: dict  # mutable — do not mutate in place


@dataclass(frozen=True)
class Layer:
    version: int
    timestamp: str          # ISO 8601 UTC
    generator: str          # "llmind-cli/0.1.0"
    generator_model: str
    checksum: str           # SHA-256 hex of original file bytes
    language: str
    description: str
    text: str
    structure: dict         # mutable — do not mutate in place
    key_id: str             # first 16 hex chars of SHA-256(creation_key)
    signature: str | None = None  # HMAC-SHA256; None if unsigned


@dataclass(frozen=True)
class KeyFile:
    key_id: str
    creation_key: str       # 64 hex chars (256-bit)
    created: str            # ISO 8601
    file: str               # original filename
    note: str = "Required to modify or delete layers. Not recoverable."


@dataclass(frozen=True)
class LLMindMeta:
    layers: tuple[Layer, ...]   # full history; index 0 = v1
    current: Layer              # layers[-1]
    layer_count: int
    immutable: bool


class EnrichResult(NamedTuple):
    path: Path
    success: bool
    skipped: bool
    version: int | None
    regions: int
    figures: int
    tables: int
    elapsed: float
    error: str | None


class VerifyResult(NamedTuple):
    path: Path
    has_layer: bool
    checksum_valid: bool
    signature_valid: bool | None   # None if no key provided
    layer_count: int
    current_version: int | None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/models.py llmind-cli/tests/test_models.py
git commit -m "feat: add data models"
```

---

## Task 3: Test Fixtures

**Files:**
- Create: `llmind-cli/tests/conftest.py`

- [ ] **Step 1: Write `conftest.py`**

```python
# llmind-cli/tests/conftest.py
import io
import pytest
from pathlib import Path
from llmind.models import Layer


def _make_minimal_jpeg() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="JPEG")
    return buf.getvalue()


def _make_minimal_png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _make_minimal_pdf() -> bytes:
    import pikepdf
    buf = io.BytesIO()
    with pikepdf.new() as pdf:
        pdf.save(buf)
    return buf.getvalue()


@pytest.fixture
def jpeg_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.jpg"
    path.write_bytes(_make_minimal_jpeg())
    return path


@pytest.fixture
def png_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.png"
    path.write_bytes(_make_minimal_png())
    return path


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.pdf"
    path.write_bytes(_make_minimal_pdf())
    return path


@pytest.fixture
def sample_layer() -> Layer:
    return Layer(
        version=1,
        timestamp="2026-04-09T12:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum="a" * 64,
        language="en",
        description="A white 1×1 test image with no content.",
        text="Hello world",
        structure={"type": "test", "regions": [], "figures": [], "tables": []},
        key_id="abcdef1234567890",
        signature="sig" * 20,
    )


# Shared XMP fixture used by test_injector, test_reader, and test_cli
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    '<rdf:Description rdf:about=""\n'
    '  xmlns:llmind="https://llmind.org/ns/1.0/"\n'
    '  llmind:version="1"\n'
    '  llmind:format_version="1.0"\n'
    '  llmind:generator="llmind-cli/0.1.0"\n'
    '  llmind:generator_model="qwen2.5-vl:7b"\n'
    '  llmind:timestamp="2026-04-09T12:00:00Z"\n'
    '  llmind:language="en"\n'
    '  llmind:checksum="' + "a" * 64 + '"\n'
    '  llmind:key_id="abcdef1234567890"\n'
    '  llmind:signature="sig"\n'
    '  llmind:layer_count="1"\n'
    '  llmind:immutable="true"\n'
    '>\n'
    '<llmind:description>Test</llmind:description>\n'
    '<llmind:text>Hello</llmind:text>\n'
    '<llmind:structure>{}</llmind:structure>\n'
    '<llmind:history>[{"version":1,"timestamp":"2026-04-09T12:00:00Z",'
    '"generator":"llmind-cli/0.1.0","generator_model":"qwen2.5-vl:7b",'
    '"checksum":"' + "a" * 64 + '","language":"en","description":"Test",'
    '"text":"Hello","structure":{},"key_id":"abcdef1234567890","signature":"sig"}]'
    '</llmind:history>\n'
    '</rdf:Description>\n'
    '</rdf:RDF>\n'
    '</x:xmpmeta>\n'
    '<?xpacket end="w"?>'
)
```

- [ ] **Step 2: Verify fixtures load cleanly**

```bash
pytest tests/ --collect-only 2>&1 | head -20
```

Expected: no import errors

- [ ] **Step 3: Commit**

```bash
git add llmind-cli/tests/conftest.py
git commit -m "test: add shared fixtures"
```

---

## Task 4: Safety Filter

**Files:**
- Create: `llmind-cli/llmind/safety.py`
- Create: `llmind-cli/tests/test_safety.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_safety.py
import pytest
from pathlib import Path
from llmind.safety import is_safe_file


@pytest.mark.parametrize("name,expected", [
    ("photo.jpg", True),
    ("scan.jpeg", True),
    ("image.PNG", True),
    ("document.pdf", True),
    (".hidden.jpg", False),
    ("Thumbs.db", False),
    ("desktop.ini", False),
    (".DS_Store", False),
    ("photo.txt", False),
    ("photo.mp4", False),
])
def test_safe_file_by_name(tmp_path: Path, name: str, expected: bool):
    path = tmp_path / name
    path.write_bytes(b"\xff\xd8" if name.endswith((".jpg", ".jpeg", ".PNG")) else b"data")
    if name in ("Thumbs.db", "desktop.ini") or name.startswith("."):
        path.touch()
    assert is_safe_file(path) == expected


def test_rejects_symlink(tmp_path: Path):
    real = tmp_path / "photo.jpg"
    real.write_bytes(b"\xff\xd8")
    link = tmp_path / "link.jpg"
    link.symlink_to(real)
    assert is_safe_file(link) is False


def test_rejects_zero_byte_file(tmp_path: Path):
    path = tmp_path / "empty.jpg"
    path.touch()
    assert is_safe_file(path) is False


def test_rejects_file_in_llmind_keys(tmp_path: Path):
    keys_dir = tmp_path / ".llmind-keys"
    keys_dir.mkdir()
    path = keys_dir / "photo.jpg"
    path.write_bytes(b"\xff\xd8")
    assert is_safe_file(path) is False


def test_rejects_file_in_hidden_directory(tmp_path: Path):
    hidden = tmp_path / ".hidden_dir"
    hidden.mkdir()
    path = hidden / "photo.jpg"
    path.write_bytes(b"\xff\xd8")
    assert is_safe_file(path) is False
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_safety.py -v
```

Expected: `ImportError: cannot import name 'is_safe_file'`

- [ ] **Step 3: Write `safety.py`**

```python
# llmind-cli/llmind/safety.py
from pathlib import Path

_BLOCKED_NAMES: frozenset[str] = frozenset(
    {"Thumbs.db", "desktop.ini", ".DS_Store", "Icon\r"}
)
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".pdf"})


def is_safe_file(path: Path) -> bool:
    """Return True if path is safe and supported for enrichment."""
    try:
        if not path.is_file():
            return False
        if path.is_symlink():
            return False
        if path.stat().st_size == 0:
            return False
        if path.name in _BLOCKED_NAMES:
            return False
        if path.name.startswith("."):
            return False
        # Reject files inside hidden directories or .llmind-keys
        for part in path.parts[:-1]:
            if part.startswith(".") or part == ".llmind-keys":
                return False
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            return False
        return True
    except (OSError, PermissionError):
        return False
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_safety.py -v
```

Expected: `10 passed` (all parametrize cases + 4 extra)

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/safety.py llmind-cli/tests/test_safety.py
git commit -m "feat: add safety filter"
```

---

## Task 5: Cryptography

**Files:**
- Create: `llmind-cli/llmind/crypto.py`
- Create: `llmind-cli/tests/test_crypto.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_crypto.py
import json
import pytest
from pathlib import Path
from llmind.crypto import (
    derive_key_id, generate_key, load_key_file, save_key_file,
    sha256_file, sign_layer, verify_signature,
)
from llmind.models import KeyFile


def test_generate_key_is_64_hex_chars():
    key = generate_key()
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_generate_key_is_unique():
    assert generate_key() != generate_key()


def test_derive_key_id_is_16_chars():
    key = "a" * 64
    kid = derive_key_id(key)
    assert len(kid) == 16
    assert all(c in "0123456789abcdef" for c in kid)


def test_derive_key_id_is_deterministic():
    key = generate_key()
    assert derive_key_id(key) == derive_key_id(key)


def test_sha256_file(tmp_path: Path):
    path = tmp_path / "test.bin"
    path.write_bytes(b"hello world")
    digest = sha256_file(path)
    assert len(digest) == 64
    # Known SHA-256 of b"hello world"
    assert digest == "b94d27b9934d3e08a52e52d7da7dabfac484efe04294e576e5b27e6a5f6e3c3e"


def test_sign_layer_produces_64_hex_chars():
    key = generate_key()
    layer = {"version": 1, "checksum": "abc"}
    sig = sign_layer(key, layer)
    assert len(sig) == 64


def test_sign_layer_is_deterministic():
    key = generate_key()
    layer = {"version": 1, "checksum": "abc"}
    assert sign_layer(key, layer) == sign_layer(key, layer)


def test_verify_signature_correct():
    key = generate_key()
    layer = {"version": 1, "text": "hello"}
    sig = sign_layer(key, layer)
    assert verify_signature(key, layer, sig) is True


def test_verify_signature_wrong_key():
    key1 = generate_key()
    key2 = generate_key()
    layer = {"version": 1, "text": "hello"}
    sig = sign_layer(key1, layer)
    assert verify_signature(key2, layer, sig) is False


def test_save_and_load_key_file(tmp_path: Path):
    key = generate_key()
    kid = derive_key_id(key)
    kf = KeyFile(key_id=kid, creation_key=key, created="2026-04-09T12:00:00Z", file="photo.jpg")
    saved_path = save_key_file(tmp_path, kf)
    loaded = load_key_file(saved_path)
    assert loaded.creation_key == key
    assert loaded.key_id == kid
    assert loaded.file == "photo.jpg"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_crypto.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `crypto.py`**

```python
# llmind-cli/llmind/crypto.py
from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import secrets
from pathlib import Path

from llmind.models import KeyFile


def generate_key() -> str:
    """Generate a 256-bit creation key as a 64-char hex string."""
    return secrets.token_hex(32)


def derive_key_id(creation_key: str) -> str:
    """First 16 hex chars of SHA-256(creation_key)."""
    return hashlib.sha256(creation_key.encode()).hexdigest()[:16]


def sha256_file(path: Path) -> str:
    """SHA-256 hex digest of a file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sign_layer(creation_key: str, layer_dict: dict) -> str:
    """HMAC-SHA256 of canonical JSON (keys sorted). Returns hex digest."""
    canonical = json.dumps(layer_dict, sort_keys=True, ensure_ascii=False)
    return _hmac.new(
        creation_key.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()


def verify_signature(creation_key: str, layer_dict: dict, signature: str) -> bool:
    """Constant-time HMAC-SHA256 verification."""
    expected = sign_layer(creation_key, layer_dict)
    return _hmac.compare_digest(expected, signature)


def save_key_file(output_dir: Path, key_file: KeyFile) -> Path:
    """Write key file to output_dir/.llmind-keys/<filename>.key. Returns path."""
    keys_dir = output_dir / ".llmind-keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    key_path = keys_dir / f"{key_file.file}.key"
    key_path.write_text(
        json.dumps(
            {
                "key_id": key_file.key_id,
                "creation_key": key_file.creation_key,
                "created": key_file.created,
                "file": key_file.file,
                "note": key_file.note,
            },
            indent=2,
        )
    )
    # Ensure .llmind-keys/ is gitignored in the parent directory
    gitignore = output_dir / ".gitignore"
    entry = ".llmind-keys/\n"
    if not gitignore.exists():
        gitignore.write_text(entry)
    elif entry.strip() not in gitignore.read_text():
        with open(gitignore, "a") as f:
            f.write(entry)
    return key_path


def load_key_file(path: Path) -> KeyFile:
    """Load and parse a .key file."""
    data = json.loads(path.read_text())
    return KeyFile(
        key_id=data["key_id"],
        creation_key=data["creation_key"],
        created=data["created"],
        file=data["file"],
        note=data.get("note", ""),
    )
```

- [ ] **Step 4: Fix the SHA-256 test value**

The known SHA-256 of `b"hello world"` is `b94d27b9934d3e08a52e52d7da7dabfac484efe04294e576e5b27e6a5f6e3c3e`. Verify by running:

```bash
python3 -c "import hashlib; print(hashlib.sha256(b'hello world').hexdigest())"
```

Copy the output and update the assertion in `test_sha256_file` to match.

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_crypto.py -v
```

Expected: `10 passed`

- [ ] **Step 6: Commit**

```bash
git add llmind-cli/llmind/crypto.py llmind-cli/tests/test_crypto.py
git commit -m "feat: add cryptography module"
```

---

## Task 6: XMP Builder & Parser

**Files:**
- Create: `llmind-cli/llmind/xmp.py`
- Create: `llmind-cli/tests/test_xmp.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_xmp.py
import json
import pytest
from llmind.models import Layer, LLMindMeta
from llmind.xmp import build_xmp, layer_to_dict, parse_xmp


@pytest.fixture
def layer() -> Layer:
    return Layer(
        version=1,
        timestamp="2026-04-09T12:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum="a" * 64,
        language="en",
        description="Test description",
        text="Test text",
        structure={"type": "test", "regions": [], "figures": [], "tables": []},
        key_id="abcdef1234567890",
        signature="sig" * 20,
    )


def test_build_xmp_contains_version(layer: Layer):
    xmp = build_xmp(layer, [layer], layer.key_id)
    assert 'llmind:version="1"' in xmp


def test_build_xmp_contains_checksum(layer: Layer):
    xmp = build_xmp(layer, [layer], layer.key_id)
    assert layer.checksum in xmp


def test_build_xmp_xml_escapes_ampersand(layer: Layer):
    tricky = Layer(
        version=1, timestamp="t", generator="g", generator_model="m",
        checksum="c" * 64, language="en",
        description="AT&T logo", text="text & more",
        structure={}, key_id="k", signature="s",
    )
    xmp = build_xmp(tricky, [tricky], tricky.key_id)
    assert "&amp;" in xmp
    assert "AT&T" not in xmp


def test_roundtrip_single_layer(layer: Layer):
    xmp = build_xmp(layer, [layer], layer.key_id)
    meta = parse_xmp(xmp)
    assert meta is not None
    assert meta.current.version == 1
    assert meta.current.language == "en"
    assert meta.current.description == "Test description"
    assert meta.current.text == "Test text"
    assert meta.current.checksum == "a" * 64
    assert meta.current.key_id == "abcdef1234567890"
    assert meta.layer_count == 1
    assert meta.immutable is True


def test_roundtrip_two_layers(layer: Layer):
    layer2 = Layer(
        version=2, timestamp="2026-04-10T00:00:00Z", generator="g",
        generator_model="m", checksum="b" * 64, language="fr",
        description="desc2", text="text2", structure={}, key_id="k",
    )
    xmp = build_xmp(layer2, [layer, layer2], layer2.key_id)
    meta = parse_xmp(xmp)
    assert meta is not None
    assert meta.layer_count == 2
    assert meta.current.version == 2
    assert meta.layers[0].version == 1


def test_parse_returns_none_for_non_llmind_xmp():
    xmp = '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about=""/></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    assert parse_xmp(xmp) is None


def test_layer_to_dict_has_no_signature_key_by_default(layer: Layer):
    d = layer_to_dict(layer, include_signature=False)
    assert "signature" not in d


def test_layer_to_dict_includes_signature_when_requested(layer: Layer):
    d = layer_to_dict(layer, include_signature=True)
    assert "signature" in d
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_xmp.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `xmp.py`**

```python
# llmind-cli/llmind/xmp.py
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from llmind.models import Layer, LLMindMeta

_LLMIND_NS = "https://llmind.org/ns/1.0/"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
_XPACKET_BEGIN = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
_XPACKET_END = '\n<?xpacket end="w"?>'


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def layer_to_dict(layer: Layer, include_signature: bool = True) -> dict:
    """Serialise a Layer to a plain dict for signing or JSON storage."""
    d: dict = {
        "version": layer.version,
        "timestamp": layer.timestamp,
        "generator": layer.generator,
        "generator_model": layer.generator_model,
        "checksum": layer.checksum,
        "language": layer.language,
        "description": layer.description,
        "text": layer.text,
        "structure": layer.structure,
        "key_id": layer.key_id,
    }
    if include_signature:
        d["signature"] = layer.signature
    return d


def build_xmp(layer: Layer, history: list[Layer], key_id: str) -> str:
    """Build a complete XMP XML packet for a layer and its history."""
    history_json = json.dumps(
        [layer_to_dict(l) for l in history], ensure_ascii=False
    )
    structure_json = json.dumps(layer.structure, ensure_ascii=False)
    sig = _esc(layer.signature or "")

    lines = [
        _XPACKET_BEGIN,
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">',
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">',
        '<rdf:Description rdf:about=""',
        '  xmlns:llmind="https://llmind.org/ns/1.0/"',
        f'  llmind:version="{layer.version}"',
        '  llmind:format_version="1.0"',
        f'  llmind:generator="{_esc(layer.generator)}"',
        f'  llmind:generator_model="{_esc(layer.generator_model)}"',
        f'  llmind:timestamp="{layer.timestamp}"',
        f'  llmind:language="{_esc(layer.language)}"',
        f'  llmind:checksum="{layer.checksum}"',
        f'  llmind:key_id="{key_id}"',
        f'  llmind:signature="{sig}"',
        f'  llmind:layer_count="{len(history)}"',
        '  llmind:immutable="true"',
        ">",
        f"<llmind:description>{_esc(layer.description)}</llmind:description>",
        f"<llmind:text>{_esc(layer.text)}</llmind:text>",
        f"<llmind:structure>{_esc(structure_json)}</llmind:structure>",
        f"<llmind:history>{_esc(history_json)}</llmind:history>",
        "</rdf:Description>",
        "</rdf:RDF>",
        "</x:xmpmeta>",
        _XPACKET_END,
    ]
    return "\n".join(lines)


def parse_xmp(xmp_xml: str) -> LLMindMeta | None:
    """Parse an XMP XML string and return LLMindMeta, or None if not found."""
    try:
        start = xmp_xml.find("<x:xmpmeta")
        end = xmp_xml.find("</x:xmpmeta>")
        if start == -1 or end == -1:
            return None
        xml_body = xmp_xml[start : end + len("</x:xmpmeta>")]

        root = ET.fromstring(xml_body)
        desc = root.find(f".//{{{_RDF_NS}}}Description")
        if desc is None:
            return None

        def attr(name: str, default: str = "") -> str:
            return desc.get(f"{{{_LLMIND_NS}}}{name}", default)

        def elem(name: str) -> str:
            el = desc.find(f"{{{_LLMIND_NS}}}{name}")
            return (el.text or "") if el is not None else ""

        version = attr("version")
        if not version:
            return None

        history_json = elem("history")
        history_dicts: list[dict] = json.loads(history_json) if history_json else []
        layers = tuple(_dict_to_layer(d) for d in history_dicts)

        if not layers:
            structure_json = elem("structure")
            layer = Layer(
                version=int(version),
                timestamp=attr("timestamp"),
                generator=attr("generator"),
                generator_model=attr("generator_model"),
                checksum=attr("checksum"),
                language=attr("language"),
                description=elem("description"),
                text=elem("text"),
                structure=json.loads(structure_json) if structure_json else {},
                key_id=attr("key_id"),
                signature=attr("signature") or None,
            )
            layers = (layer,)

        return LLMindMeta(
            layers=layers,
            current=layers[-1],
            layer_count=int(attr("layer_count", str(len(layers)))),
            immutable=attr("immutable") == "true",
        )
    except (ET.ParseError, json.JSONDecodeError, ValueError, KeyError):
        return None


def _dict_to_layer(d: dict) -> Layer:
    return Layer(
        version=d["version"],
        timestamp=d["timestamp"],
        generator=d["generator"],
        generator_model=d["generator_model"],
        checksum=d["checksum"],
        language=d["language"],
        description=d["description"],
        text=d["text"],
        structure=d["structure"],
        key_id=d["key_id"],
        signature=d.get("signature"),
    )
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_xmp.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/xmp.py llmind-cli/tests/test_xmp.py
git commit -m "feat: add XMP builder and parser"
```

---

## Task 7: JPEG Injection & Reading

**Files:**
- Create: `llmind-cli/llmind/injector.py`
- Create: `llmind-cli/llmind/reader.py`
- Create: `llmind-cli/tests/test_injector.py`
- Create: `llmind-cli/tests/test_reader.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_injector.py  (JPEG section — add PNG/PDF later)
import pytest
from pathlib import Path
from llmind.injector import inject, remove_llmind_xmp
from llmind.reader import has_llmind_layer, is_fresh, read_llmind_meta
from conftest import SAMPLE_XMP


def test_jpeg_inject_produces_valid_jpeg(jpeg_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.jpg"
    inject(jpeg_file, SAMPLE_XMP, out)
    data = out.read_bytes()
    assert data[:2] == b"\xff\xd8"


def test_jpeg_roundtrip(jpeg_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.jpg"
    inject(jpeg_file, SAMPLE_XMP, out)
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.version == 1
    assert meta.current.language == "en"
    assert meta.current.text == "Hello"


def test_jpeg_has_llmind_layer(jpeg_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.jpg"
    assert has_llmind_layer(jpeg_file) is False
    inject(jpeg_file, SAMPLE_XMP, out)
    assert has_llmind_layer(out) is True


def test_jpeg_is_fresh(jpeg_file: Path, tmp_path: Path):
    from llmind.crypto import sha256_file
    out = tmp_path / "enriched.jpg"
    checksum = sha256_file(jpeg_file)
    assert is_fresh(jpeg_file, checksum) is False
    inject(jpeg_file, SAMPLE_XMP, out)
    # SAMPLE_XMP has checksum "aaa..."; original file has a different checksum
    assert is_fresh(out, "a" * 64) is True
    assert is_fresh(out, "b" * 64) is False


def test_jpeg_remove_xmp(jpeg_file: Path, tmp_path: Path):
    enriched = tmp_path / "enriched.jpg"
    stripped = tmp_path / "stripped.jpg"
    inject(jpeg_file, SAMPLE_XMP, enriched)
    remove_llmind_xmp(enriched, stripped)
    assert has_llmind_layer(stripped) is False
    assert stripped.read_bytes()[:2] == b"\xff\xd8"


def test_jpeg_reinject_replaces_existing(jpeg_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.jpg"
    inject(jpeg_file, SAMPLE_XMP, out)
    xmp2 = SAMPLE_XMP.replace('"en"', '"fr"')
    inject(out, xmp2, out)
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.language == "fr"
    # Only one XMP block should be present
    data = out.read_bytes()
    assert data.count(b"http://ns.adobe.com/xap/1.0/") == 1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_injector.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `injector.py`**

```python
# llmind-cli/llmind/injector.py
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pikepdf

_JPEG_XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
_PNG_HEADER = b"\x89PNG\r\n\x1a\n"
_PNG_XMP_KW = b"XML:com.adobe.xmp"


def inject(source_path: Path, xmp_xml: str, output_path: Path) -> None:
    """Inject XMP into a JPEG, PNG, or PDF file. source_path == output_path is in-place."""
    data = source_path.read_bytes()
    xmp_bytes = xmp_xml.encode("utf-8")

    if data[:2] == b"\xff\xd8":
        output_path.write_bytes(_inject_jpeg(data, xmp_bytes))
    elif data[:8] == _PNG_HEADER:
        output_path.write_bytes(_inject_png(data, xmp_bytes))
    elif data[:4] == b"%PDF":
        _inject_pdf(source_path, xmp_bytes, output_path)
    else:
        raise ValueError(f"Unsupported format: {source_path.suffix}")


def remove_llmind_xmp(source_path: Path, output_path: Path) -> None:
    """Remove the LLMind XMP block from a file, leaving all other metadata intact."""
    data = source_path.read_bytes()

    if data[:2] == b"\xff\xd8":
        output_path.write_bytes(_remove_jpeg_xmp(data))
    elif data[:8] == _PNG_HEADER:
        output_path.write_bytes(_remove_png_xmp(data))
    elif data[:4] == b"%PDF":
        _remove_pdf_xmp(source_path, output_path)
    else:
        raise ValueError(f"Unsupported format: {source_path.suffix}")


# ── JPEG ──────────────────────────────────────────────────────────────────────

def _inject_jpeg(data: bytes, xmp_bytes: bytes) -> bytes:
    cleaned = _remove_jpeg_xmp(data)
    payload = _JPEG_XMP_NS + xmp_bytes
    length = len(payload) + 2
    app1 = b"\xff\xe1" + struct.pack(">H", length) + payload
    return cleaned[:2] + app1 + cleaned[2:]


def _remove_jpeg_xmp(data: bytes) -> bytes:
    result = bytearray(data[:2])  # SOI
    pos = 2
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            result.extend(data[pos:])
            break
        marker = data[pos : pos + 2]
        if marker in (b"\xff\xd9", b"\xff\xda"):
            result.extend(data[pos:])
            break
        # Standalone markers (no length field): TEM (0x01) and RST0–RST7 (0xD0–0xD7)
        if marker[1] in (0x01, *range(0xD0, 0xD8)):
            result.extend(marker)
            pos += 2
            continue
        if pos + 4 > len(data):
            result.extend(data[pos:])
            break
        length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        seg_end = pos + 2 + length
        # Skip XMP APP1
        if (
            marker == b"\xff\xe1"
            and length > len(_JPEG_XMP_NS)
            and data[pos + 4 : pos + 4 + len(_JPEG_XMP_NS)] == _JPEG_XMP_NS
        ):
            pos = seg_end
            continue
        result.extend(data[pos:seg_end])
        pos = seg_end
    return bytes(result)


# ── PNG ───────────────────────────────────────────────────────────────────────

def _inject_png(data: bytes, xmp_bytes: bytes) -> bytes:
    cleaned = _remove_png_xmp(data)
    chunk_data = (
        _PNG_XMP_KW
        + b"\x00"   # null after keyword
        + b"\x00"   # compression flag: none
        + b"\x00"   # compression method
        + b"\x00"   # language tag (empty) + null
        + b"\x00"   # translated keyword (empty) + null
        + xmp_bytes
    )
    chunk = _png_chunk(b"iTXt", chunk_data)
    ihdr_end = 8 + 4 + 4 + 13 + 4  # PNG header + IHDR (length+type+data+CRC)
    return cleaned[:ihdr_end] + chunk + cleaned[ihdr_end:]


def _remove_png_xmp(data: bytes) -> bytes:
    result = bytearray(data[:8])  # PNG signature
    pos = 8
    while pos < len(data):
        if pos + 8 > len(data):
            result.extend(data[pos:])
            break
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        total = 12 + length
        if chunk_type == b"iTXt" and chunk_data[: len(_PNG_XMP_KW)] == _PNG_XMP_KW:
            pos += total
            continue
        result.extend(data[pos : pos + total])
        pos += total
    return bytes(result)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)


# ── PDF ───────────────────────────────────────────────────────────────────────

def _inject_pdf(source_path: Path, xmp_bytes: bytes, output_path: Path) -> None:
    with pikepdf.open(source_path) as pdf:
        stream = pikepdf.Stream(pdf, xmp_bytes)
        stream[pikepdf.Name("/Type")] = pikepdf.Name("/Metadata")
        stream[pikepdf.Name("/Subtype")] = pikepdf.Name("/XML")
        pdf.Root[pikepdf.Name("/Metadata")] = pdf.make_indirect(stream)
        pdf.save(output_path)


def _remove_pdf_xmp(source_path: Path, output_path: Path) -> None:
    with pikepdf.open(source_path) as pdf:
        if pikepdf.Name("/Metadata") in pdf.Root:
            del pdf.Root[pikepdf.Name("/Metadata")]
        pdf.save(output_path)
```

- [ ] **Step 4: Write `reader.py`**

```python
# llmind-cli/llmind/reader.py
from __future__ import annotations

import re
import struct
from pathlib import Path

import pikepdf

from llmind.models import LLMindMeta
from llmind.xmp import parse_xmp

_JPEG_XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
_PNG_HEADER = b"\x89PNG\r\n\x1a\n"
_PNG_XMP_KW = b"XML:com.adobe.xmp"
_CHECKSUM_RE = re.compile(r'llmind:checksum="([a-f0-9]{64})"')


def read_llmind_meta(path: Path) -> LLMindMeta | None:
    """Return parsed LLMind metadata from file, or None if absent."""
    xmp = _extract_xmp(path)
    return parse_xmp(xmp) if xmp else None


def has_llmind_layer(path: Path) -> bool:
    """Return True if file contains a LLMind XMP layer."""
    xmp = _extract_xmp(path)
    return bool(xmp and "llmind:version" in xmp)


def is_fresh(path: Path, checksum: str) -> bool:
    """Return True if file has a LLMind layer whose stored checksum matches `checksum`."""
    xmp = _extract_xmp(path)
    if not xmp or "llmind:version" not in xmp:
        return False
    m = _CHECKSUM_RE.search(xmp)
    return bool(m and m.group(1) == checksum)


# ── Format dispatchers ────────────────────────────────────────────────────────

def _extract_xmp(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except (OSError, PermissionError):
        return None
    if data[:2] == b"\xff\xd8":
        return _jpeg_xmp(data)
    if data[:8] == _PNG_HEADER:
        return _png_xmp(data)
    if data[:4] == b"%PDF":
        return _pdf_xmp(path)
    return None


def _jpeg_xmp(data: bytes) -> str | None:
    pos = 2
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            break
        marker = data[pos : pos + 2]
        if marker in (b"\xff\xd9", b"\xff\xda"):
            break
        # TEM (0x01) and RST0–RST7 (0xD0–0xD7): no length field
        if marker[1] in (0x01, *range(0xD0, 0xD8)):
            pos += 2
            continue
        if pos + 4 > len(data):
            break
        length = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if (
            marker == b"\xff\xe1"
            and length > len(_JPEG_XMP_NS)
            and data[pos + 4 : pos + 4 + len(_JPEG_XMP_NS)] == _JPEG_XMP_NS
        ):
            xmp_start = pos + 4 + len(_JPEG_XMP_NS)
            xmp_end = pos + 2 + length
            return data[xmp_start:xmp_end].decode("utf-8", errors="replace")
        pos += 2 + length
    return None


def _png_xmp(data: bytes) -> str | None:
    pos = 8
    while pos < len(data):
        if pos + 8 > len(data):
            break
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        if chunk_type == b"iTXt" and chunk_data[: len(_PNG_XMP_KW)] == _PNG_XMP_KW:
            # Skip: keyword + null + comp_flag + comp_method + lang_tag_null + translated_kw_null
            skip = len(_PNG_XMP_KW) + 1 + 1 + 1 + 1 + 1
            return chunk_data[skip:].decode("utf-8", errors="replace")
        pos += 12 + length
    return None


def _pdf_xmp(path: Path) -> str | None:
    try:
        with pikepdf.open(path) as pdf:
            meta = pdf.Root.get(pikepdf.Name("/Metadata"))
            if meta is None:
                return None
            return pdf.get_object(meta.objgen).read_bytes().decode("utf-8", errors="replace")
    except Exception:
        return None
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_injector.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Write `test_reader.py`**

```python
# llmind-cli/tests/test_reader.py
from pathlib import Path
from llmind.injector import inject
from llmind.reader import has_llmind_layer, is_fresh, read_llmind_meta
from conftest import SAMPLE_XMP


def test_read_meta_from_unenriched_jpeg_returns_none(jpeg_file: Path):
    assert read_llmind_meta(jpeg_file) is None


def test_has_llmind_layer_false_before_inject(jpeg_file: Path):
    assert has_llmind_layer(jpeg_file) is False


def test_is_fresh_false_before_inject(jpeg_file: Path):
    assert is_fresh(jpeg_file, "a" * 64) is False


def test_read_meta_returns_correct_fields(jpeg_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.jpg"
    inject(jpeg_file, SAMPLE_XMP, out)
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.generator == "llmind-cli/0.1.0"
    assert meta.current.key_id == "abcdef1234567890"
    assert meta.immutable is True
```

- [ ] **Step 7: Run `test_reader.py`**

```bash
pytest tests/test_reader.py -v
```

Expected: `4 passed`

- [ ] **Step 8: Commit**

```bash
git add llmind-cli/llmind/injector.py llmind-cli/llmind/reader.py \
        llmind-cli/tests/test_injector.py llmind-cli/tests/test_reader.py
git commit -m "feat: add JPEG injection and reading"
```

---

## Task 8: PNG & PDF Injection / Reading

**Files:**
- Modify: `llmind-cli/tests/test_injector.py` (append PNG + PDF tests)

- [ ] **Step 1: Append PNG tests to `test_injector.py`**

```python
# Append to llmind-cli/tests/test_injector.py

def test_png_roundtrip(png_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.png"
    inject(png_file, SAMPLE_XMP, out)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.version == 1
    assert meta.current.text == "Hello"


def test_png_remove_xmp(png_file: Path, tmp_path: Path):
    enriched = tmp_path / "enriched.png"
    stripped = tmp_path / "stripped.png"
    inject(png_file, SAMPLE_XMP, enriched)
    remove_llmind_xmp(enriched, stripped)
    assert has_llmind_layer(stripped) is False
    assert stripped.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_png_reinject_replaces_existing(png_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.png"
    inject(png_file, SAMPLE_XMP, out)
    xmp2 = SAMPLE_XMP.replace('"en"', '"de"')
    inject(out, xmp2, out)
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.language == "de"
    data = out.read_bytes()
    assert data.count(b"XML:com.adobe.xmp") == 1
```

- [ ] **Step 2: Append PDF tests to `test_injector.py`**

```python
# Append to llmind-cli/tests/test_injector.py

def test_pdf_roundtrip(pdf_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.pdf"
    inject(pdf_file, SAMPLE_XMP, out)
    assert out.read_bytes()[:4] == b"%PDF"
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.version == 1
    assert meta.current.text == "Hello"


def test_pdf_remove_xmp(pdf_file: Path, tmp_path: Path):
    enriched = tmp_path / "enriched.pdf"
    stripped = tmp_path / "stripped.pdf"
    inject(pdf_file, SAMPLE_XMP, enriched)
    remove_llmind_xmp(enriched, stripped)
    assert has_llmind_layer(stripped) is False


def test_pdf_reinject_replaces_existing(pdf_file: Path, tmp_path: Path):
    out = tmp_path / "enriched.pdf"
    inject(pdf_file, SAMPLE_XMP, out)
    xmp2 = SAMPLE_XMP.replace('"en"', '"ja"')
    inject(out, xmp2, out)
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.language == "ja"
```

- [ ] **Step 3: Run all injector tests**

```bash
pytest tests/test_injector.py -v
```

Expected: `13 passed`

- [ ] **Step 4: Commit**

```bash
git add llmind-cli/tests/test_injector.py
git commit -m "test: add PNG and PDF injection round-trip tests"
```

---

## Task 9: Ollama Client

**Files:**
- Create: `llmind-cli/llmind/ollama.py`
- Create: `llmind-cli/tests/test_ollama.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_ollama.py
import json
import pytest
import responses as resp_lib
from pathlib import Path
from llmind.ollama import OllamaConnectionError, OllamaExtractionError, extract

VALID_RESPONSE = {
    "language": "en",
    "description": "A white square.",
    "text": "No text found.",
    "structure": {
        "type": "photograph",
        "regions": [{"label": "background", "area": "full", "content": "white"}],
        "figures": [],
        "tables": [],
    },
}

OLLAMA_URL = "http://localhost:11434"


@resp_lib.activate
def test_extract_jpeg_success(jpeg_file: Path):
    resp_lib.add(
        resp_lib.POST,
        f"{OLLAMA_URL}/api/chat",
        json={"message": {"content": json.dumps(VALID_RESPONSE)}},
        status=200,
    )
    result = extract(jpeg_file, "qwen2.5-vl:7b", OLLAMA_URL)
    assert result.language == "en"
    assert result.description == "A white square."
    assert result.structure["type"] == "photograph"


@resp_lib.activate
def test_extract_retries_on_connection_error(jpeg_file: Path):
    # First two calls fail, third succeeds
    resp_lib.add(resp_lib.POST, f"{OLLAMA_URL}/api/chat", body=ConnectionError("refused"))
    resp_lib.add(resp_lib.POST, f"{OLLAMA_URL}/api/chat", body=ConnectionError("refused"))
    resp_lib.add(
        resp_lib.POST,
        f"{OLLAMA_URL}/api/chat",
        json={"message": {"content": json.dumps(VALID_RESPONSE)}},
        status=200,
    )
    result = extract(jpeg_file, "qwen2.5-vl:7b", OLLAMA_URL)
    assert result.language == "en"


@resp_lib.activate
def test_extract_raises_after_three_failures(jpeg_file: Path):
    for _ in range(4):  # 1 initial + 3 retries
        resp_lib.add(resp_lib.POST, f"{OLLAMA_URL}/api/chat", body=ConnectionError("refused"))
    with pytest.raises(OllamaConnectionError):
        extract(jpeg_file, "qwen2.5-vl:7b", OLLAMA_URL)


@resp_lib.activate
def test_extract_retries_on_malformed_json(jpeg_file: Path):
    resp_lib.add(
        resp_lib.POST,
        f"{OLLAMA_URL}/api/chat",
        json={"message": {"content": "not json at all"}},
        status=200,
    )
    resp_lib.add(
        resp_lib.POST,
        f"{OLLAMA_URL}/api/chat",
        json={"message": {"content": json.dumps(VALID_RESPONSE)}},
        status=200,
    )
    result = extract(jpeg_file, "qwen2.5-vl:7b", OLLAMA_URL)
    assert result.language == "en"


@resp_lib.activate
def test_extract_raises_after_two_json_failures(jpeg_file: Path):
    resp_lib.add(
        resp_lib.POST,
        f"{OLLAMA_URL}/api/chat",
        json={"message": {"content": "not json"}},
        status=200,
    )
    resp_lib.add(
        resp_lib.POST,
        f"{OLLAMA_URL}/api/chat",
        json={"message": {"content": "still not json"}},
        status=200,
    )
    with pytest.raises(OllamaExtractionError):
        extract(jpeg_file, "qwen2.5-vl:7b", OLLAMA_URL)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_ollama.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `ollama.py`**

```python
# llmind-cli/llmind/ollama.py
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

from llmind.models import ExtractionResult

_EXTRACTION_PROMPT = """\
You are LLMind, a file enrichment engine. Extract ALL text and visual data from this file.
Return ONLY valid JSON with these exact fields:
{
  "language": "detected language ISO codes, comma-separated",
  "description": "Exhaustive visual description: logos, badges, icons, colors, layout, text styling, spatial relationships.",
  "text": "ALL extracted text organized by section. Use separators like ═══ SECTION NAME ═══",
  "structure": {
    "type": "document type (e.g. e-ticket, invoice, photograph, diagram, form)",
    "regions": [{"label": "name", "area": "position", "content": "what it contains"}],
    "figures": [{"label": "name", "area": "position", "content": "visual description"}],
    "tables": [{"label": "name", "rows": 0, "cols": 0, "content": "cell summary"}]
  }
}"""

_STRICT_PROMPT = _EXTRACTION_PROMPT + (
    "\n\nIMPORTANT: Return ONLY the JSON object. No markdown. No code blocks. No explanation."
)


class OllamaConnectionError(Exception):
    pass


class OllamaExtractionError(Exception):
    pass


def extract(path: Path, model: str, ollama_url: str) -> ExtractionResult:
    """Extract semantic data from a file using an Ollama vision model."""
    if path.suffix.lower() == ".pdf":
        return _extract_pdf(path, model, ollama_url)
    return _extract_image(path, model, ollama_url)


def _extract_image(path: Path, model: str, url: str) -> ExtractionResult:
    b64 = base64.b64encode(path.read_bytes()).decode()
    raw = _call_with_retry(url, model, _EXTRACTION_PROMPT, [b64])
    data = _parse_with_retry(url, model, raw, [b64])
    return _to_result(data)


def _extract_pdf(path: Path, model: str, url: str) -> ExtractionResult:
    images = _pdf_to_images(path)
    if not images:
        raise OllamaExtractionError("PDF produced no page images")
    page_results: list[tuple[int, dict]] = []
    for i, img_bytes in enumerate(images, start=1):
        b64 = base64.b64encode(img_bytes).decode()
        raw = _call_with_retry(url, model, _EXTRACTION_PROMPT, [b64])
        data = _parse_with_retry(url, model, raw, [b64])
        page_results.append((i, data))
    return _merge_pages(page_results)


def _call_with_retry(url: str, model: str, prompt: str, images: list[str]) -> str:
    delays = [0, 1, 2, 4]
    last_exc: Exception | None = None
    for delay in delays:
        if delay:
            time.sleep(delay)
        try:
            return _call(url, model, prompt, images)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            last_exc = exc
    raise OllamaConnectionError(
        f"Ollama unreachable after {len(delays)} attempts: {last_exc}"
    )


def _call(url: str, model: str, prompt: str, images: list[str]) -> str:
    resp = requests.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": images}],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 8000},
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _parse_with_retry(url: str, model: str, raw: str, images: list[str]) -> dict:
    try:
        return _parse_json(raw)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    try:
        raw2 = _call(url, model, _STRICT_PROMPT, images)
        return _parse_json(raw2)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise OllamaExtractionError(f"Model returned invalid JSON after retry: {exc}")


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def _to_result(data: dict) -> ExtractionResult:
    return ExtractionResult(
        language=data.get("language", ""),
        description=data.get("description", ""),
        text=data.get("text", ""),
        structure=data.get("structure", {}),
    )


def _merge_pages(page_results: list[tuple[int, dict]]) -> ExtractionResult:
    descriptions, texts, pages, languages = [], [], [], set()
    doc_type = ""
    for page_num, data in page_results:
        descriptions.append(f"Page {page_num}: {data.get('description', '')}")
        texts.append(f"═══ PAGE {page_num} ═══\n{data.get('text', '')}")
        pages.append(data.get("structure", {}))
        for lang in data.get("language", "").split(","):
            lang = lang.strip()
            if lang:
                languages.add(lang)
        if not doc_type:
            doc_type = data.get("structure", {}).get("type", "")
    return ExtractionResult(
        language=", ".join(sorted(languages)),
        description="\n\n".join(descriptions),
        text="\n\n".join(texts),
        structure={"type": doc_type, "pages": pages, "regions": [], "figures": [], "tables": []},
    )


def _pdf_to_images(path: Path, dpi: int = 150) -> list[bytes]:
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError(
            "pdf2image is not installed. Install poppler and run: pip install pdf2image"
        )
    import io
    pages = convert_from_path(str(path), dpi=dpi, fmt="jpeg")
    result = []
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, format="JPEG", quality=85)
        result.append(buf.getvalue())
    return result
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_ollama.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/ollama.py llmind-cli/tests/test_ollama.py
git commit -m "feat: add Ollama client with retry logic"
```

---

## Task 10: Enricher

**Files:**
- Create: `llmind-cli/llmind/enricher.py`
- Create: `llmind-cli/tests/test_enricher.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_enricher.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from llmind.enricher import EnrichOptions, enrich_file
from llmind.models import ExtractionResult
from llmind.reader import has_llmind_layer, read_llmind_meta
from llmind.crypto import sha256_file

MOCK_EXTRACTION = ExtractionResult(
    language="en",
    description="A white square.",
    text="No text.",
    structure={"type": "photograph", "regions": [], "figures": [], "tables": []},
)


def test_enrich_jpeg_creates_layer(jpeg_file: Path, tmp_path: Path):
    opts = EnrichOptions(output_dir=tmp_path)
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION):
        result = enrich_file(jpeg_file, opts)
    out = tmp_path / "test.jpg"
    assert result.success is True
    assert result.version == 1
    assert has_llmind_layer(out)


def test_enrich_saves_key_file(jpeg_file: Path, tmp_path: Path):
    opts = EnrichOptions(output_dir=tmp_path)
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION):
        enrich_file(jpeg_file, opts)
    key_path = tmp_path / ".llmind-keys" / "test.jpg.key"
    assert key_path.exists()
    data = json.loads(key_path.read_text())
    assert "creation_key" in data
    assert len(data["creation_key"]) == 64


def test_enrich_checksum_matches_original(jpeg_file: Path, tmp_path: Path):
    opts = EnrichOptions(output_dir=tmp_path)
    original_checksum = sha256_file(jpeg_file)
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION):
        enrich_file(jpeg_file, opts)
    out = tmp_path / "test.jpg"
    meta = read_llmind_meta(out)
    assert meta is not None
    assert meta.current.checksum == original_checksum


def test_enrich_skips_fresh_file(jpeg_file: Path, tmp_path: Path):
    opts = EnrichOptions(output_dir=tmp_path)
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION) as mock_extract:
        enrich_file(jpeg_file, opts)
        out = tmp_path / "test.jpg"
        # Second enrich of the out file — should skip since no changes
        opts2 = EnrichOptions()
        result2 = enrich_file(out, opts2)
    assert result2.skipped is True
    assert mock_extract.call_count == 1  # only called once


def test_enrich_force_flag_re_enriches(jpeg_file: Path, tmp_path: Path):
    opts = EnrichOptions(output_dir=tmp_path)
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION) as mock_extract:
        enrich_file(jpeg_file, opts)
        out = tmp_path / "test.jpg"
        opts2 = EnrichOptions(force=True)
        result2 = enrich_file(out, opts2)
    assert result2.success is True
    assert mock_extract.call_count == 2


def test_enrich_dry_run_does_not_write(jpeg_file: Path, tmp_path: Path):
    opts = EnrichOptions(output_dir=tmp_path, dry_run=True)
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION):
        result = enrich_file(jpeg_file, opts)
    out = tmp_path / "test.jpg"
    assert not out.exists()
    assert result.success is True


def test_enrich_unsafe_file_is_skipped(tmp_path: Path):
    hidden = tmp_path / ".hidden.jpg"
    hidden.write_bytes(b"\xff\xd8")
    result = enrich_file(hidden, EnrichOptions())
    assert result.skipped is True
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_enricher.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `enricher.py`**

```python
# llmind-cli/llmind/enricher.py
from __future__ import annotations

import datetime
import time
from pathlib import Path
from typing import NamedTuple

from llmind import __version__
from llmind.crypto import derive_key_id, generate_key, load_key_file, save_key_file, sha256_file
from llmind.injector import inject
from llmind.models import EnrichResult, ExtractionResult, KeyFile, Layer
from llmind.ollama import extract
from llmind.reader import is_fresh, read_llmind_meta
from llmind.safety import is_safe_file
from llmind.xmp import build_xmp, layer_to_dict


class EnrichOptions(NamedTuple):
    model: str = "qwen2.5-vl:7b"
    ollama_url: str = "http://localhost:11434"
    key_path: Path | None = None
    force: bool = False
    dry_run: bool = False
    output_dir: Path | None = None
    recursive: bool = False
    verbose: bool = False


def enrich_file(path: Path, opts: EnrichOptions) -> EnrichResult:
    """Enrich a single file. Returns EnrichResult."""
    start = time.monotonic()

    if not is_safe_file(path):
        return EnrichResult(path, False, True, None, 0, 0, 0, 0.0, "Unsafe or unsupported")

    checksum = sha256_file(path)

    if not opts.force and is_fresh(path, checksum):
        return EnrichResult(path, False, True, None, 0, 0, 0, 0.0, "Already fresh")

    if opts.dry_run:
        return EnrichResult(path, True, False, None, 0, 0, 0, 0.0, None)

    output_path = (opts.output_dir / path.name) if opts.output_dir else path
    keys_dir = opts.output_dir or path.parent

    existing_meta = read_llmind_meta(path)
    existing_history = list(existing_meta.layers) if existing_meta else []
    version = (existing_meta.current.version + 1) if existing_meta else 1

    if existing_history and opts.key_path:
        kf = load_key_file(opts.key_path)
        creation_key = kf.creation_key
    else:
        creation_key = generate_key()

    key_id = derive_key_id(creation_key)
    extraction = extract(path, opts.model, opts.ollama_url)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    generator = f"llmind-cli/{__version__}"

    # Build signable dict (no signature field)
    signable = {
        "version": version,
        "timestamp": now,
        "generator": generator,
        "generator_model": opts.model,
        "checksum": checksum,
        "language": extraction.language,
        "description": extraction.description,
        "text": extraction.text,
        "structure": extraction.structure,
        "key_id": key_id,
    }
    from llmind.crypto import sign_layer
    signature = sign_layer(creation_key, signable)

    layer = Layer(
        version=version,
        timestamp=now,
        generator=generator,
        generator_model=opts.model,
        checksum=checksum,
        language=extraction.language,
        description=extraction.description,
        text=extraction.text,
        structure=extraction.structure,
        key_id=key_id,
        signature=signature,
    )

    history = existing_history + [layer]
    xmp_xml = build_xmp(layer, history, key_id)
    inject(path, xmp_xml, output_path)

    if version == 1:
        kf_out = KeyFile(
            key_id=key_id, creation_key=creation_key,
            created=now, file=path.name,
        )
        save_key_file(keys_dir, kf_out)

    elapsed = time.monotonic() - start
    structure = extraction.structure
    regions = len(structure.get("regions", []))
    figures = len(structure.get("figures", []))
    tables = len(structure.get("tables", []))

    return EnrichResult(path, True, False, version, regions, figures, tables, elapsed, None)


def enrich_directory(directory: Path, opts: EnrichOptions) -> list[EnrichResult]:
    """Enrich all supported files in a directory."""
    pattern = "**/*" if opts.recursive else "*"
    results = []
    for path in sorted(directory.glob(pattern)):
        if path.is_file() and is_safe_file(path):
            results.append(enrich_file(path, opts))
    return results
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_enricher.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/enricher.py llmind-cli/tests/test_enricher.py
git commit -m "feat: add enricher pipeline"
```

---

## Task 11: Verifier

**Files:**
- Create: `llmind-cli/llmind/verifier.py`
- Create: `llmind-cli/tests/test_verifier.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_verifier.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from llmind.enricher import EnrichOptions, enrich_file
from llmind.models import ExtractionResult
from llmind.verifier import verify_file

MOCK_EXTRACTION = ExtractionResult(
    language="en", description="desc", text="text",
    structure={"type": "test", "regions": [], "figures": [], "tables": []},
)


@pytest.fixture
def enriched_jpeg(jpeg_file: Path, tmp_path: Path):
    opts = EnrichOptions(output_dir=tmp_path)
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION):
        enrich_file(jpeg_file, opts)
    return tmp_path / "test.jpg", tmp_path / ".llmind-keys" / "test.jpg.key"


def test_verify_fresh_file(enriched_jpeg):
    out_path, _ = enriched_jpeg
    result = verify_file(out_path)
    assert result.has_layer is True
    assert result.checksum_valid is True
    assert result.signature_valid is None  # no key provided


def test_verify_stale_file(enriched_jpeg, tmp_path: Path):
    out_path, _ = enriched_jpeg
    # Modify file after enrichment to make it stale
    out_path.write_bytes(out_path.read_bytes() + b"\x00")
    result = verify_file(out_path)
    assert result.has_layer is True
    assert result.checksum_valid is False


def test_verify_signature_valid(enriched_jpeg):
    out_path, key_path = enriched_jpeg
    result = verify_file(out_path, key_path=key_path)
    assert result.signature_valid is True


def test_verify_wrong_key(enriched_jpeg, tmp_path: Path):
    out_path, key_path = enriched_jpeg
    # Write a key file with the wrong creation_key
    wrong_key_data = json.loads(key_path.read_text())
    from llmind.crypto import generate_key
    wrong_key_data["creation_key"] = generate_key()
    wrong_key_path = tmp_path / "wrong.key"
    wrong_key_path.write_text(json.dumps(wrong_key_data))
    result = verify_file(out_path, key_path=wrong_key_path)
    assert result.signature_valid is False


def test_verify_file_without_layer(jpeg_file: Path):
    result = verify_file(jpeg_file)
    assert result.has_layer is False
    assert result.checksum_valid is False
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_verifier.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `verifier.py`**

```python
# llmind-cli/llmind/verifier.py
from __future__ import annotations

from pathlib import Path

from llmind.crypto import load_key_file, sha256_file, verify_signature
from llmind.models import VerifyResult
from llmind.reader import read_llmind_meta
from llmind.xmp import layer_to_dict


def verify_file(path: Path, key_path: Path | None = None) -> VerifyResult:
    """Verify checksum freshness and optionally signature validity."""
    meta = read_llmind_meta(path)
    if meta is None:
        return VerifyResult(path, False, False, None, 0, None)

    current_checksum = sha256_file(path)
    checksum_valid = current_checksum == meta.current.checksum

    signature_valid: bool | None = None
    if key_path is not None:
        kf = load_key_file(key_path)
        signable = layer_to_dict(meta.current, include_signature=False)
        signature_valid = verify_signature(
            kf.creation_key, signable, meta.current.signature or ""
        )

    return VerifyResult(
        path=path,
        has_layer=True,
        checksum_valid=checksum_valid,
        signature_valid=signature_valid,
        layer_count=meta.layer_count,
        current_version=meta.current.version,
    )


def verify_directory(directory: Path, key_path: Path | None = None) -> list[VerifyResult]:
    """Verify all supported files in a directory."""
    from llmind.safety import is_safe_file
    results = []
    for path in sorted(directory.glob("*")):
        if path.is_file() and is_safe_file(path):
            results.append(verify_file(path, key_path))
    return results
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_verifier.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/verifier.py llmind-cli/tests/test_verifier.py
git commit -m "feat: add verifier"
```

---

## Task 12: Watcher

**Files:**
- Create: `llmind-cli/llmind/watcher.py`
- Create: `llmind-cli/tests/test_watcher.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_watcher.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from llmind.enricher import EnrichOptions
from llmind.watcher import WatchMode, should_process_event


def test_should_process_only_supported_extensions(tmp_path: Path):
    jpg = tmp_path / "photo.jpg"
    jpg.write_bytes(b"\xff\xd8")
    txt = tmp_path / "notes.txt"
    txt.write_text("hello")
    assert should_process_event(jpg) is True
    assert should_process_event(txt) is False


def test_should_not_process_hidden_file(tmp_path: Path):
    hidden = tmp_path / ".hidden.jpg"
    hidden.write_bytes(b"\xff\xd8")
    assert should_process_event(hidden) is False


def test_watch_mode_enum_values():
    assert WatchMode.NEW.value == "new"
    assert WatchMode.BACKFILL.value == "backfill"
    assert WatchMode.EXISTING.value == "existing"


def test_existing_mode_calls_enrich_directory_only(tmp_path: Path):
    opts = EnrichOptions()
    with patch("llmind.watcher.enrich_directory") as mock_enrich:
        from llmind.watcher import run_watch
        run_watch(tmp_path, opts, WatchMode.EXISTING, start_observer=False)
    mock_enrich.assert_called_once_with(tmp_path, opts)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_watcher.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Write `watcher.py`**

```python
# llmind-cli/llmind/watcher.py
from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from llmind.enricher import EnrichOptions, enrich_directory, enrich_file
from llmind.safety import is_safe_file

logger = logging.getLogger(__name__)


class WatchMode(str, Enum):
    NEW = "new"
    BACKFILL = "backfill"
    EXISTING = "existing"


def should_process_event(path: Path) -> bool:
    """Return True if the path should trigger enrichment."""
    return is_safe_file(path)


class _LLMindHandler(FileSystemEventHandler):
    def __init__(self, opts: EnrichOptions, debounce_seconds: float = 2.0) -> None:
        super().__init__()
        self._opts = opts
        self._debounce = debounce_seconds
        self._pending: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def _schedule(self, path: Path) -> None:
        if not should_process_event(path):
            return
        with self._lock:
            existing = self._pending.pop(path, None)
            if existing:
                existing.cancel()
            timer = threading.Timer(self._debounce, self._process, args=[path])
            self._pending[path] = timer
            timer.start()

    def _process(self, path: Path) -> None:
        with self._lock:
            self._pending.pop(path, None)
        try:
            result = enrich_file(path, self._opts)
            if result.success:
                logger.info("Enriched: %s (v%s, %.1fs)", path.name, result.version, result.elapsed)
            elif result.skipped:
                logger.debug("Skipped: %s — %s", path.name, result.error)
        except Exception as exc:
            logger.warning("Failed to enrich %s: %s", path.name, exc)


def run_watch(
    directory: Path,
    opts: EnrichOptions,
    mode: WatchMode,
    start_observer: bool = True,
) -> None:
    """Start watch mode. Blocks until KeyboardInterrupt unless start_observer=False."""
    if mode in (WatchMode.BACKFILL, WatchMode.EXISTING):
        enrich_directory(directory, opts)

    if mode == WatchMode.EXISTING or not start_observer:
        return

    handler = _LLMindHandler(opts)
    observer = Observer()
    observer.schedule(handler, str(directory), recursive=opts.recursive)
    observer.start()
    logger.info("Watching %s (mode=%s) — press Ctrl+C to stop", directory, mode.value)
    try:
        while observer.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_watcher.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/watcher.py llmind-cli/tests/test_watcher.py
git commit -m "feat: add watcher with three modes"
```

---

## Task 13: CLI — enrich, read, history

**Files:**
- Modify: `llmind-cli/llmind/cli.py`
- Create: `llmind-cli/tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-cli/tests/test_cli.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from click.testing import CliRunner
from llmind.cli import main
from llmind.models import EnrichResult, ExtractionResult, LLMindMeta, Layer

MOCK_EXTRACTION = ExtractionResult(
    language="en", description="desc", text="text",
    structure={"type": "test", "regions": [{"label": "r", "area": "top", "content": "c"}],
               "figures": [], "tables": []},
)

SAMPLE_LAYER = Layer(
    version=1, timestamp="2026-04-09T12:00:00Z", generator="llmind-cli/0.1.0",
    generator_model="qwen2.5-vl:7b", checksum="a" * 64, language="en",
    description="A test image", text="Hello world",
    structure={"type": "test", "regions": [], "figures": [], "tables": []},
    key_id="abcdef1234567890", signature="sig",
)

SAMPLE_META = LLMindMeta(layers=(SAMPLE_LAYER,), current=SAMPLE_LAYER, layer_count=1, immutable=True)


def test_enrich_single_file(jpeg_file: Path):
    runner = CliRunner()
    with patch("llmind.enricher.extract", return_value=MOCK_EXTRACTION):
        result = runner.invoke(main, ["enrich", str(jpeg_file)])
    assert result.exit_code == 0
    assert "✓" in result.output or "enriched" in result.output.lower()


def test_enrich_dry_run_shows_would_enrich(jpeg_file: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["enrich", "--dry-run", str(jpeg_file)])
    assert result.exit_code == 0
    assert "dry" in result.output.lower() or "would" in result.output.lower()


def test_read_text_format(jpeg_file: Path, tmp_path: Path):
    runner = CliRunner()
    with patch("llmind.cli.read_llmind_meta", return_value=SAMPLE_META):
        result = runner.invoke(main, ["read", str(jpeg_file)])
    assert result.exit_code == 0
    assert "en" in result.output
    assert "Hello world" in result.output


def test_read_json_format(jpeg_file: Path):
    runner = CliRunner()
    with patch("llmind.cli.read_llmind_meta", return_value=SAMPLE_META):
        result = runner.invoke(main, ["read", "--format", "json", str(jpeg_file)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["version"] == 1
    assert data["language"] == "en"


def test_read_no_layer(jpeg_file: Path):
    runner = CliRunner()
    with patch("llmind.cli.read_llmind_meta", return_value=None):
        result = runner.invoke(main, ["read", str(jpeg_file)])
    assert result.exit_code != 0 or "no llmind" in result.output.lower()


def test_history_text_format(jpeg_file: Path):
    runner = CliRunner()
    with patch("llmind.cli.read_llmind_meta", return_value=SAMPLE_META):
        result = runner.invoke(main, ["history", str(jpeg_file)])
    assert result.exit_code == 0
    assert "v1" in result.output or "version" in result.output.lower()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_cli.py::test_enrich_single_file tests/test_cli.py::test_read_text_format -v
```

Expected: fail (missing commands in cli.py)

- [ ] **Step 3: Replace `cli.py` with full implementation**

```python
# llmind-cli/llmind/cli.py
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from llmind import __version__
from llmind.enricher import EnrichOptions, enrich_directory, enrich_file
from llmind.reader import read_llmind_meta
from llmind.verifier import verify_directory, verify_file
from llmind.xmp import layer_to_dict

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="llmind-cli")
def main() -> None:
    """LLMind — semantic file enrichment engine."""


# ── enrich ────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive", "-r", is_flag=True)
@click.option("--model", "-m", default="qwen2.5-vl:7b", show_default=True)
@click.option("--ollama-url", default="http://localhost:11434", show_default=True)
@click.option("--key", "key_path", type=click.Path(exists=True, path_type=Path))
@click.option("--force", is_flag=True)
@click.option("--dry-run", is_flag=True)
@click.option("--output-dir", type=click.Path(path_type=Path))
@click.option("--verbose", "-v", is_flag=True)
@click.option("--quiet", "-q", is_flag=True)
def enrich(
    path: Path, recursive: bool, model: str, ollama_url: str,
    key_path: Path | None, force: bool, dry_run: bool,
    output_dir: Path | None, verbose: bool, quiet: bool,
) -> None:
    """Enrich one file or all supported files in a directory."""
    opts = EnrichOptions(
        model=model, ollama_url=ollama_url, key_path=key_path,
        force=force, dry_run=dry_run, output_dir=output_dir,
        recursive=recursive, verbose=verbose,
    )
    if dry_run and not quiet:
        console.print("[yellow]Dry run — no files will be modified.[/yellow]")

    if path.is_file():
        result = enrich_file(path, opts)
        _print_enrich_result(result, quiet)
    else:
        results = enrich_directory(path, opts)
        _print_enrich_summary(results, quiet)


def _print_enrich_result(result, quiet: bool) -> None:
    if quiet:
        return
    if result.skipped:
        console.print(f"[dim]Skipped:[/dim] {result.path.name} — {result.error}")
    elif result.success:
        if result.error:
            console.print(f"[green]✓[/green] {result.path.name} (dry run)")
        else:
            console.print(
                f"[green]✓[/green] {result.path.name} "
                f"v{result.version} · {result.regions}r {result.figures}f {result.tables}t "
                f"({result.elapsed:.1f}s)"
            )
    else:
        console.print(f"[red]✗[/red] {result.path.name} — {result.error}")


def _print_enrich_summary(results: list, quiet: bool) -> None:
    if quiet:
        return
    enriched = [r for r in results if r.success and not r.skipped]
    skipped = [r for r in results if r.skipped]
    errors = [r for r in results if not r.success and not r.skipped]
    console.print(f"\nDone. {len(enriched)} enriched, {len(skipped)} skipped, {len(errors)} errors.")


# ── read ──────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json", "yaml"]), default="text")
def read(file: Path, fmt: str) -> None:
    """Read and display the LLMind layer from a file."""
    meta = read_llmind_meta(file)
    if meta is None:
        console.print(f"[red]No LLMind layer found in {file.name}[/red]")
        sys.exit(1)

    layer = meta.current
    if fmt == "json":
        click.echo(json.dumps(layer_to_dict(layer), indent=2, ensure_ascii=False))
    elif fmt == "yaml":
        click.echo(yaml.dump(layer_to_dict(layer), allow_unicode=True))
    else:
        _print_layer_text(layer, meta)


def _print_layer_text(layer, meta) -> None:
    console.print(f"[bold]LLMind Layer v{layer.version}[/bold] · {layer.timestamp}")
    console.print(f"  Generator : {layer.generator} ({layer.generator_model})")
    console.print(f"  Language  : {layer.language}")
    console.print(f"  Checksum  : {layer.checksum[:16]}…")
    console.print(f"  Key ID    : {layer.key_id}")
    console.print(f"  Layers    : {meta.layer_count}")
    console.rule("Description")
    console.print(layer.description)
    console.rule("Text")
    console.print(layer.text)


# ── history ───────────────────────────────────────────────────────────────────

@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(["text", "json", "yaml"]), default="text")
def history(file: Path, fmt: str) -> None:
    """Show the full version history of layers in a file."""
    meta = read_llmind_meta(file)
    if meta is None:
        console.print(f"[red]No LLMind layer found in {file.name}[/red]")
        sys.exit(1)

    layers_data = [layer_to_dict(l) for l in meta.layers]
    if fmt == "json":
        click.echo(json.dumps(layers_data, indent=2, ensure_ascii=False))
    elif fmt == "yaml":
        click.echo(yaml.dump(layers_data, allow_unicode=True))
    else:
        for layer in meta.layers:
            console.print(
                f"  [bold]v{layer.version}[/bold] · {layer.timestamp} · "
                f"{layer.generator_model} · checksum={layer.checksum[:12]}…"
            )
```

Note: `yaml` is not yet in dependencies. Add it to `pyproject.toml`:

```toml
# In llmind-cli/pyproject.toml, add to dependencies:
"pyyaml>=6.0",
```

Then run `pip install -e ".[dev]"` again.

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_cli.py -v -k "enrich or read or history"
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/cli.py llmind-cli/pyproject.toml
git commit -m "feat: add enrich, read, history CLI commands"
```

---

## Task 14: CLI — verify, strip, watch

**Files:**
- Modify: `llmind-cli/llmind/cli.py` (append commands)
- Modify: `llmind-cli/tests/test_cli.py` (append tests)

- [ ] **Step 1: Append verify/strip/watch tests to `test_cli.py`**

```python
# Append to llmind-cli/tests/test_cli.py

from llmind.models import VerifyResult


def test_verify_fresh(jpeg_file: Path):
    runner = CliRunner()
    mock_result = VerifyResult(
        path=jpeg_file, has_layer=True, checksum_valid=True,
        signature_valid=None, layer_count=1, current_version=1,
    )
    with patch("llmind.cli.verify_file", return_value=mock_result):
        result = runner.invoke(main, ["verify", str(jpeg_file)])
    assert result.exit_code == 0
    assert "fresh" in result.output.lower() or "✓" in result.output


def test_verify_stale(jpeg_file: Path):
    runner = CliRunner()
    mock_result = VerifyResult(
        path=jpeg_file, has_layer=True, checksum_valid=False,
        signature_valid=None, layer_count=1, current_version=1,
    )
    with patch("llmind.cli.verify_file", return_value=mock_result):
        result = runner.invoke(main, ["verify", str(jpeg_file)])
    assert "stale" in result.output.lower() or "modified" in result.output.lower()


def test_strip_requires_key(jpeg_file: Path):
    runner = CliRunner()
    result = runner.invoke(main, ["strip", str(jpeg_file)])
    assert result.exit_code != 0


def test_strip_wrong_key_id_aborts(jpeg_file: Path, tmp_path: Path):
    runner = CliRunner()
    # Inject a layer with key_id "abcdef1234567890"
    from llmind.injector import inject
    from conftest import SAMPLE_XMP
    enriched = tmp_path / "enriched.jpg"
    inject(jpeg_file, SAMPLE_XMP, enriched)
    # Key file with mismatched key_id
    import json as _json
    from llmind.crypto import generate_key, derive_key_id
    wrong_key = generate_key()
    wrong_kid = derive_key_id(wrong_key)
    key_file = tmp_path / "wrong.key"
    key_file.write_text(_json.dumps({
        "key_id": wrong_kid, "creation_key": wrong_key,
        "created": "2026-04-09T12:00:00Z", "file": "enriched.jpg", "note": "",
    }))
    result = runner.invoke(main, ["strip", str(enriched), "--key", str(key_file)])
    assert result.exit_code != 0 or "mismatch" in result.output.lower()


def test_watch_existing_mode_calls_enrich_directory(tmp_path: Path):
    runner = CliRunner()
    with patch("llmind.cli.run_watch") as mock_watch:
        result = runner.invoke(main, ["watch", "--mode", "existing", str(tmp_path)])
    mock_watch.assert_called_once()
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_cli.py -v -k "verify or strip or watch"
```

Expected: fail (commands not yet in cli.py)

- [ ] **Step 3: Append verify, strip, watch commands to `cli.py`**

Add these two lines to the import block at the **top** of `cli.py` (after the existing imports):

```python
from llmind.injector import remove_llmind_xmp
from llmind.watcher import WatchMode, run_watch
```

Then append the following command functions after `history`:

```python
# Append to llmind-cli/llmind/cli.py (after history command — imports already added above)


# ── verify ────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--recursive", "-r", is_flag=True)
@click.option("--key", "key_path", type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", "-v", is_flag=True)
def verify(path: Path, recursive: bool, key_path: Path | None, verbose: bool) -> None:
    """Check checksum freshness and signature validity."""
    if path.is_file():
        result = verify_file(path, key_path)
        _print_verify_result(result, verbose)
    else:
        results = verify_directory(path, key_path)
        for r in results:
            _print_verify_result(r, verbose)


def _print_verify_result(result, verbose: bool) -> None:
    if not result.has_layer:
        console.print(f"[dim]–[/dim] {result.path.name}: no LLMind layer")
        return
    freshness = "[green]fresh[/green]" if result.checksum_valid else "[red]STALE[/red]"
    sig = ""
    if result.signature_valid is True:
        sig = " · sig [green]✓[/green]"
    elif result.signature_valid is False:
        sig = " · sig [red]INVALID[/red]"
    console.print(f"{result.path.name}: {freshness} (v{result.current_version}){sig}")


# ── strip ─────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--key", "key_path", type=click.Path(exists=True, path_type=Path), required=True)
def strip(file: Path, key_path: Path) -> None:
    """Remove LLMind layer (requires creation key)."""
    from llmind.crypto import load_key_file
    meta = read_llmind_meta(file)
    if meta is None:
        console.print("[red]No LLMind layer found.[/red]")
        sys.exit(1)

    kf = load_key_file(key_path)
    if kf.key_id != meta.current.key_id:
        console.print(
            f"[red]Key mismatch.[/red] File key_id: {meta.current.key_id}, "
            f"provided key_id: {kf.key_id}"
        )
        sys.exit(1)

    original_size = file.stat().st_size
    remove_llmind_xmp(file, file)
    stripped_size = file.stat().st_size
    console.print(
        f"[green]✓[/green] Stripped {file.name} "
        f"({original_size:,} → {stripped_size:,} bytes, "
        f"-{original_size - stripped_size:,} bytes)"
    )


# ── watch ─────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--mode", type=click.Choice(["new", "backfill", "existing"]), default="new")
@click.option("--recursive", "-r", is_flag=True)
@click.option("--model", "-m", default="qwen2.5-vl:7b", show_default=True)
@click.option("--ollama-url", default="http://localhost:11434", show_default=True)
@click.option("--log-file", type=click.Path(path_type=Path))
@click.option("--verbose", "-v", is_flag=True)
def watch(
    directory: Path, mode: str, recursive: bool, model: str,
    ollama_url: str, log_file: Path | None, verbose: bool,
) -> None:
    """Watch a folder and auto-enrich new files."""
    if log_file:
        import logging
        logging.basicConfig(
            filename=str(log_file),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )

    opts = EnrichOptions(model=model, ollama_url=ollama_url, recursive=recursive, verbose=verbose)
    watch_mode = WatchMode(mode)
    run_watch(directory, opts, watch_mode)
```

- [ ] **Step 4: Run all CLI tests**

```bash
pytest tests/test_cli.py -v
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/cli.py llmind-cli/tests/test_cli.py
git commit -m "feat: add verify, strip, watch CLI commands"
```

---

## Task 15: Coverage Gate

**Files:**
- None modified — run coverage and fix gaps

- [ ] **Step 1: Run full test suite with coverage**

```bash
cd llmind-cli && pytest --cov=llmind --cov-report=term-missing -v
```

- [ ] **Step 2: Check coverage is ≥ 80%**

Expected output ends with something like:
```
TOTAL    ...    82%
```

If coverage is below 80%, look at the `Missing` column in the report. Common gaps:
- `ollama.py`: `_pdf_to_images` — add a test that mocks `convert_from_path`
- `watcher.py`: Observer start/stop path — integration test with a real temp dir event
- `cli.py`: error paths in strip/verify — add CliRunner tests for each

- [ ] **Step 3: Add missing test coverage for `ollama._pdf_to_images` mock**

```python
# Append to llmind-cli/tests/test_ollama.py

@resp_lib.activate
def test_extract_pdf_merges_pages(tmp_path: Path):
    """PDF extraction merges multiple pages."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 stub")
    fake_img = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # fake JPEG bytes

    with patch("llmind.ollama._pdf_to_images", return_value=[fake_img, fake_img]):
        resp_lib.add(
            resp_lib.POST, f"{OLLAMA_URL}/api/chat",
            json={"message": {"content": json.dumps(VALID_RESPONSE)}}, status=200,
        )
        resp_lib.add(
            resp_lib.POST, f"{OLLAMA_URL}/api/chat",
            json={"message": {"content": json.dumps(VALID_RESPONSE)}}, status=200,
        )
        result = extract(pdf_path, "qwen2.5-vl:7b", OLLAMA_URL)

    assert "PAGE 1" in result.text
    assert "PAGE 2" in result.text
    assert "pages" in result.structure
    assert len(result.structure["pages"]) == 2
```

- [ ] **Step 4: Re-run coverage until ≥ 80%**

```bash
pytest --cov=llmind --cov-report=term-missing -q
```

Expected: `TOTAL ... 80%+`

- [ ] **Step 5: Smoke test the installed CLI**

```bash
llmind --help
llmind enrich --help
llmind read --help
llmind verify --help
llmind strip --help
llmind watch --help
llmind history --help
```

Expected: all commands display usage without errors.

- [ ] **Step 6: Final commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-cli/
git commit -m "test: ensure 80%+ test coverage"
```
