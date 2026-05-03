# Audio Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `llmind-cli` to enrich MP3, WAV, and M4A audio files with XMP-embedded transcripts, summaries, and timestamped segments.

**Architecture:** Mirror the existing vision pipeline with two new modules (`audio.py` for provider dispatch, `audio_injector.py` for format-specific XMP embedding). Extend `models.Layer` with optional audio fields (`segments`, `duration_seconds`, `media_type`). Route by file extension in `enricher.py`, `injector.py`, `reader.py`, and `safety.py`. Signing/verification reuse existing `crypto.py` unchanged.

**Tech Stack:** Python 3.11+, `mutagen` (MP3 ID3v2), `faster-whisper` (local STT), OpenAI Whisper API, Gemini File API, stdlib (RIFF/MP4 box manipulation), pytest.

**Spec:** `docs/superpowers/specs/2026-04-18-audio-enrichment-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|----------------|
| `llmind-cli/llmind/audio.py` | Provider dispatch. `query_audio(path, provider, model, api_key) -> AudioExtraction`. Per-provider impls inline (OpenAI, Gemini, local Whisper). `AUDIO_PROVIDER_DEFAULTS`, `AUDIO_SUMMARIZER_DEFAULTS`, `UnsupportedProviderError`. |
| `llmind-cli/llmind/audio_injector.py` | Format-aware XMP embedding. `inject_audio(path, xmp)`, `read_xmp_audio(path)`, `remove_llmind_xmp_audio(path)`. Dispatches to `_inject_mp3`, `_inject_wav`, `_inject_m4a` and their readers/removers. |
| `llmind-cli/tests/test_audio_injector_mp3.py` | Round-trip injection tests for MP3. |
| `llmind-cli/tests/test_audio_injector_wav.py` | Round-trip injection tests for WAV. |
| `llmind-cli/tests/test_audio_injector_m4a.py` | Round-trip injection tests for M4A. |
| `llmind-cli/tests/test_audio_dispatch.py` | `query_audio` provider routing tests (mocked clients). |
| `llmind-cli/tests/test_audio_models.py` | `Segment` dataclass + `Layer` extended-field tests. |
| `llmind-cli/tests/test_audio_xmp.py` | XMP build/parse round-trip with audio fields + backwards compat. |
| `llmind-cli/tests/test_audio_signing.py` | Sign/verify audio layer; verify old image signatures still valid. |
| `llmind-cli/tests/test_audio_enricher.py` | End-to-end enrichment with mocked `query_audio`. |
| `llmind-cli/tests/fixtures/audio/silent.mp3` | ~10 KB silent MP3 fixture. |
| `llmind-cli/tests/fixtures/audio/silent.wav` | Minimal silent WAV fixture. |
| `llmind-cli/tests/fixtures/audio/silent.m4a` | ~20 KB silent M4A fixture. |
| `llmind-cli/tests/fixtures/audio/generate_fixtures.py` | Deterministic fixture generator (run once, outputs committed). |

### Modified files

| File | Change |
|------|--------|
| `llmind-cli/llmind/models.py` | Add `Segment` dataclass. Extend `Layer` with `segments`, `duration_seconds`, `media_type`. |
| `llmind-cli/llmind/xmp.py` | Serialize/parse audio fields. Backwards-compatible defaults. |
| `llmind-cli/llmind/safety.py` | Add audio extensions + per-provider size checks. |
| `llmind-cli/llmind/injector.py` | Top-level dispatcher routes audio suffixes to `audio_injector`. |
| `llmind-cli/llmind/reader.py` | `_read_raw_xmp` routes audio suffixes to `audio_injector.read_xmp_audio`. |
| `llmind-cli/llmind/enricher.py` | Add audio branch in `_enrich` and `_reenrich`; `is_already_enriched_file` recognizes audio. |
| `llmind-cli/llmind/watcher.py` | No code changes required (extension-driven) — add regression test. |
| `llmind-cli/pyproject.toml` | Add `mutagen` to core deps; `faster-whisper` as optional extra. |

---

## Task Overview

1. Fixtures — generate and commit tiny silent audio files
2. `Segment` dataclass + `Layer` field extension
3. XMP serializer/parser updates for audio fields
4. XMP backwards-compat test
5. Safety checks for audio
6. MP3 injector helpers (`mutagen` PRIV:XMP)
7. WAV injector helpers (`_PMX` RIFF chunk)
8. M4A injector helpers (top-level `uuid` atom)
9. `audio_injector.py` public dispatch
10. Wire `injector.inject` and `reader._read_raw_xmp`
11. `AudioExtraction`/`Segment`, `UnsupportedProviderError`, `AUDIO_PROVIDER_DEFAULTS`
12. OpenAI Whisper provider implementation
13. Gemini audio provider implementation
14. `faster-whisper` local provider implementation
15. `query_audio` dispatch
16. `enricher._enrich` audio branch
17. `enricher._reenrich` audio branch
18. `is_already_enriched_file` audio support
19. Signing/verification regression test
20. End-to-end enrichment test with mocked provider
21. `pyproject.toml` dependency update
22. Watcher regression test + docs

---

### Task 1: Commit Silent Audio Fixtures

**Files:**
- Create: `llmind-cli/tests/fixtures/audio/generate_fixtures.py`
- Create: `llmind-cli/tests/fixtures/audio/silent.mp3`
- Create: `llmind-cli/tests/fixtures/audio/silent.wav`
- Create: `llmind-cli/tests/fixtures/audio/silent.m4a`

- [ ] **Step 1: Write the fixture generator**

```python
# llmind-cli/tests/fixtures/audio/generate_fixtures.py
"""Generate deterministic silent audio fixtures for tests.

Run once; commit the outputs. Requires ffmpeg on PATH.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).parent


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True)


def generate_wav(out: Path) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
        "-t", "0.25", "-c:a", "pcm_s16le", str(out),
    ])


def generate_mp3(out: Path) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
        "-t", "0.5", "-b:a", "32k", "-c:a", "libmp3lame", str(out),
    ])


def generate_m4a(out: Path) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
        "-t", "0.5", "-b:a", "32k", "-c:a", "aac", str(out),
    ])


if __name__ == "__main__":
    generate_wav(HERE / "silent.wav")
    generate_mp3(HERE / "silent.mp3")
    generate_m4a(HERE / "silent.m4a")
    print("Fixtures written to", HERE)
```

- [ ] **Step 2: Generate the fixtures**

Run: `python llmind-cli/tests/fixtures/audio/generate_fixtures.py`
Expected: three silent files appear in `tests/fixtures/audio/`. Each <30 KB.

- [ ] **Step 3: Commit**

```bash
git add llmind-cli/tests/fixtures/audio/
git commit -m "test: add silent audio fixtures for enrichment tests"
```

---

### Task 2: Add `Segment` and Extend `Layer`

**Files:**
- Modify: `llmind-cli/llmind/models.py`
- Test: `llmind-cli/tests/test_audio_models.py`

- [ ] **Step 1: Write failing test**

```python
# llmind-cli/tests/test_audio_models.py
from llmind.models import Layer, Segment


def test_segment_is_frozen():
    s = Segment(start=0.0, end=1.5, text="hello")
    assert s.start == 0.0
    assert s.end == 1.5
    assert s.text == "hello"


def test_layer_audio_fields_default_none():
    layer = Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="whisper-1",
        checksum="a" * 64, language="en", description="A voice memo.",
        text="hello world", structure={}, key_id="",
    )
    assert layer.segments is None
    assert layer.duration_seconds is None
    assert layer.media_type == "image"


def test_layer_audio_fields_populated():
    seg = (Segment(0.0, 1.0, "hi"),)
    layer = Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="whisper-1",
        checksum="a" * 64, language="en", description="summary",
        text="hi", structure={}, key_id="",
        segments=seg, duration_seconds=1.0, media_type="audio",
    )
    assert layer.media_type == "audio"
    assert layer.segments == seg
    assert layer.duration_seconds == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llmind-cli && pytest tests/test_audio_models.py -v`
Expected: FAIL — `Segment` import error.

- [ ] **Step 3: Add `Segment` and extend `Layer`**

```python
# llmind-cli/llmind/models.py — add after ExtractionResult
@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str
```

Then extend `Layer`:

```python
@dataclass(frozen=True)
class Layer:
    version: int
    timestamp: str
    generator: str
    generator_model: str
    checksum: str
    language: str
    description: str
    text: str
    structure: dict
    key_id: str
    signature: str | None = None
    # Audio-only optional fields:
    segments: tuple[Segment, ...] | None = None
    duration_seconds: float | None = None
    media_type: str = "image"   # "image" | "pdf" | "audio"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd llmind-cli && pytest tests/test_audio_models.py -v`
Expected: PASS — all 3 tests.

- [ ] **Step 5: Regression — full suite must still pass**

Run: `cd llmind-cli && pytest -x`
Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add llmind-cli/llmind/models.py llmind-cli/tests/test_audio_models.py
git commit -m "feat(models): add Segment dataclass and audio Layer fields"
```

---

### Task 3: Extend XMP Serializer for Audio Fields

**Files:**
- Modify: `llmind-cli/llmind/xmp.py`
- Test: `llmind-cli/tests/test_audio_xmp.py`

- [ ] **Step 1: Write failing test**

```python
# llmind-cli/tests/test_audio_xmp.py
from llmind.models import Layer, Segment
from llmind.xmp import build_xmp, parse_xmp, layer_to_dict


def _audio_layer(signature: str | None = None) -> Layer:
    return Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="whisper-1",
        checksum="a" * 64, language="en",
        description="A short voice memo greeting.",
        text="hello world", structure={}, key_id="",
        signature=signature,
        segments=(Segment(0.0, 1.0, "hello"), Segment(1.0, 2.0, "world")),
        duration_seconds=2.0,
        media_type="audio",
    )


def test_audio_layer_roundtrip():
    layer = _audio_layer()
    xmp = build_xmp([layer])
    meta = parse_xmp(xmp)
    assert meta.current.media_type == "audio"
    assert meta.current.duration_seconds == 2.0
    assert meta.current.segments == layer.segments


def test_layer_to_dict_includes_audio_fields_when_present():
    layer = _audio_layer()
    d = layer_to_dict(layer, include_signature=False)
    assert d["media_type"] == "audio"
    assert d["duration_seconds"] == 2.0
    assert d["segments"] == [
        {"start": 0.0, "end": 1.0, "text": "hello"},
        {"start": 1.0, "end": 2.0, "text": "world"},
    ]


def test_layer_to_dict_omits_audio_fields_when_absent():
    # Image layer: no audio fields serialized → signatures remain stable
    layer = Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="gpt-4o-mini",
        checksum="b" * 64, language="en",
        description="A photograph.", text="sign text",
        structure={"type": "photo"}, key_id="",
    )
    d = layer_to_dict(layer, include_signature=False)
    assert "media_type" not in d
    assert "duration_seconds" not in d
    assert "segments" not in d
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llmind-cli && pytest tests/test_audio_xmp.py -v`
Expected: FAIL.

- [ ] **Step 3: Update `layer_to_dict`**

Replace the body of `layer_to_dict` in `llmind-cli/llmind/xmp.py` with:

```python
def layer_to_dict(layer: Layer, include_signature: bool = True) -> dict[str, object]:
    d: dict[str, object] = {
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
    # Audio-only fields — serialized only when populated, preserving
    # backwards-compat signatures for existing image/pdf layers.
    if layer.media_type and layer.media_type != "image":
        d["media_type"] = layer.media_type
    if layer.duration_seconds is not None:
        d["duration_seconds"] = layer.duration_seconds
    if layer.segments is not None:
        d["segments"] = [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in layer.segments
        ]
    return d
```

- [ ] **Step 4: Update `parse_xmp` to reconstruct `Segment`s**

In `llmind-cli/llmind/xmp.py`, replace the `Layer(...)` construction inside `parse_xmp` with:

```python
            Layer(
                version=int(d["version"]),
                timestamp=str(d["timestamp"]),
                generator=str(d["generator"]),
                generator_model=str(d["generator_model"]),
                checksum=str(d["checksum"]),
                language=str(d["language"]),
                description=str(d["description"]),
                text=str(d["text"]),
                structure=dict(d.get("structure") or {}),
                key_id=str(d["key_id"]),
                signature=d.get("signature"),
                segments=(
                    tuple(
                        Segment(
                            start=float(seg["start"]),
                            end=float(seg["end"]),
                            text=str(seg["text"]),
                        )
                        for seg in d["segments"]
                    )
                    if d.get("segments") is not None
                    else None
                ),
                duration_seconds=(
                    float(d["duration_seconds"])
                    if d.get("duration_seconds") is not None
                    else None
                ),
                media_type=str(d.get("media_type") or "image"),
            )
```

Also update the import at top of `xmp.py`:

```python
from llmind.models import Layer, LLMindMeta, Segment
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd llmind-cli && pytest tests/test_audio_xmp.py -v`
Expected: PASS.

- [ ] **Step 6: Run full suite for regressions**

Run: `cd llmind-cli && pytest -x`
Expected: all pass (existing image/pdf XMP tests unaffected because audio fields are omitted from their serialized dict).

- [ ] **Step 7: Commit**

```bash
git add llmind-cli/llmind/xmp.py llmind-cli/tests/test_audio_xmp.py
git commit -m "feat(xmp): serialize/parse audio Layer fields with backwards-compat defaults"
```

---

### Task 4: Backwards-Compat XMP Parsing

**Files:**
- Test: `llmind-cli/tests/test_audio_xmp.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `llmind-cli/tests/test_audio_xmp.py`:

```python
# Legacy XMP (no media_type, no segments, no duration) — pre-audio format.
# Must parse successfully and default media_type to "image".
LEGACY_XMP = '''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
    xmlns:llmind="https://llmind.org/ns/1.0/"
    llmind:version="1"
    llmind:format_version="1.0"
    llmind:generator="llmind-cli/0.1.0"
    llmind:generator_model="gpt-4o-mini"
    llmind:timestamp="2026-01-01T00:00:00Z"
    llmind:language="en"
    llmind:checksum="deadbeef"
    llmind:key_id=""
    llmind:signature=""
    llmind:layer_count="1"
    llmind:immutable="true"
    >
      <llmind:description>A photo.</llmind:description>
      <llmind:text>some text</llmind:text>
      <llmind:structure>{}</llmind:structure>
      <llmind:history>[{"version":1,"timestamp":"2026-01-01T00:00:00Z","generator":"llmind-cli/0.1.0","generator_model":"gpt-4o-mini","checksum":"deadbeef","language":"en","description":"A photo.","text":"some text","structure":{},"key_id":"","signature":null}]</llmind:history>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''


def test_legacy_xmp_parses_with_image_defaults():
    meta = parse_xmp(LEGACY_XMP)
    assert meta.current.media_type == "image"
    assert meta.current.segments is None
    assert meta.current.duration_seconds is None
```

- [ ] **Step 2: Run test to verify it passes immediately**

Run: `cd llmind-cli && pytest tests/test_audio_xmp.py::test_legacy_xmp_parses_with_image_defaults -v`
Expected: PASS (Task 3's parser already handles missing keys).

If it fails, fix the `parse_xmp` defaults from Task 3 before continuing.

- [ ] **Step 3: Commit**

```bash
git add llmind-cli/tests/test_audio_xmp.py
git commit -m "test(xmp): verify legacy image XMP parses with media_type='image' default"
```

---

### Task 5: Safety Checks for Audio Extensions

**Files:**
- Modify: `llmind-cli/llmind/safety.py`
- Test: `llmind-cli/tests/test_safety.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `llmind-cli/tests/test_safety.py`:

```python
import pytest
from llmind.safety import is_safe_file, is_audio_file, AUDIO_EXTENSIONS


def test_audio_extensions_set():
    assert AUDIO_EXTENSIONS == frozenset({".mp3", ".wav", ".m4a"})


@pytest.mark.parametrize("name", ["memo.mp3", "memo.MP3", "test.wav", "voice.m4a"])
def test_audio_file_passes_safety(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"\x00" * 32)
    assert is_safe_file(p) is True
    assert is_audio_file(p) is True


def test_image_file_is_not_audio(tmp_path):
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0")
    assert is_audio_file(p) is False


def test_flac_not_supported_yet(tmp_path):
    p = tmp_path / "song.flac"
    p.write_bytes(b"fLaC\x00")
    assert is_safe_file(p) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llmind-cli && pytest tests/test_safety.py::test_audio_extensions_set -v`
Expected: FAIL — `AUDIO_EXTENSIONS` not exported.

- [ ] **Step 3: Update `safety.py`**

Replace `llmind-cli/llmind/safety.py` with:

```python
from pathlib import Path

_BLOCKED_NAMES: frozenset[str] = frozenset(
    {"Thumbs.db", "desktop.ini", ".DS_Store", "Icon\r"}
)
_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".pdf"})
AUDIO_EXTENSIONS: frozenset[str] = frozenset({".mp3", ".wav", ".m4a"})
_SUPPORTED_EXTENSIONS: frozenset[str] = _IMAGE_EXTENSIONS | AUDIO_EXTENSIONS


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


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
        for part in path.parts[:-1]:
            if part.startswith(".") or part == ".llmind-keys":
                return False
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            return False
        return True
    except (OSError, PermissionError):
        return False
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd llmind-cli && pytest tests/test_safety.py -v`
Expected: PASS — new tests and existing ones.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/safety.py llmind-cli/tests/test_safety.py
git commit -m "feat(safety): accept mp3/wav/m4a audio files"
```

---

### Task 6: MP3 Injection via `mutagen` PRIV:XMP

**Files:**
- Create: `llmind-cli/llmind/audio_injector.py` (MP3 helpers only this task)
- Test: `llmind-cli/tests/test_audio_injector_mp3.py`

- [ ] **Step 1: Write failing test**

```python
# llmind-cli/tests/test_audio_injector_mp3.py
import shutil
from pathlib import Path

import pytest

from llmind.audio_injector import (
    _inject_mp3, _read_xmp_mp3, _remove_llmind_xmp_mp3,
)

FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "silent.mp3"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


def _mpeg_audio_bytes(path: Path) -> bytes:
    """Return MP3 audio frames only (skip any ID3v2 header)."""
    data = path.read_bytes()
    if data[:3] == b"ID3":
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) \
             | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        return data[10 + size:]
    return data


def test_inject_roundtrip(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    _inject_mp3(dst, SAMPLE_XMP)
    assert _read_xmp_mp3(dst) == SAMPLE_XMP


def test_inject_replaces_existing(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    _inject_mp3(dst, SAMPLE_XMP)
    updated = SAMPLE_XMP.replace('version="1"', 'version="2"')
    _inject_mp3(dst, updated)
    assert _read_xmp_mp3(dst) == updated
    # Ensure no duplicate PRIV:XMP frames remain
    from mutagen.id3 import ID3
    tags = ID3(dst)
    priv_frames = [f for f in tags.getall("PRIV") if f.owner == "XMP"]
    assert len(priv_frames) == 1


def test_audio_samples_unchanged_after_inject(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    original_samples = _mpeg_audio_bytes(dst)
    _inject_mp3(dst, SAMPLE_XMP)
    assert _mpeg_audio_bytes(dst) == original_samples


def test_remove_xmp(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    _inject_mp3(dst, SAMPLE_XMP)
    assert _remove_llmind_xmp_mp3(dst) is True
    assert _read_xmp_mp3(dst) is None


def test_remove_xmp_absent(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    assert _remove_llmind_xmp_mp3(dst) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llmind-cli && pytest tests/test_audio_injector_mp3.py -v`
Expected: FAIL — `audio_injector` module does not exist.

- [ ] **Step 3: Create `audio_injector.py` with MP3 helpers**

```python
# llmind-cli/llmind/audio_injector.py
"""Format-aware XMP injection for audio files (MP3/WAV/M4A).

Follows Adobe XMP spec slots:
- MP3  → ID3v2 PRIV frame, owner "XMP"
- WAV  → RIFF "_PMX" top-level chunk
- M4A  → top-level "uuid" atom, UUID BE7ACFCB-97A9-42E8-9C71-999491E3AFAC
"""
from __future__ import annotations

from pathlib import Path

_LLMIND_MARKER = b"https://llmind.org/ns/1.0/"

# ── MP3 ─────────────────────────────────────────────────────────────────────

def _inject_mp3(path: Path, xmp_string: str) -> None:
    from mutagen.id3 import ID3, ID3NoHeaderError, PRIV
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    # Remove any prior LLMind PRIV:XMP frames (defensive, allows replace).
    priv_frames = [f for f in tags.getall("PRIV") if f.owner == "XMP"]
    for f in priv_frames:
        tags.delall("PRIV:XMP")
        break
    tags.add(PRIV(owner="XMP", data=xmp_string.encode("utf-8")))
    tags.save(path)


def _read_xmp_mp3(path: Path) -> str | None:
    from mutagen.id3 import ID3, ID3NoHeaderError
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return None
    for frame in tags.getall("PRIV"):
        if frame.owner == "XMP":
            data = frame.data
            if _LLMIND_MARKER in data:
                return data.decode("utf-8")
    return None


def _remove_llmind_xmp_mp3(path: Path) -> bool:
    from mutagen.id3 import ID3, ID3NoHeaderError
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return False
    priv_frames = [f for f in tags.getall("PRIV") if f.owner == "XMP"
                   and _LLMIND_MARKER in f.data]
    if not priv_frames:
        return False
    tags.delall("PRIV:XMP")
    tags.save(path)
    return True
```

- [ ] **Step 4: Ensure `mutagen` is installed for dev**

Run: `pip install mutagen`
Expected: installs (will be added to `pyproject.toml` in Task 21).

- [ ] **Step 5: Run tests to verify pass**

Run: `cd llmind-cli && pytest tests/test_audio_injector_mp3.py -v`
Expected: PASS — all 5 MP3 tests.

- [ ] **Step 6: Commit**

```bash
git add llmind-cli/llmind/audio_injector.py llmind-cli/tests/test_audio_injector_mp3.py
git commit -m "feat(audio): MP3 XMP injection via mutagen PRIV:XMP"
```

---

### Task 7: WAV Injection via RIFF `_PMX` Chunk

**Files:**
- Modify: `llmind-cli/llmind/audio_injector.py` (append WAV helpers)
- Test: `llmind-cli/tests/test_audio_injector_wav.py`

- [ ] **Step 1: Write failing test**

```python
# llmind-cli/tests/test_audio_injector_wav.py
import shutil
import struct
from pathlib import Path

from llmind.audio_injector import (
    _inject_wav, _read_xmp_wav, _remove_llmind_xmp_wav,
)

FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "silent.wav"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


def _riff_chunks(data: bytes):
    """Yield (chunk_id, payload) tuples at the RIFF top level."""
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    i = 12
    while i < len(data):
        chunk_id = data[i:i + 4]
        size = struct.unpack("<I", data[i + 4:i + 8])[0]
        payload = data[i + 8:i + 8 + size]
        yield chunk_id, payload
        i += 8 + size + (size & 1)


def _wav_data_payload(path: Path) -> bytes:
    for cid, payload in _riff_chunks(path.read_bytes()):
        if cid == b"data":
            return payload
    return b""


def test_inject_roundtrip(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    assert _read_xmp_wav(dst) == SAMPLE_XMP


def test_riff_size_header_updated(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    data = dst.read_bytes()
    declared = struct.unpack("<I", data[4:8])[0]
    assert declared == len(data) - 8


def test_inject_replaces_existing(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    updated = SAMPLE_XMP.replace('version="1"', 'version="2"')
    _inject_wav(dst, updated)
    assert _read_xmp_wav(dst) == updated
    pmx_count = sum(1 for cid, _ in _riff_chunks(dst.read_bytes()) if cid == b"_PMX")
    assert pmx_count == 1


def test_data_chunk_unchanged(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    before = _wav_data_payload(dst)
    _inject_wav(dst, SAMPLE_XMP)
    assert _wav_data_payload(dst) == before


def test_remove_xmp(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    assert _remove_llmind_xmp_wav(dst) is True
    assert _read_xmp_wav(dst) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llmind-cli && pytest tests/test_audio_injector_wav.py -v`
Expected: FAIL — helpers not yet defined.

- [ ] **Step 3: Append WAV helpers to `audio_injector.py`**

Append to `llmind-cli/llmind/audio_injector.py`:

```python
import struct as _struct

# ── WAV / RIFF ──────────────────────────────────────────────────────────────

_PMX_ID = b"_PMX"


def _iter_riff_chunks(data: bytes):
    """Yield (offset, chunk_id, size, payload)."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Not a RIFF/WAVE file")
    i = 12
    while i + 8 <= len(data):
        chunk_id = data[i:i + 4]
        size = _struct.unpack("<I", data[i + 4:i + 8])[0]
        payload = data[i + 8:i + 8 + size]
        yield i, chunk_id, size, payload
        i += 8 + size + (size & 1)


def _strip_pmx_chunks(data: bytes) -> bytes:
    out = bytearray(data[:12])  # RIFF header preserved
    for _, cid, size, payload in _iter_riff_chunks(data):
        if cid == _PMX_ID and _LLMIND_MARKER in payload:
            continue
        out += cid + _struct.pack("<I", size) + payload
        if size & 1:
            out += b"\x00"
    new_riff_size = len(out) - 8
    out[4:8] = _struct.pack("<I", new_riff_size)
    return bytes(out)


def _inject_wav(path: Path, xmp_string: str) -> None:
    data = path.read_bytes()
    data = _strip_pmx_chunks(data)
    payload = xmp_string.encode("utf-8")
    chunk = _PMX_ID + _struct.pack("<I", len(payload)) + payload
    if len(payload) & 1:
        chunk += b"\x00"
    out = bytearray(data + chunk)
    new_riff_size = len(out) - 8
    out[4:8] = _struct.pack("<I", new_riff_size)
    path.write_bytes(bytes(out))


def _read_xmp_wav(path: Path) -> str | None:
    data = path.read_bytes()
    try:
        chunks = list(_iter_riff_chunks(data))
    except ValueError:
        return None
    for _, cid, _, payload in chunks:
        if cid == _PMX_ID and _LLMIND_MARKER in payload:
            return payload.decode("utf-8")
    return None


def _remove_llmind_xmp_wav(path: Path) -> bool:
    data = path.read_bytes()
    new_data = _strip_pmx_chunks(data)
    if new_data == data:
        return False
    path.write_bytes(new_data)
    return True
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd llmind-cli && pytest tests/test_audio_injector_wav.py -v`
Expected: PASS — all 5 WAV tests.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio_injector.py llmind-cli/tests/test_audio_injector_wav.py
git commit -m "feat(audio): WAV XMP injection via RIFF _PMX chunk"
```

---

### Task 8: M4A Injection via Top-Level `uuid` Atom

**Files:**
- Modify: `llmind-cli/llmind/audio_injector.py` (append M4A helpers)
- Test: `llmind-cli/tests/test_audio_injector_m4a.py`

- [ ] **Step 1: Write failing test**

```python
# llmind-cli/tests/test_audio_injector_m4a.py
import shutil
import struct
from pathlib import Path

from llmind.audio_injector import (
    _inject_m4a, _read_xmp_m4a, _remove_llmind_xmp_m4a,
    XMP_UUID,
)

FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "silent.m4a"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


def _iter_boxes(data: bytes):
    """Yield (offset, atom_type, size, payload) for top-level MP4 boxes."""
    i = 0
    while i + 8 <= len(data):
        size = struct.unpack(">I", data[i:i + 4])[0]
        atom = data[i + 4:i + 8]
        if size == 1:
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            payload = data[i + 16:i + size]
        elif size == 0:
            payload = data[i + 8:]
            yield i, atom, len(data) - i, payload
            break
        else:
            payload = data[i + 8:i + size]
        yield i, atom, size, payload
        i += size


def _mdat_payload(path: Path) -> bytes:
    for _, atom, _, payload in _iter_boxes(path.read_bytes()):
        if atom == b"mdat":
            return payload
    return b""


def test_inject_roundtrip(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    _inject_m4a(dst, SAMPLE_XMP)
    assert _read_xmp_m4a(dst) == SAMPLE_XMP


def test_inject_replaces_existing(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    _inject_m4a(dst, SAMPLE_XMP)
    updated = SAMPLE_XMP.replace('version="1"', 'version="2"')
    _inject_m4a(dst, updated)
    assert _read_xmp_m4a(dst) == updated
    uuid_count = 0
    for _, atom, _, payload in _iter_boxes(dst.read_bytes()):
        if atom == b"uuid" and payload[:16] == XMP_UUID:
            uuid_count += 1
    assert uuid_count == 1


def test_mdat_unchanged(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    before = _mdat_payload(dst)
    _inject_m4a(dst, SAMPLE_XMP)
    assert _mdat_payload(dst) == before


def test_remove_xmp(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    _inject_m4a(dst, SAMPLE_XMP)
    assert _remove_llmind_xmp_m4a(dst) is True
    assert _read_xmp_m4a(dst) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llmind-cli && pytest tests/test_audio_injector_m4a.py -v`
Expected: FAIL — helpers not yet defined.

- [ ] **Step 3: Append M4A helpers to `audio_injector.py`**

Append to `llmind-cli/llmind/audio_injector.py`:

```python
# ── M4A / MP4 ───────────────────────────────────────────────────────────────

XMP_UUID = bytes.fromhex("BE7ACFCB97A942E89C71999491E3AFAC")


def _iter_mp4_boxes(data: bytes):
    """Yield (offset, atom_type, full_size, payload) for top-level MP4 boxes."""
    i = 0
    while i + 8 <= len(data):
        size = _struct.unpack(">I", data[i:i + 4])[0]
        atom = data[i + 4:i + 8]
        header = 8
        if size == 1:
            if i + 16 > len(data):
                break
            size = _struct.unpack(">Q", data[i + 8:i + 16])[0]
            header = 16
        elif size == 0:
            size = len(data) - i
        if size < header or i + size > len(data):
            break
        payload = data[i + header:i + size]
        yield i, atom, size, payload, header
        i += size


def _build_uuid_box(uuid_bytes: bytes, payload: bytes) -> bytes:
    """Build a top-level MP4 uuid box: [size:4][type:'uuid'][uuid:16][payload]."""
    assert len(uuid_bytes) == 16
    total = 8 + 16 + len(payload)
    return _struct.pack(">I", total) + b"uuid" + uuid_bytes + payload


def _strip_llmind_uuid_boxes(data: bytes) -> bytes:
    out = bytearray()
    for _, atom, size, payload, header in _iter_mp4_boxes(data):
        if atom == b"uuid" and payload[:16] == XMP_UUID and _LLMIND_MARKER in payload[16:]:
            continue
        box_size = header + len(payload)
        if header == 16:
            out += _struct.pack(">I", 1) + atom + _struct.pack(">Q", box_size) + payload
        else:
            out += _struct.pack(">I", box_size) + atom + payload
    return bytes(out)


def _inject_m4a(path: Path, xmp_string: str) -> None:
    data = path.read_bytes()
    data = _strip_llmind_uuid_boxes(data)
    xmp_bytes = xmp_string.encode("utf-8")
    box = _build_uuid_box(XMP_UUID, xmp_bytes)
    # Append at end — top level, safe for QuickTime/iTunes parsers.
    path.write_bytes(data + box)


def _read_xmp_m4a(path: Path) -> str | None:
    data = path.read_bytes()
    for _, atom, _size, payload, _header in _iter_mp4_boxes(data):
        if atom == b"uuid" and payload[:16] == XMP_UUID:
            xmp = payload[16:]
            if _LLMIND_MARKER in xmp:
                return xmp.decode("utf-8")
    return None


def _remove_llmind_xmp_m4a(path: Path) -> bool:
    data = path.read_bytes()
    new_data = _strip_llmind_uuid_boxes(data)
    if new_data == data:
        return False
    path.write_bytes(new_data)
    return True
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd llmind-cli && pytest tests/test_audio_injector_m4a.py -v`
Expected: PASS — all 4 M4A tests.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio_injector.py llmind-cli/tests/test_audio_injector_m4a.py
git commit -m "feat(audio): M4A XMP injection via top-level uuid atom"
```

---

### Task 9: Public Dispatch in `audio_injector.py`

**Files:**
- Modify: `llmind-cli/llmind/audio_injector.py` (append dispatch API)
- Test: new cases in `llmind-cli/tests/test_audio_injector_mp3.py` (cross-format dispatch can live in any existing test file)

- [ ] **Step 1: Write failing test**

Create `llmind-cli/tests/test_audio_injector_dispatch.py`:

```python
import shutil
from pathlib import Path

import pytest

from llmind.audio_injector import (
    inject_audio, read_xmp_audio, remove_llmind_xmp_audio,
)

FIXTURES = Path(__file__).parent / "fixtures" / "audio"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


@pytest.mark.parametrize("name", ["silent.mp3", "silent.wav", "silent.m4a"])
def test_roundtrip(tmp_path, name):
    dst = tmp_path / name
    shutil.copy(FIXTURES / name, dst)
    inject_audio(dst, SAMPLE_XMP)
    assert read_xmp_audio(dst) == SAMPLE_XMP
    assert remove_llmind_xmp_audio(dst) is True
    assert read_xmp_audio(dst) is None


def test_unsupported_format(tmp_path):
    dst = tmp_path / "song.flac"
    dst.write_bytes(b"fLaC")
    with pytest.raises(ValueError, match="Unsupported"):
        inject_audio(dst, SAMPLE_XMP)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd llmind-cli && pytest tests/test_audio_injector_dispatch.py -v`
Expected: FAIL — public dispatch functions not defined.

- [ ] **Step 3: Append public dispatch to `audio_injector.py`**

Append to `llmind-cli/llmind/audio_injector.py`:

```python
# ── Public dispatch ─────────────────────────────────────────────────────────

def inject_audio(path: Path, xmp_string: str) -> None:
    """Inject XMP into an audio file, replacing any prior LLMind XMP packet."""
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        _inject_mp3(path, xmp_string)
    elif suffix == ".wav":
        _inject_wav(path, xmp_string)
    elif suffix == ".m4a":
        _inject_m4a(path, xmp_string)
    else:
        raise ValueError(f"Unsupported audio format: {suffix}")


def read_xmp_audio(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return _read_xmp_mp3(path)
    if suffix == ".wav":
        return _read_xmp_wav(path)
    if suffix == ".m4a":
        return _read_xmp_m4a(path)
    raise ValueError(f"Unsupported audio format: {suffix}")


def remove_llmind_xmp_audio(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return _remove_llmind_xmp_mp3(path)
    if suffix == ".wav":
        return _remove_llmind_xmp_wav(path)
    if suffix == ".m4a":
        return _remove_llmind_xmp_m4a(path)
    raise ValueError(f"Unsupported audio format: {suffix}")
```

- [ ] **Step 4: Run tests**

Run: `cd llmind-cli && pytest tests/test_audio_injector_dispatch.py -v`
Expected: PASS — all 4 parametrized cases + unsupported-format.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio_injector.py llmind-cli/tests/test_audio_injector_dispatch.py
git commit -m "feat(audio): public inject/read/remove dispatch for audio formats"
```

---

### Task 10: Wire `injector.inject` and `reader._read_raw_xmp`

**Files:**
- Modify: `llmind-cli/llmind/injector.py`
- Modify: `llmind-cli/llmind/reader.py`
- Test: `llmind-cli/tests/test_reader.py` (extend), `llmind-cli/tests/test_injector.py` (extend)

- [ ] **Step 1: Write failing test for reader**

Append to `llmind-cli/tests/test_reader.py`:

```python
import shutil
from pathlib import Path

from llmind.audio_injector import inject_audio
from llmind.reader import read, has_llmind_layer

AUDIO_FIX = Path(__file__).parent / "fixtures" / "audio"
MINIMAL_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '    <rdf:Description rdf:about=""'
    '    xmlns:llmind="https://llmind.org/ns/1.0/"'
    '    llmind:version="1"'
    '    llmind:format_version="1.0"'
    '    llmind:generator="llmind-cli/0.1.0"'
    '    llmind:generator_model="whisper-1"'
    '    llmind:timestamp="2026-04-18T00:00:00Z"'
    '    llmind:language="en"'
    '    llmind:checksum="c"'
    '    llmind:key_id=""'
    '    llmind:signature=""'
    '    llmind:layer_count="1"'
    '    llmind:immutable="true"'
    '    >'
    '      <llmind:description>hi</llmind:description>'
    '      <llmind:text>hi</llmind:text>'
    '      <llmind:structure>{}</llmind:structure>'
    '      <llmind:history>[{"version":1,"timestamp":"2026-04-18T00:00:00Z","generator":"llmind-cli/0.1.0","generator_model":"whisper-1","checksum":"c","language":"en","description":"hi","text":"hi","structure":{},"key_id":"","signature":null,"media_type":"audio","duration_seconds":1.0,"segments":[{"start":0.0,"end":1.0,"text":"hi"}]}]</llmind:history>'
    '    </rdf:Description>'
    '  </rdf:RDF>'
    '</x:xmpmeta>'
    '<?xpacket end="w"?>'
)


def test_reader_reads_audio_layer(tmp_path):
    dst = tmp_path / "silent.mp3"
    shutil.copy(AUDIO_FIX / "silent.mp3", dst)
    inject_audio(dst, MINIMAL_XMP)
    assert has_llmind_layer(dst) is True
    meta = read(dst)
    assert meta is not None
    assert meta.current.media_type == "audio"
    assert meta.current.duration_seconds == 1.0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_reader.py::test_reader_reads_audio_layer -v`
Expected: FAIL — `_read_raw_xmp` raises on unknown suffix.

- [ ] **Step 3: Update `reader.py`**

Replace `_read_raw_xmp` in `llmind-cli/llmind/reader.py`:

```python
from llmind.audio_injector import read_xmp_audio
from llmind.safety import is_audio_file


def _read_raw_xmp(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return read_xmp_jpeg(path)
    if suffix == ".png":
        return read_xmp_png(path)
    if suffix == ".pdf":
        return read_xmp_pdf(path)
    if is_audio_file(path):
        return read_xmp_audio(path)
    raise ValueError(f"Unsupported format: {path.suffix}")
```

- [ ] **Step 4: Update `injector.inject` and `injector.remove_llmind_xmp`**

In `llmind-cli/llmind/injector.py`, update both dispatchers:

```python
from llmind.safety import is_audio_file


def inject(path: Path, xmp_string: str) -> None:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        _inject_jpeg(path, xmp_string)
    elif suffix == ".png":
        _inject_png(path, xmp_string)
    elif suffix == ".pdf":
        _inject_pdf(path, xmp_string)
    elif is_audio_file(path):
        from llmind.audio_injector import inject_audio
        inject_audio(path, xmp_string)
    else:
        raise ValueError(f"Unsupported format for inject: {path.suffix}")


def remove_llmind_xmp(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return _remove_llmind_xmp_jpeg(path)
    elif suffix == ".png":
        return _remove_llmind_xmp_png(path)
    elif suffix == ".pdf":
        return _remove_llmind_xmp_pdf(path)
    elif is_audio_file(path):
        from llmind.audio_injector import remove_llmind_xmp_audio
        return remove_llmind_xmp_audio(path)
    else:
        raise ValueError(f"Unsupported format for remove_llmind_xmp: {path.suffix}")
```

- [ ] **Step 5: Run reader + injector + full suite**

Run: `cd llmind-cli && pytest tests/test_reader.py tests/test_injector.py -v`
Then: `cd llmind-cli && pytest -x`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add llmind-cli/llmind/reader.py llmind-cli/llmind/injector.py llmind-cli/tests/test_reader.py
git commit -m "feat(io): route audio suffixes through audio_injector"
```

---

### Task 11: `AudioExtraction`, Provider Defaults, `UnsupportedProviderError`

**Files:**
- Create: `llmind-cli/llmind/audio.py` (scaffolding + dataclass + exception only)
- Test: `llmind-cli/tests/test_audio_dispatch.py`

- [ ] **Step 1: Write failing test**

```python
# llmind-cli/tests/test_audio_dispatch.py
import pytest

from llmind.audio import (
    AudioExtraction, UnsupportedProviderError,
    AUDIO_PROVIDER_DEFAULTS, AUDIO_SUMMARIZER_DEFAULTS,
)
from llmind.models import Segment


def test_audio_extraction_frozen():
    e = AudioExtraction(
        text="hi", summary="short", segments=(Segment(0.0, 1.0, "hi"),),
        language="en", duration_seconds=1.0,
    )
    assert e.text == "hi"
    assert e.segments[0].text == "hi"


def test_provider_defaults_table():
    assert AUDIO_PROVIDER_DEFAULTS == {
        "openai": "whisper-1",
        "gemini": "gemini-2.5-flash",
        "whisper_local": "base",
    }


def test_summarizer_defaults_table():
    assert AUDIO_SUMMARIZER_DEFAULTS["openai"] == "gpt-4o-mini"


def test_unsupported_provider_error_is_value_error_subclass():
    assert issubclass(UnsupportedProviderError, ValueError)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py -v`
Expected: FAIL — `llmind.audio` module missing.

- [ ] **Step 3: Create `audio.py` skeleton**

```python
# llmind-cli/llmind/audio.py
"""Audio transcription providers and dispatch."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llmind.models import Segment


class UnsupportedProviderError(ValueError):
    """Raised when a provider does not support audio input."""


@dataclass(frozen=True)
class AudioExtraction:
    text: str
    summary: str
    segments: tuple[Segment, ...]
    language: str
    duration_seconds: float


AUDIO_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "whisper-1",
    "gemini": "gemini-2.5-flash",
    "whisper_local": "base",
}

AUDIO_SUMMARIZER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",   # same model handles both transcript + summary
    "whisper_local": "",            # extractive summary, no model
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py -v`
Expected: PASS — all 4 tests.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio.py llmind-cli/tests/test_audio_dispatch.py
git commit -m "feat(audio): scaffold AudioExtraction, provider defaults, UnsupportedProviderError"
```

---

### Task 12: OpenAI Whisper Provider

**Files:**
- Modify: `llmind-cli/llmind/audio.py`
- Test: `llmind-cli/tests/test_audio_dispatch.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `llmind-cli/tests/test_audio_dispatch.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from llmind.audio import _query_openai

FIXTURE_WAV = Path(__file__).parent / "fixtures" / "audio" / "silent.wav"


def _fake_whisper_response():
    resp = MagicMock()
    resp.text = "hello world"
    resp.language = "en"
    resp.duration = 2.0
    seg1 = MagicMock(); seg1.start = 0.0; seg1.end = 1.0; seg1.text = "hello"
    seg2 = MagicMock(); seg2.start = 1.0; seg2.end = 2.0; seg2.text = "world"
    resp.segments = [seg1, seg2]
    return resp


def _fake_chat_response(text: str):
    choice = MagicMock()
    choice.message.content = text
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_openai_provider_returns_extraction(tmp_path):
    dst = tmp_path / "copy.wav"
    dst.write_bytes(FIXTURE_WAV.read_bytes())
    fake_client = MagicMock()
    fake_client.audio.transcriptions.create.return_value = _fake_whisper_response()
    fake_client.chat.completions.create.return_value = _fake_chat_response(
        "A short greeting."
    )
    with patch("llmind.audio._get_openai_client", return_value=fake_client):
        result = _query_openai(dst, model="whisper-1", summarizer="gpt-4o-mini")
    assert result.text == "hello world"
    assert result.language == "en"
    assert result.duration_seconds == 2.0
    assert result.summary == "A short greeting."
    assert len(result.segments) == 2
    assert result.segments[0].text == "hello"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py::test_openai_provider_returns_extraction -v`
Expected: FAIL — `_query_openai` undefined.

- [ ] **Step 3: Append OpenAI implementation to `audio.py`**

```python
# Append to llmind-cli/llmind/audio.py

def _get_openai_client():
    from openai import OpenAI
    return OpenAI()


def _query_openai(path: Path, model: str, summarizer: str) -> AudioExtraction:
    client = _get_openai_client()
    with open(path, "rb") as fh:
        resp = client.audio.transcriptions.create(
            model=model,
            file=fh,
            response_format="verbose_json",
        )
    segments = tuple(
        Segment(start=float(s.start), end=float(s.end), text=str(s.text).strip())
        for s in (resp.segments or [])
    )
    transcript = str(resp.text or "").strip()
    summary_resp = client.chat.completions.create(
        model=summarizer,
        messages=[
            {"role": "system", "content": "Summarize the following transcript in 1-2 sentences."},
            {"role": "user", "content": transcript or "(empty transcript)"},
        ],
    )
    summary = str(summary_resp.choices[0].message.content or "").strip()
    return AudioExtraction(
        text=transcript,
        summary=summary,
        segments=segments,
        language=str(resp.language or "en"),
        duration_seconds=float(resp.duration or 0.0),
    )
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py::test_openai_provider_returns_extraction -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio.py llmind-cli/tests/test_audio_dispatch.py
git commit -m "feat(audio): OpenAI Whisper provider with gpt-4o-mini summarizer"
```

---

### Task 13: Gemini Audio Provider

**Files:**
- Modify: `llmind-cli/llmind/audio.py`
- Test: `llmind-cli/tests/test_audio_dispatch.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `llmind-cli/tests/test_audio_dispatch.py`:

```python
from llmind.audio import _query_gemini


GEMINI_JSON = (
    '{"transcript":"hello world","language":"en","duration":2.0,'
    '"summary":"A greeting.",'
    '"segments":[{"start":0.0,"end":1.0,"text":"hello"},'
    '{"start":1.0,"end":2.0,"text":"world"}]}'
)


def test_gemini_provider_parses_json(tmp_path):
    dst = tmp_path / "copy.wav"
    dst.write_bytes(FIXTURE_WAV.read_bytes())

    fake_file = MagicMock(); fake_file.name = "files/xyz"
    fake_client = MagicMock()
    fake_client.files.upload.return_value = fake_file
    response = MagicMock()
    response.text = GEMINI_JSON
    fake_client.models.generate_content.return_value = response

    with patch("llmind.audio._get_gemini_client", return_value=fake_client):
        result = _query_gemini(dst, model="gemini-2.5-flash")
    assert result.text == "hello world"
    assert result.summary == "A greeting."
    assert result.duration_seconds == 2.0
    assert len(result.segments) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py::test_gemini_provider_parses_json -v`
Expected: FAIL — `_query_gemini` undefined.

- [ ] **Step 3: Append Gemini implementation to `audio.py`**

```python
# Append to llmind-cli/llmind/audio.py

import json as _json


_GEMINI_PROMPT = (
    "Transcribe this audio. Return ONLY a JSON object with keys: "
    '"transcript" (full text), "language" (BCP-47 code), '
    '"duration" (seconds, float), '
    '"summary" (1-2 sentence description), '
    '"segments" (list of {start, end, text}).'
)


def _get_gemini_client():
    from google import genai
    return genai.Client()


def _query_gemini(path: Path, model: str) -> AudioExtraction:
    client = _get_gemini_client()
    uploaded = client.files.upload(file=str(path))
    response = client.models.generate_content(
        model=model,
        contents=[_GEMINI_PROMPT, uploaded],
    )
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw[raw.index("\n") + 1:]
    if raw.endswith("```"):
        raw = raw[:raw.rindex("```")].strip()
    data = _json.loads(raw)
    segments = tuple(
        Segment(start=float(s["start"]), end=float(s["end"]),
                text=str(s["text"]).strip())
        for s in data.get("segments", [])
    )
    return AudioExtraction(
        text=str(data.get("transcript", "")).strip(),
        summary=str(data.get("summary", "")).strip(),
        segments=segments,
        language=str(data.get("language", "en")),
        duration_seconds=float(data.get("duration", 0.0)),
    )
```

- [ ] **Step 4: Run test**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py::test_gemini_provider_parses_json -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio.py llmind-cli/tests/test_audio_dispatch.py
git commit -m "feat(audio): Gemini provider with JSON-mode transcription + summary"
```

---

### Task 14: Local `faster-whisper` Provider

**Files:**
- Modify: `llmind-cli/llmind/audio.py`
- Test: `llmind-cli/tests/test_audio_dispatch.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `llmind-cli/tests/test_audio_dispatch.py`:

```python
from llmind.audio import _query_whisper_local, _extractive_summary


def test_extractive_summary_empty():
    assert _extractive_summary("") == ""


def test_extractive_summary_short():
    assert _extractive_summary("Only one sentence.") == "Only one sentence."


def test_extractive_summary_picks_first_and_longest():
    text = "Hi. This is a much longer informative sentence with details. Bye."
    s = _extractive_summary(text)
    assert "Hi." in s
    assert "This is a much longer informative sentence with details." in s


def test_whisper_local_provider(tmp_path):
    dst = tmp_path / "copy.wav"
    dst.write_bytes(FIXTURE_WAV.read_bytes())

    seg1 = MagicMock(); seg1.start = 0.0; seg1.end = 1.0; seg1.text = " hello"
    seg2 = MagicMock(); seg2.start = 1.0; seg2.end = 2.0; seg2.text = " world"
    info = MagicMock(); info.language = "en"; info.duration = 2.0

    fake_model = MagicMock()
    fake_model.transcribe.return_value = (iter([seg1, seg2]), info)

    with patch("llmind.audio._load_whisper_local", return_value=fake_model):
        result = _query_whisper_local(dst, model="base")
    assert result.text == "hello\nworld"
    assert result.duration_seconds == 2.0
    assert result.language == "en"
    assert len(result.segments) == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py::test_whisper_local_provider -v`
Expected: FAIL — helpers undefined.

- [ ] **Step 3: Append local-whisper implementation**

```python
# Append to llmind-cli/llmind/audio.py

import re as _re


def _extractive_summary(text: str) -> str:
    """Return first sentence + longest sentence (deduped) as a 2-line summary."""
    text = text.strip()
    if not text:
        return ""
    sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= 1:
        return sentences[0] if sentences else ""
    first = sentences[0]
    longest = max(sentences[1:], key=len)
    if longest == first:
        return first
    return f"{first} {longest}"


def _load_whisper_local(model_size: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise UnsupportedProviderError(
            "Install `faster-whisper` to use the whisper_local provider."
        ) from exc
    return WhisperModel(model_size, compute_type="int8")


def _query_whisper_local(path: Path, model: str) -> AudioExtraction:
    whisper = _load_whisper_local(model or "base")
    segments_iter, info = whisper.transcribe(str(path))
    segments: list[Segment] = []
    parts: list[str] = []
    for s in segments_iter:
        text = str(s.text).strip()
        segments.append(Segment(start=float(s.start), end=float(s.end), text=text))
        parts.append(text)
    transcript = "\n".join(parts)
    return AudioExtraction(
        text=transcript,
        summary=_extractive_summary(transcript.replace("\n", " ")),
        segments=tuple(segments),
        language=str(info.language or "en"),
        duration_seconds=float(info.duration or 0.0),
    )
```

- [ ] **Step 4: Run tests**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py -v`
Expected: PASS — all tests including the new local-whisper and extractive-summary cases.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio.py llmind-cli/tests/test_audio_dispatch.py
git commit -m "feat(audio): local faster-whisper provider with extractive summary"
```

---

### Task 15: `query_audio` Public Dispatch

**Files:**
- Modify: `llmind-cli/llmind/audio.py`
- Test: `llmind-cli/tests/test_audio_dispatch.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `llmind-cli/tests/test_audio_dispatch.py`:

```python
from llmind.audio import query_audio


def test_query_audio_dispatches_openai(tmp_path):
    dst = tmp_path / "copy.wav"
    dst.write_bytes(FIXTURE_WAV.read_bytes())
    expected = AudioExtraction(
        text="t", summary="s", segments=(), language="en", duration_seconds=1.0,
    )
    with patch("llmind.audio._query_openai", return_value=expected) as m:
        result = query_audio(dst, provider="openai")
    assert result is expected
    m.assert_called_once()


def test_query_audio_rejects_anthropic(tmp_path):
    dst = tmp_path / "copy.wav"
    dst.write_bytes(FIXTURE_WAV.read_bytes())
    with pytest.raises(UnsupportedProviderError, match="anthropic"):
        query_audio(dst, provider="anthropic")


def test_query_audio_rejects_ollama(tmp_path):
    dst = tmp_path / "copy.wav"
    dst.write_bytes(FIXTURE_WAV.read_bytes())
    with pytest.raises(UnsupportedProviderError, match="ollama"):
        query_audio(dst, provider="ollama")


def test_query_audio_unknown_provider_raises(tmp_path):
    dst = tmp_path / "copy.wav"
    dst.write_bytes(FIXTURE_WAV.read_bytes())
    with pytest.raises(UnsupportedProviderError):
        query_audio(dst, provider="bogus")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py -v -k query_audio`
Expected: FAIL — `query_audio` undefined.

- [ ] **Step 3: Append `query_audio` to `audio.py`**

```python
# Append to llmind-cli/llmind/audio.py

_UNSUPPORTED = {"anthropic", "ollama"}


def query_audio(
    path: Path,
    provider: str,
    model: str | None = None,
) -> AudioExtraction:
    """Dispatch audio transcription to the requested provider.

    Supported: openai, gemini, whisper_local.
    Raises UnsupportedProviderError for anthropic, ollama, or unknown providers.
    """
    if provider in _UNSUPPORTED:
        raise UnsupportedProviderError(
            f"Provider {provider!r} does not support audio. "
            f"Supported: openai, gemini, whisper_local."
        )
    if provider not in AUDIO_PROVIDER_DEFAULTS:
        raise UnsupportedProviderError(
            f"Unknown audio provider {provider!r}. "
            f"Supported: openai, gemini, whisper_local."
        )
    resolved_model = model or AUDIO_PROVIDER_DEFAULTS[provider]
    if provider == "openai":
        return _query_openai(
            path, model=resolved_model,
            summarizer=AUDIO_SUMMARIZER_DEFAULTS["openai"],
        )
    if provider == "gemini":
        return _query_gemini(path, model=resolved_model)
    if provider == "whisper_local":
        return _query_whisper_local(path, model=resolved_model)
    raise UnsupportedProviderError(f"Unreachable provider: {provider!r}")
```

- [ ] **Step 4: Run tests**

Run: `cd llmind-cli && pytest tests/test_audio_dispatch.py -v`
Expected: PASS — all tests.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/audio.py llmind-cli/tests/test_audio_dispatch.py
git commit -m "feat(audio): query_audio dispatcher with fail-fast for anthropic/ollama"
```

---

### Task 16: Enricher Audio Branch in `_enrich`

**Files:**
- Modify: `llmind-cli/llmind/enricher.py`
- Test: `llmind-cli/tests/test_audio_enricher.py`

- [ ] **Step 1: Write failing test**

```python
# llmind-cli/tests/test_audio_enricher.py
import shutil
from pathlib import Path
from unittest.mock import patch

from llmind.audio import AudioExtraction
from llmind.enricher import enrich
from llmind.models import Segment
from llmind.reader import read

FIX = Path(__file__).parent / "fixtures" / "audio"


def _fake_extraction() -> AudioExtraction:
    return AudioExtraction(
        text="hello world",
        summary="A greeting.",
        segments=(Segment(0.0, 1.0, "hello"), Segment(1.0, 2.0, "world")),
        language="en",
        duration_seconds=2.0,
    )


def test_enrich_mp3(tmp_path):
    src = tmp_path / "memo.mp3"
    shutil.copy(FIX / "silent.mp3", src)
    with patch("llmind.enricher.query_audio", return_value=_fake_extraction()):
        result = enrich(src, provider="openai")
    assert result.success
    out = src.with_name("memo.llmind.mp3")
    assert out.exists()
    meta = read(out)
    assert meta.current.media_type == "audio"
    assert meta.current.description == "A greeting."
    assert meta.current.text == "hello world"
    assert meta.current.duration_seconds == 2.0
    assert meta.current.segments is not None
    assert len(meta.current.segments) == 2


def test_enrich_wav(tmp_path):
    src = tmp_path / "rec.wav"
    shutil.copy(FIX / "silent.wav", src)
    with patch("llmind.enricher.query_audio", return_value=_fake_extraction()):
        result = enrich(src, provider="whisper_local")
    assert result.success
    out = src.with_name("rec.llmind.wav")
    assert out.exists()
    meta = read(out)
    assert meta.current.media_type == "audio"


def test_enrich_m4a(tmp_path):
    src = tmp_path / "voice.m4a"
    shutil.copy(FIX / "silent.m4a", src)
    with patch("llmind.enricher.query_audio", return_value=_fake_extraction()):
        result = enrich(src, provider="gemini")
    assert result.success
    out = src.with_name("voice.llmind.m4a")
    assert out.exists()
    meta = read(out)
    assert meta.current.media_type == "audio"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_audio_enricher.py -v`
Expected: FAIL — `query_audio` not imported in enricher; audio dispatch branch missing.

- [ ] **Step 3: Modify `enricher.py`**

Top of file, add import:

```python
from llmind.audio import AudioExtraction, query_audio
from llmind.models import Segment
from llmind.safety import is_audio_file, AUDIO_EXTENSIONS
```

Add helper near other private helpers:

```python
def _audio_layer_fields(extraction: AudioExtraction) -> dict:
    """Map AudioExtraction to Layer-keyword kwargs (segments, duration, media_type)."""
    return {
        "segments": extraction.segments,
        "duration_seconds": extraction.duration_seconds,
        "media_type": "audio",
    }
```

Inside `_enrich`, replace the `suffix = path.suffix.lower()` dispatch block with:

```python
    suffix = path.suffix.lower()
    media_type = "image"
    audio_kwargs: dict = {}
    if suffix == ".pdf":
        image_pages = _pdf_to_images(path)
        extraction = query_pdf(image_pages, provider=provider, model=model, base_url=base_url)
        media_type = "pdf"
    elif is_audio_file(path):
        audio = query_audio(path, provider=provider, model=model)
        extraction = ExtractionResult(
            language=audio.language,
            description=audio.summary,
            text=audio.text,
            structure={},
        )
        audio_kwargs = _audio_layer_fields(audio)
        media_type = "audio"
    else:
        extraction = query_image(path.read_bytes(), provider=provider, model=model, base_url=base_url)
```

Add `from llmind.models import ExtractionResult` import at top if not already imported. (It's defined in `models.py`.)

Then, in `_enrich` where `Layer(...)` is built, add `**audio_kwargs` and `media_type=media_type` kwargs:

```python
    layer = Layer(
        version=version,
        timestamp=timestamp,
        generator=generator,
        generator_model=resolved_model,
        checksum=checksum,
        language=extraction.language,
        description=extraction.description,
        text=extraction.text,
        structure=extraction.structure,
        key_id=derive_key_id(creation_key) if creation_key else "",
        signature=None,
        media_type=media_type,
        **audio_kwargs,
    )
```

For audio, `resolved_model` should come from `AUDIO_PROVIDER_DEFAULTS` when `model is None`. Update the `resolved_model` line:

```python
    if is_audio_file(path):
        from llmind.audio import AUDIO_PROVIDER_DEFAULTS
        resolved_model = model or AUDIO_PROVIDER_DEFAULTS.get(provider, "")
    else:
        resolved_model = model or PROVIDER_DEFAULTS.get(provider, "")
```

- [ ] **Step 4: Run tests**

Run: `cd llmind-cli && pytest tests/test_audio_enricher.py -v`
Expected: PASS — 3 tests.

- [ ] **Step 5: Full-suite regression**

Run: `cd llmind-cli && pytest -x`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add llmind-cli/llmind/enricher.py llmind-cli/tests/test_audio_enricher.py
git commit -m "feat(enricher): audio branch with media_type and audio Layer fields"
```

---

### Task 17: `_reenrich` Audio Branch

**Files:**
- Modify: `llmind-cli/llmind/enricher.py`
- Test: `llmind-cli/tests/test_audio_enricher.py` (extend)

- [ ] **Step 1: Write failing test**

Append to `llmind-cli/tests/test_audio_enricher.py`:

```python
from llmind.enricher import reenrich


def test_reenrich_mp3_appends_v2(tmp_path):
    src = tmp_path / "memo.mp3"
    shutil.copy(FIX / "silent.mp3", src)
    with patch("llmind.enricher.query_audio", return_value=_fake_extraction()):
        first = enrich(src, provider="openai")
    assert first.success
    out = src.with_name("memo.llmind.mp3")

    with patch("llmind.enricher.query_audio", return_value=_fake_extraction()):
        second = reenrich(out, provider="openai", force=True)
    assert second.success
    assert second.version == 2
    meta = read(out)
    assert meta.layer_count == 2
    assert meta.current.media_type == "audio"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_audio_enricher.py::test_reenrich_mp3_appends_v2 -v`
Expected: FAIL — `_reenrich` does not branch on audio.

- [ ] **Step 3: Update `_reenrich` in `enricher.py`**

Inside `_reenrich`, replace the suffix dispatch block with:

```python
    suffix = path.suffix.lower()
    media_type = "image"
    audio_kwargs: dict = {}
    if suffix == ".pdf":
        image_pages = _pdf_to_images(path)
        extraction = query_pdf(image_pages, provider=provider, model=model, base_url=base_url)
        media_type = "pdf"
    elif is_audio_file(path):
        audio = query_audio(path, provider=provider, model=model)
        extraction = ExtractionResult(
            language=audio.language,
            description=audio.summary,
            text=audio.text,
            structure={},
        )
        audio_kwargs = _audio_layer_fields(audio)
        media_type = "audio"
    else:
        extraction = query_image(path.read_bytes(), provider=provider, model=model, base_url=base_url)
```

And the `Layer(...)` construction adds `media_type=media_type, **audio_kwargs`.

Update `resolved_model` same way as Task 16 (`AUDIO_PROVIDER_DEFAULTS` when audio).

Also update `is_already_enriched_file` reference inside `_reenrich` — no change needed if `is_already_enriched_file` already matches the `.llmind.<ext>` pattern. Verified in Task 18.

- [ ] **Step 4: Run test**

Run: `cd llmind-cli && pytest tests/test_audio_enricher.py -v`
Expected: PASS — all audio enricher tests.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/llmind/enricher.py llmind-cli/tests/test_audio_enricher.py
git commit -m "feat(enricher): audio branch in _reenrich for in-place layer append"
```

---

### Task 18: `is_already_enriched_file` Regression for Audio

**Files:**
- Test: `llmind-cli/tests/test_enricher.py` (extend)

- [ ] **Step 1: Write test**

Append to `llmind-cli/tests/test_enricher.py`:

```python
from pathlib import Path

from llmind.enricher import is_already_enriched_file


def test_is_already_enriched_audio_files():
    assert is_already_enriched_file(Path("voice.llmind.mp3"))
    assert is_already_enriched_file(Path("recording.llmind.wav"))
    assert is_already_enriched_file(Path("memo.llmind.m4a"))


def test_is_already_enriched_fresh_audio_is_not():
    assert not is_already_enriched_file(Path("voice.mp3"))
    assert not is_already_enriched_file(Path("recording.wav"))
    assert not is_already_enriched_file(Path("memo.m4a"))
```

- [ ] **Step 2: Run**

Run: `cd llmind-cli && pytest tests/test_enricher.py -v -k is_already_enriched`
Expected: PASS — existing `is_already_enriched_file` logic (checks `.llmind` stem suffix) already covers audio.

If it fails, review the implementation and adjust to match the `.llmind.<ext>` pattern.

- [ ] **Step 3: Commit**

```bash
git add llmind-cli/tests/test_enricher.py
git commit -m "test(enricher): pin is_already_enriched behavior for audio suffixes"
```

---

### Task 19: Signing/Verification Regression for Audio

**Files:**
- Test: `llmind-cli/tests/test_audio_signing.py`

- [ ] **Step 1: Write test**

```python
# llmind-cli/tests/test_audio_signing.py
import shutil
from pathlib import Path
from unittest.mock import patch

from llmind.audio import AudioExtraction
from llmind.crypto import sign_layer, verify_signature
from llmind.enricher import enrich
from llmind.models import Layer, Segment
from llmind.reader import read
from llmind.verifier import verify
from llmind.xmp import layer_to_dict

FIX = Path(__file__).parent / "fixtures" / "audio"
KEY = "1" * 64


def _audio_extraction() -> AudioExtraction:
    return AudioExtraction(
        text="hi", summary="greeting",
        segments=(Segment(0.0, 1.0, "hi"),),
        language="en", duration_seconds=1.0,
    )


def test_audio_layer_signature_roundtrip(tmp_path):
    src = tmp_path / "memo.mp3"
    shutil.copy(FIX / "silent.mp3", src)
    with patch("llmind.enricher.query_audio", return_value=_audio_extraction()):
        result = enrich(src, provider="openai", creation_key=KEY)
    assert result.success
    out = src.with_name("memo.llmind.mp3")
    vr = verify(out, creation_key=KEY)
    assert vr.has_layer
    assert vr.checksum_valid
    assert vr.signature_valid is True


def test_existing_image_signature_still_valid():
    """Adding audio fields to layer_to_dict must not break legacy image signatures."""
    # Legacy image layer (no audio fields) — simulates pre-audio signing.
    image_layer = Layer(
        version=1, timestamp="2026-01-01T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="gpt-4o-mini",
        checksum="d" * 64, language="en",
        description="A photo.", text="some text",
        structure={"type": "photo"}, key_id="",
    )
    payload = layer_to_dict(image_layer, include_signature=False)
    # Audio-only keys must be absent for image layers.
    assert "segments" not in payload
    assert "duration_seconds" not in payload
    assert "media_type" not in payload
    sig = sign_layer(KEY, payload)
    assert verify_signature(KEY, payload, sig) is True
```

- [ ] **Step 2: Run**

Run: `cd llmind-cli && pytest tests/test_audio_signing.py -v`
Expected: PASS — both tests.

If either fails, check that `layer_to_dict` (Task 3) omits audio-only fields when they're absent and that `crypto.sign_layer` serializes with sorted keys.

- [ ] **Step 3: Commit**

```bash
git add llmind-cli/tests/test_audio_signing.py
git commit -m "test(crypto): audio signing roundtrip and legacy-image compat"
```

---

### Task 20: End-to-End Freshness Test (Audio)

**Files:**
- Test: `llmind-cli/tests/test_audio_enricher.py` (extend)

- [ ] **Step 1: Write test**

Append to `llmind-cli/tests/test_audio_enricher.py`:

```python
from llmind.reader import is_fresh
from llmind.crypto import sha256_file


def test_enriched_audio_is_fresh(tmp_path):
    src = tmp_path / "memo.mp3"
    shutil.copy(FIX / "silent.mp3", src)
    with patch("llmind.enricher.query_audio", return_value=_fake_extraction()):
        result = enrich(src, provider="openai")
    out = src.with_name("memo.llmind.mp3")
    # After enrichment the checksum stored in the layer matches the
    # pre-injection hash, so is_fresh (computed against the pre-injection
    # content) returns True iff we re-enrich and the file has not mutated.
    # For this test we just confirm the stored checksum exists and matches
    # the recorded layer value.
    meta = read(out)
    stored = meta.current.checksum
    assert len(stored) == 64
    # Touching the file should NOT invalidate freshness (XMP added later
    # would change the hash, but the layer's own checksum is pre-injection)
    # — we simply confirm the invariant holds for the in-memory read.
    assert is_fresh(out, stored) is True
    # Sanity: the actual on-disk hash now differs from the stored checksum
    # because the XMP was injected after the hash was captured.
    assert sha256_file(out) != stored
```

- [ ] **Step 2: Run**

Run: `cd llmind-cli && pytest tests/test_audio_enricher.py::test_enriched_audio_is_fresh -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add llmind-cli/tests/test_audio_enricher.py
git commit -m "test(enricher): confirm freshness invariant for enriched audio files"
```

---

### Task 21: Dependency Updates in `pyproject.toml`

**Files:**
- Modify: `llmind-cli/pyproject.toml`

- [ ] **Step 1: Update `pyproject.toml`**

Replace the `[project]` `dependencies` block and the `[project.optional-dependencies]` block in `llmind-cli/pyproject.toml` with:

```toml
dependencies = [
    "click>=8.0",
    "pillow>=10.0",
    "pikepdf>=8.0",
    "watchdog>=3.0",
    "requests>=2.31",
    "pdf2image>=1.16",
    "rich>=13.0",
    "pyyaml>=6.0",
    "mutagen>=1.47",
]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov>=4.0", "responses>=0.23"]
anthropic = ["anthropic>=0.40.0"]
openai = ["openai>=1.50.0"]
embeddings = ["voyageai>=0.2.0"]
gemini = ["google-genai>=1.0.0"]
whisper-local = ["faster-whisper>=1.0"]
all-providers = [
    "anthropic>=0.40.0",
    "openai>=1.50.0",
    "google-genai>=1.0.0",
    "faster-whisper>=1.0",
]
```

- [ ] **Step 2: Install locally**

Run: `cd llmind-cli && pip install -e .[dev]`
Expected: `mutagen` installed as a core dep. `faster-whisper` only if `.[whisper-local]` extra is installed.

- [ ] **Step 3: Run full suite**

Run: `cd llmind-cli && pytest -x`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add llmind-cli/pyproject.toml
git commit -m "chore(deps): add mutagen core dep; faster-whisper as optional extra"
```

---

### Task 22: Watcher Regression + Documentation

**Files:**
- Test: `llmind-cli/tests/test_watcher.py` (extend)
- Modify: `README.md`

- [ ] **Step 1: Write watcher test**

Append to `llmind-cli/tests/test_watcher.py`:

```python
from pathlib import Path

from llmind.safety import is_safe_file


def test_watcher_accepts_audio_files(tmp_path):
    for name in ["a.mp3", "b.wav", "c.m4a"]:
        p = tmp_path / name
        p.write_bytes(b"\x00" * 64)
        assert is_safe_file(p) is True
```

- [ ] **Step 2: Run**

Run: `cd llmind-cli && pytest tests/test_watcher.py -v -k audio`
Expected: PASS (safety change from Task 5 makes this work without watcher changes).

- [ ] **Step 3: Update `README.md`**

In `/Users/dzmitrytryhubenka/APP DEV/LLMind/README.md`, update the "What it does" section. Replace this paragraph:

```markdown
LLMind takes a standard **JPEG, PNG, or PDF** file and enriches it with a structured metadata layer containing:

- **Extracted text** — every word, badge, watermark, and label from the file
- **Visual description** — a natural-language description of layout, logos, icons, and design elements
- **Document structure** — regions, figures, and tables mapped as JSON
```

With:

```markdown
LLMind takes a standard **JPEG, PNG, PDF, MP3, WAV, or M4A** file and enriches it with a structured metadata layer containing:

- **Extracted text** — every word, badge, watermark, label (images/PDF) or spoken-word transcript (audio)
- **Visual description** or **audio summary** — natural-language description
- **Document structure** (image/PDF) or **timestamped segments** (audio) — mapped as JSON
```

Add a new short section after the existing "How it works" section:

```markdown
## Audio support (CLI-only)

Audio files are transcribed and enriched with:

- Full transcript (`llmind:text`)
- 1–2 sentence summary (`llmind:description`)
- Timestamped segments (`llmind:segments`)
- Duration in seconds (`llmind:duration_seconds`)
- Media type marker (`llmind:media_type="audio"`)

Supported providers: OpenAI Whisper, Gemini, local `faster-whisper`.
Install the local provider with: `pip install -e .[whisper-local]`.
```

- [ ] **Step 4: Run full suite one more time**

Run: `cd llmind-cli && pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add llmind-cli/tests/test_watcher.py README.md
git commit -m "docs: document audio enrichment in README and watcher regression"
```

---

## Final Verification

After all 22 tasks:

- [ ] `cd llmind-cli && pytest --cov=llmind --cov-report=term-missing`
  Expected: coverage >= 80% overall; `audio.py` and `audio_injector.py` >= 90%.

- [ ] `cd llmind-cli && llmind enrich tests/fixtures/audio/silent.mp3 --provider whisper_local`
  (requires local faster-whisper install — manual smoke test)
  Expected: a `silent.llmind.mp3` appears; `llmind read silent.llmind.mp3` shows the audio layer.

- [ ] Confirm legacy image files still enrich correctly:
  `cd llmind-cli && llmind enrich path/to/some.jpg --provider openai`
  Expected: works unchanged, `media_type` defaults to "image" in output.

---

### Task 23: CLI `--provider` Choice + Cloud Size Limit

**Files:**
- Modify: `llmind-cli/llmind/cli.py`
- Modify: `llmind-cli/llmind/safety.py`
- Modify: `llmind-cli/llmind/enricher.py`
- Test: `llmind-cli/tests/test_cli.py` (extend), `llmind-cli/tests/test_safety.py` (extend)

- [ ] **Step 1: Write failing CLI test**

Append to `llmind-cli/tests/test_cli.py`:

```python
from click.testing import CliRunner

from llmind.cli import main


def test_cli_enrich_accepts_whisper_local_provider(tmp_path):
    fixture = tmp_path / "memo.mp3"
    fixture.write_bytes(b"\x00" * 64)
    runner = CliRunner()
    # Use --help-like early exit pattern: passing an unknown provider
    # should error; a supported one should not error at argument parse.
    result = runner.invoke(main, ["enrich", "--provider", "whisper_local", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Write failing safety test**

Append to `llmind-cli/tests/test_safety.py`:

```python
from llmind.safety import audio_size_ok


def test_audio_size_ok_small_cloud(tmp_path):
    p = tmp_path / "a.mp3"
    p.write_bytes(b"\x00" * 1024)
    assert audio_size_ok(p, provider="openai") is True


def test_audio_size_ok_large_cloud_rejected(tmp_path):
    p = tmp_path / "a.mp3"
    # Fake a 26 MB file via seek/write
    with open(p, "wb") as fh:
        fh.seek(26 * 1024 * 1024 - 1)
        fh.write(b"\x00")
    assert audio_size_ok(p, provider="openai") is False
    assert audio_size_ok(p, provider="gemini") is False


def test_audio_size_ok_large_local_accepted(tmp_path):
    p = tmp_path / "a.mp3"
    with open(p, "wb") as fh:
        fh.seek(26 * 1024 * 1024 - 1)
        fh.write(b"\x00")
    assert audio_size_ok(p, provider="whisper_local") is True
```

- [ ] **Step 3: Run to verify failure**

Run: `cd llmind-cli && pytest tests/test_safety.py -v -k audio_size_ok`
Expected: FAIL — `audio_size_ok` not defined.

- [ ] **Step 4: Update `safety.py`**

Append to `llmind-cli/llmind/safety.py`:

```python
_CLOUD_AUDIO_LIMIT_BYTES = 25 * 1024 * 1024   # OpenAI Whisper hard limit
_CLOUD_AUDIO_PROVIDERS = frozenset({"openai", "gemini"})


def audio_size_ok(path: Path, provider: str) -> bool:
    """Return True if the file's size is within the provider's audio limit."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if provider in _CLOUD_AUDIO_PROVIDERS:
        return size <= _CLOUD_AUDIO_LIMIT_BYTES
    return True
```

- [ ] **Step 5: Update `cli.py` — add `whisper_local` to both `enrich` and `reenrich` provider choices**

In `llmind-cli/llmind/cli.py`, change the two `click.Choice([...])` lines used for the `enrich` and `reenrich` commands (near lines 28 and 77) from:

```python
type=click.Choice(["ollama", "anthropic", "openai", "gemini"]),
```

to:

```python
type=click.Choice(["ollama", "anthropic", "openai", "gemini", "whisper_local"]),
```

Do NOT change the `embed` or `search` provider choices — audio embedding is out of scope for v1.

Also update the `watch` command provider choice (near line 441) the same way to keep parity:

```python
type=click.Choice(["ollama", "anthropic", "openai", "gemini", "whisper_local"]),
```

- [ ] **Step 6: Update `enricher.py` to enforce audio size limit**

In `llmind-cli/llmind/enricher.py`, inside both `_enrich` and `_reenrich`, right after the `is_safe_file` check, add:

```python
    if is_audio_file(path):
        from llmind.safety import audio_size_ok
        if not audio_size_ok(path, provider):
            raise ValueError(
                f"Audio file exceeds 25 MB limit for provider {provider!r}. "
                f"Use --provider whisper_local for larger files."
            )
```

- [ ] **Step 7: Run tests**

Run: `cd llmind-cli && pytest tests/test_cli.py tests/test_safety.py -v`
Run: `cd llmind-cli && pytest -x`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add llmind-cli/llmind/cli.py llmind-cli/llmind/safety.py llmind-cli/llmind/enricher.py \
        llmind-cli/tests/test_cli.py llmind-cli/tests/test_safety.py
git commit -m "feat(cli): add whisper_local provider choice and 25 MB cloud audio cap"
```

---
