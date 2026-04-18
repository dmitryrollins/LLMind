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
