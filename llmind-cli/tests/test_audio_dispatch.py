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
