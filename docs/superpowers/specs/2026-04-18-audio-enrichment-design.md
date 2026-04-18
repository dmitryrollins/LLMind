# Audio Enrichment — Design Spec

**Date:** 2026-04-18
**Scope:** `llmind-cli` only (v1)
**Status:** Approved design, pending implementation plan

---

## 1. Purpose

Extend LLMind's enrichment pipeline — currently JPEG/PNG/PDF via vision models — to cover **audio files**. Audio is enriched by extracting a transcript (speech-to-text), a short summary, and timestamped segments, then embedding all of that as XMP metadata inside the audio file's standard metadata slot.

The enriched file stays playable in any audio tool. LLMind-aware tools can read the embedded layer to skip re-transcription, verify authenticity, and search by content.

---

## 2. Scope

### In scope (v1)

- **Formats:** MP3, WAV, M4A
- **Surfaces:** CLI only (`llmind-cli`). `watcher.py` auto-picks audio files because dispatch is by extension.
- **Providers:** OpenAI Whisper, Gemini (native audio), local Whisper via `faster-whisper`
- **Metadata embedding:** XMP packets inside format-standard slots (Adobe XMP spec for each container)
- **Layer contents:** transcript, 1–2 sentence summary, timestamped segments, language, duration
- **Signing/verification:** identical to image layers — HMAC-SHA256 via existing `crypto.py`

### Out of scope (v1)

- FastAPI web app (`llmind-app`) and React browser app (`llmind-converter.jsx`) — same pipeline, added in a later version
- Native tag mirrors (ID3 `USLT`, M4A `©lyr`, WAV `INFO`) — iTunes/QuickTime will not display the transcript in v1
- Anthropic/Ollama audio support — neither provider supports audio input
- Speaker diarization (who spoke when)
- Audio re-encoding, format conversion, or quality preservation checks beyond "sample bytes unchanged after injection"
- Formats beyond MP3/WAV/M4A (FLAC, OGG, Opus, etc.)

---

## 3. Architecture

Audio enrichment mirrors the existing vision pipeline. Two new modules plus targeted extensions to existing modules.

### 3.1 New modules

**`llmind/audio.py`** — provider dispatch, analogous to `vision.py`.

```python
@dataclass(frozen=True)
class AudioExtraction:
    text: str                          # full transcript
    summary: str                       # 1–2 sentence description
    segments: tuple[Segment, ...]      # timestamped chunks
    language: str                      # BCP-47
    duration_seconds: float

AUDIO_PROVIDER_DEFAULTS = {
    "openai": "whisper-1",
    "gemini": "gemini-2.5-flash",
    "whisper_local": "base",
}

def query_audio(
    path: Path,
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
) -> AudioExtraction: ...
```

**`llmind/audio_injector.py`** — format-aware XMP embedding.

```python
def inject_audio(path: Path, xmp_packet: str) -> None:
    """Inject XMP into an audio file, replacing any prior LLMind XMP packet."""
```

Internally dispatches to `_inject_mp3`, `_inject_wav`, `_inject_m4a`. Implementation details in §5.

### 3.2 Extended modules

| Module | Change |
|--------|--------|
| `safety.py` | Add audio MIME/extension checks (`.mp3`/`.wav`/`.m4a`). Cloud provider cap: 25 MB (OpenAI Whisper limit). Local cap: existing 500 MB. |
| `models.py` | Extend `Layer` with `segments: tuple[Segment, ...] \| None`, `duration_seconds: float \| None`, `media_type: str = "image"`. New `Segment` frozen dataclass. |
| `xmp.py` | Serialize `segments` as JSON string in `llmind:segments`; serialize `duration_seconds` and `media_type`. Deserialize with sensible defaults for backwards compat. |
| `enricher.py` | Dispatch by extension: PDF → `query_pdf`, audio → `query_audio`, else → `query_image`. Adapter function `_audio_to_extraction` keeps `_enrich` branch small. |
| `injector.py` | Top-level dispatcher: audio suffixes → `audio_injector.inject_audio`, else → existing image/PDF injection. |
| `reader.py` / `verifier.py` | Format-agnostic today; only need to locate the XMP packet in each audio format. Delegated to a small `xmp_locator` helper per format. |
| `cli.py` | No change — existing `enrich` command transparently accepts audio paths. |

### 3.3 New dependencies

- **`faster-whisper`** — local transcription (pulls in `ctranslate2`)
- **`mutagen`** — MP3 ID3v2 tag reading/writing

WAV and M4A box manipulation is done with stdlib — no extra dependencies.

---

## 4. Data Model

### 4.1 `Layer` dataclass (extended)

```python
@dataclass(frozen=True)
class Segment:
    start: float           # seconds from start of audio
    end: float             # seconds from start of audio
    text: str

@dataclass(frozen=True)
class Layer:
    # existing fields — unchanged:
    version: int
    timestamp: str
    generator: str
    generator_model: str
    checksum: str
    language: str
    description: str       # image: visual description; audio: summary
    text: str              # image: OCR text; audio: full transcript
    structure: dict        # image: regions/figures/tables; audio: {}
    key_id: str
    signature: str | None
    # new optional fields:
    segments: tuple[Segment, ...] | None = None
    duration_seconds: float | None = None
    media_type: str = "image"       # "image" | "pdf" | "audio"
```

### 4.2 Rationale — reuse `Layer` instead of subclassing

- `sign_layer` and verification iterate a serialized dict of the layer. Optional keys are trivial to add; a subclass forces type-branching in `crypto.py`, `xmp.py`, and `reader.py`.
- `llmind:version` numbering is per-file and monotonic across media types. One dataclass keeps the invariant clean.
- `media_type` discriminator lets consumers switch behavior without type introspection.

### 4.3 Audio → existing-field mapping

| Field | Audio meaning |
|-------|---------------|
| `text` | Full transcript, single string, segments joined by `\n` |
| `description` | 1–2 sentence summary (generated per §5.3) |
| `language` | BCP-47 code — Whisper returns ISO-639-1, normalized on ingress |
| `structure` | `{}` — segments live in their own field, not here (semantic incompatibility with regions/figures/tables) |

### 4.4 XMP serialization

| XMP element | Type | Notes |
|-------------|------|-------|
| `llmind:segments` | string (JSON array) | `[{"start": 0.0, "end": 3.2, "text": "..."}]`. Same JSON-in-XMP technique as `llmind:structure`. |
| `llmind:duration_seconds` | float | Omitted for non-audio layers. |
| `llmind:media_type` | string | `"audio"`, `"pdf"`, or `"image"`. Omitted for backwards compat — reader defaults to `"image"` when absent. |

### 4.5 Backwards compatibility

Existing `.llmind.jpg`/`.llmind.pdf` files have none of the new XMP elements. The reader treats missing fields as:

- `segments` → `None`
- `duration_seconds` → `None`
- `media_type` → `"image"`

Existing signatures remain valid because the new fields are not part of the signed payload for image layers. For new audio layers, the canonical dict sent to `sign_layer` includes the new fields (sorted keys, stable JSON). A regression test confirms old image signatures still verify after the canonicalization change.

---

## 5. Provider Layer

### 5.1 Dispatch table

| Provider | Transcript | Segments | Summary | Notes |
|----------|-----------|----------|---------|-------|
| `openai` | Whisper API `audio.transcriptions.create`, `response_format="verbose_json"` | Native | Second call to `gpt-4o-mini` (hardcoded for v1; model id lives in `AUDIO_SUMMARIZER_DEFAULTS` alongside `AUDIO_PROVIDER_DEFAULTS`) | Two round-trips per file. |
| `gemini` | File API upload + prompt "transcribe with timestamps" | Parsed from structured JSON response | Same call returns `{transcript, segments, summary}` | One round-trip. |
| `whisper_local` | `faster-whisper` in-process | Native | Deterministic extractive summary (first sentence + longest sentence, ~2 lines) | No cloud calls. Document that summary quality is best on cloud providers. |

### 5.2 Unsupported providers

If the user passes `--provider anthropic` or `--provider ollama` on an audio file, `query_audio` raises `UnsupportedProviderError` with a message listing supported audio providers. CLI exits non-zero. No silent fallback.

### 5.3 Interface shape

Audio providers take a `Path`, not `bytes`:

- OpenAI Whisper accepts file uploads directly
- Gemini File API takes a file handle
- `faster-whisper` streams from disk to avoid loading large files into RAM

This differs intentionally from `vision.query_image(bytes)`. Passing `Path` matches idiomatic audio tooling.

### 5.4 Size limits

Added to `safety.is_safe_file`:

- Cloud providers (`openai`, `gemini`): reject audio >25 MB with a clear error (OpenAI Whisper hard limit)
- Local (`whisper_local`): reuse existing 500 MB cap

---

## 6. Enrichment Flow

`enricher._enrich` already branches on `.pdf` vs. image. Add a third branch:

```python
suffix = path.suffix.lower()
if suffix == ".pdf":
    extraction = query_pdf(...)
    media_type = "pdf"
elif suffix in {".mp3", ".wav", ".m4a"}:
    audio = query_audio(path, provider=provider, model=model, api_key=api_key)
    extraction = _audio_to_extraction(audio)
    media_type = "audio"
else:
    extraction = query_image(...)
    media_type = "image"
```

The `Layer` construction passes `media_type`, `segments`, `duration_seconds` through. `_audio_to_extraction` is a small adapter that keeps audio-specific fields out of the main branch.

**Freshness:** `reader.is_fresh(path, checksum)` compares stored `llmind:checksum` to `sha256_file(path)`. Works identically for audio — the checksum is over the whole file. Re-enrichment triggers correctly when audio samples change.

**Re-enrich invariant:** the checksum on the freshly injected layer is the hash **before** injection. Already handled by existing `_enrich` flow. No audio-specific change needed.

**Output naming:** same convention as images. `hello.mp3` → `hello.llmind.mp3` on first enrich. In-place on re-enrich.

---

## 7. XMP Injection Per Format

### 7.1 MP3 — ID3v2 `PRIV` frame, owner `XMP`

- **Slot:** Per Adobe XMP Specification Part 3, `PRIV` frame with owner identifier `XMP`
- **Why not `GEOB`:** Some tools use `GEOB` with MIME `application/rdf+xml`, but Adobe's canonical slot is `PRIV:XMP`. We follow the spec so our XMP reader uses one code path.
- **Injection:** `mutagen.id3.ID3` — read existing tags, remove all prior `PRIV:XMP` frames, add the new one, save.
- **Reading:** `mutagen.id3.ID3(path).getall("PRIV")` → filter `owner == "XMP"` → decode `data` as UTF-8 → feed existing XMP parser.

### 7.2 WAV — RIFF `_PMX` chunk

- **Slot:** Top-level `_PMX` chunk (Adobe spec for XMP-in-RIFF)
- **Why not `LIST:INFO`:** INFO holds short text fields (artist, title); not a spec-compliant home for an XMP packet. `_PMX` is the explicit Adobe slot.
- **Implementation:** Pure stdlib `_pmx_chunk.py` helper (~40 lines). RIFF chunks are `[4B ID][4B LE size][payload][pad byte if odd]`. Read RIFF top level, strip any existing `_PMX`, append new one, rewrite top-level `RIFF` size header.

### 7.3 M4A — top-level `uuid` atom

- **Slot:** Top-level `uuid` atom with UUID `BE7ACFCB-97A9-42E8-9C71-999491E3AFAC` (Adobe's reserved XMP-in-MP4 UUID)
- **Why manual over `mutagen.mp4`:** Mutagen's `uuid` atom support is patchy and would force us into private APIs. MP4 boxes are `[4B size][4B type][payload]` — almost identical to RIFF. A `_mp4_uuid.py` helper (~80 lines) inserts/replaces the top-level `uuid` atom cleanly.

### 7.4 Unified interface

```python
# audio_injector.py
def inject_audio(path: Path, xmp_packet: str) -> None:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        _inject_mp3(path, xmp_packet)
    elif suffix == ".wav":
        _inject_wav(path, xmp_packet)
    elif suffix == ".m4a":
        _inject_m4a(path, xmp_packet)
    else:
        raise ValueError(f"Unsupported audio format: {suffix}")
```

`injector.py` gets a thin top-level dispatcher: audio suffixes → `inject_audio`, else → existing image/PDF logic. `xmp.build_xmp(...)` is unchanged — it produces one XMP string regardless of target format.

### 7.5 Duplicate-prevention guarantee

Every injection function explicitly removes prior LLMind XMP packets before inserting the new one. No format should end up with multiple XMP packets after re-enrich.

---

## 8. Testing Strategy

### 8.1 Unit tests (fast, deterministic, no providers)

**Injection round-trip:**
- `test_audio_injector_mp3.py` — inject known XMP → read back → exact match. Fixture: ~10 KB silent MP3.
- `test_audio_injector_wav.py` — same for `_PMX` chunk. Fixture: minimal silent WAV.
- `test_audio_injector_m4a.py` — same for `uuid` atom. Fixture: ~20 KB silent M4A.

Each test verifies:
- (a) Second injection **replaces** the first LLMind packet, not duplicates
- (b) Unrelated tags/chunks/atoms are preserved
- (c) File still parses as valid audio after injection
- (d) Audio sample bytes are unchanged — extracted via format-specific walker (MP3: skip ID3v2 header, hash remaining MPEG frames; WAV: hash `data` chunk payload; M4A: hash `mdat` atom payload) and compared before/after injection

**Fixtures:** Commit tiny silent fixtures in `tests/fixtures/audio/` (<100 KB total). Prefer committed-as-is over on-the-fly generation to remove FFmpeg dependency from test runs.

**Model & XMP:**
- `test_models_audio_layer.py` — `Layer` with audio fields serializes/deserializes correctly
- `test_xmp_audio_fields.py` — `build_xmp()` + `read()` round-trip preserves segments JSON and numeric duration
- `test_xmp_backwards_compat.py` — parse fixture XMP from an existing image layer → reader returns `media_type="image"`, `segments=None`
- `test_signing_audio.py` — sign an audio layer → verify → confirm old image signatures still validate

**Provider dispatch (mocked):**
- `test_audio_dispatch.py` — `query_audio` routes correctly per provider name; unsupported providers raise `UnsupportedProviderError`. Provider clients mocked via `unittest.mock` — no real API calls.

### 8.2 Integration tests (marked, opt-in)

`@pytest.mark.integration` — skipped by default, run with `pytest -m integration` when API keys are set.

- **OpenAI Whisper** — transcribe `hello_world.wav`, assert transcript contains "hello" (case-insensitive)
- **Gemini audio** — same fixture, same tolerant assertion
- **Local Whisper** — same fixture; marked integration to keep CI fast

Fixture: 3-second `hello_world.wav` (~30 KB), committed under `tests/fixtures/audio/`.

### 8.3 End-to-end

`test_enrich_audio_e2e.py` — enrich each of `hello_world.{mp3,wav,m4a}` with a fake `query_audio` returning a canned `AudioExtraction`. Verify:
- File renamed to `hello_world.llmind.{mp3,wav,m4a}`
- `reader.read()` returns expected `Layer` with `media_type="audio"`, correct segments, correct summary
- `verifier.verify()` succeeds when signed
- Re-enrich in-place works and appends a v2 layer

### 8.4 Coverage target

80% per project standard, measured by `pytest --cov=llmind --cov-report=term-missing`. `audio.py` dispatch and `audio_injector.py` format code should reach ~90% with unit tests alone; providers covered by integration tests.

### 8.5 Explicitly not tested

- Transcription accuracy benchmarking — provider's problem
- Audio quality preservation beyond "sample bytes unchanged" — we do not re-encode

---

## 9. Error Handling

| Scenario | Behavior |
|----------|----------|
| Unsupported provider on audio file | `UnsupportedProviderError` with supported-providers list. CLI exits non-zero. |
| Audio file >25 MB with cloud provider | Clear safety error from `is_safe_file`. Suggest `--provider whisper_local`. |
| Corrupt audio file | Provider raises; enrichment returns `EnrichResult(success=False, error=...)`. Consistent with existing image/PDF error handling. |
| Missing `faster-whisper` when `--provider whisper_local` | Import error caught, reported as "install `faster-whisper` to use local transcription". |
| XMP injection fails mid-write | Atomic-write pattern (write to temp + rename) already used by existing `injector.py` — audio injectors follow the same pattern. |

---

## 10. Open Questions Resolved During Brainstorming

| Decision | Choice |
|----------|--------|
| Formats for v1 | MP3 + WAV + M4A |
| Provider strategy | OpenAI + Gemini + local Whisper (no cloud fallback) |
| Layer contents | Transcript + summary + timestamped segments |
| Metadata storage | XMP everywhere (consistent with current code) — no native tag mirrors |
| Surfaces | CLI only |

---

## 11. Backwards Compatibility Guarantees

1. Existing `.llmind.jpg`/`.llmind.pdf` files continue to read correctly
2. Existing HMAC signatures continue to verify
3. `Layer` dataclass fields added are **optional with defaults** — no constructor breakage for existing callers
4. `llmind:media_type` omission on read = `"image"` (legacy default)
5. No change to `crypto.sign_layer` API; canonicalization adds new keys only when present

---

## 12. Future Work (Not v1)

- Native tag mirrors for iTunes/QuickTime visibility (ID3 `USLT`, M4A `©lyr`, WAV `INFO`)
- Speaker diarization via `pyannote`
- FLAC, OGG, Opus support
- FastAPI + React surface parity
- Streaming transcription for files >25 MB without local fallback
- Chapter/silence-based segmentation beyond Whisper's default
