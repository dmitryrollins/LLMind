# llmind-cli/tests/test_audio_enricher.py
import shutil
from pathlib import Path
from unittest.mock import patch

from llmind.audio import AudioExtraction
from llmind.crypto import sha256_file
from llmind.enricher import enrich, reenrich
from llmind.models import Segment
from llmind.reader import is_fresh, read

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
