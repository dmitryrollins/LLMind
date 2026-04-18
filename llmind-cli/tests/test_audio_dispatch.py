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
