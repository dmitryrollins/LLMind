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
