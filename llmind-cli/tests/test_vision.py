"""Tests for llmind.vision — shared utilities and dispatcher."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from llmind.models import ExtractionResult
from llmind.vision import (
    PROVIDER_DEFAULTS,
    _detect_media_type,
    _parse_response,
    query_image,
    query_pdf,
)

MOCK_EXTRACTION = ExtractionResult(
    language="en",
    description="A test image.",
    text="Hello world",
    structure={"type": "document", "regions": [], "figures": [], "tables": []},
)

MOCK_PAYLOAD = {
    "language": "en",
    "description": "A test image.",
    "text": "Hello world",
    "structure": {"type": "document", "regions": [], "figures": [], "tables": []},
}


# ---------------------------------------------------------------------------
# _detect_media_type
# ---------------------------------------------------------------------------


def test_detect_media_type_jpeg():
    assert _detect_media_type(b"\xff\xd8\xff" + b"\x00" * 10) == "image/jpeg"


def test_detect_media_type_png():
    assert _detect_media_type(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10) == "image/png"


def test_detect_media_type_webp():
    data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 10
    assert _detect_media_type(data) == "image/webp"


def test_detect_media_type_gif():
    assert _detect_media_type(b"GIF8" + b"\x00" * 10) == "image/gif"
    assert _detect_media_type(b"GIF9" + b"\x00" * 10) == "image/gif"


def test_detect_media_type_unknown():
    assert _detect_media_type(b"RANDOM BYTES HERE") == "image/jpeg"


# ---------------------------------------------------------------------------
# PROVIDER_DEFAULTS
# ---------------------------------------------------------------------------


def test_provider_defaults_keys():
    assert "ollama" in PROVIDER_DEFAULTS
    assert "anthropic" in PROVIDER_DEFAULTS
    assert "openai" in PROVIDER_DEFAULTS


def test_provider_defaults_values_nonempty():
    for provider, model in PROVIDER_DEFAULTS.items():
        assert isinstance(model, str) and len(model) > 0, f"Empty default for {provider}"


# ---------------------------------------------------------------------------
# query_image dispatching
# The lazy imports inside query_image mean we must patch at the source module.
# ---------------------------------------------------------------------------


@patch("llmind.ollama.query_ollama", return_value=MOCK_EXTRACTION)
def test_query_image_dispatches_ollama(mock_query):
    result = query_image(b"img", provider="ollama")
    mock_query.assert_called_once()
    assert result.language == "en"


@patch("llmind.anthropic_client.query_anthropic", return_value=MOCK_EXTRACTION)
def test_query_image_dispatches_anthropic(mock_query):
    result = query_image(b"img", provider="anthropic")
    mock_query.assert_called_once()
    assert result.language == "en"


@patch("llmind.openai_client.query_openai", return_value=MOCK_EXTRACTION)
def test_query_image_dispatches_openai(mock_query):
    result = query_image(b"img", provider="openai")
    mock_query.assert_called_once()
    assert result.language == "en"


def test_query_image_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        query_image(b"img", provider="unknown_provider")


@patch("llmind.ollama.query_ollama", return_value=MOCK_EXTRACTION)
def test_query_image_resolves_model_default_ollama(mock_query):
    """When model=None and provider='ollama', the default model is used."""
    query_image(b"img", provider="ollama", model=None)
    call_kwargs = mock_query.call_args
    assert call_kwargs.kwargs.get("model") == PROVIDER_DEFAULTS["ollama"]


@patch("llmind.anthropic_client.query_anthropic", return_value=MOCK_EXTRACTION)
def test_query_image_resolves_model_default_anthropic(mock_query):
    """When model=None and provider='anthropic', the default model is used."""
    query_image(b"img", provider="anthropic", model=None)
    call_kwargs = mock_query.call_args
    assert call_kwargs.kwargs.get("model") == PROVIDER_DEFAULTS["anthropic"]


@patch("llmind.openai_client.query_openai", return_value=MOCK_EXTRACTION)
def test_query_image_resolves_model_default_openai(mock_query):
    """When model=None and provider='openai', the default model is used."""
    query_image(b"img", provider="openai", model=None)
    call_kwargs = mock_query.call_args
    assert call_kwargs.kwargs.get("model") == PROVIDER_DEFAULTS["openai"]


# ---------------------------------------------------------------------------
# query_pdf
# ---------------------------------------------------------------------------


@patch("llmind.ollama.query_ollama", return_value=MOCK_EXTRACTION)
def test_query_pdf_single_page(mock_query):
    result = query_pdf([b"page1"], provider="ollama")
    assert result.language == "en"
    assert result.text == "Hello world"
    assert "PAGE" not in result.text


@patch("llmind.ollama.query_ollama")
def test_query_pdf_multi_page_separator(mock_query):
    page2 = ExtractionResult(
        language="en",
        description="Page 2",
        text="Page two text",
        structure={"type": "document", "regions": [], "figures": [], "tables": []},
    )
    mock_query.side_effect = [MOCK_EXTRACTION, page2]

    result = query_pdf([b"page1", b"page2"], provider="ollama")

    assert "═══ PAGE 1 ═══" in result.text
    assert "═══ PAGE 2 ═══" in result.text
    assert "Hello world" in result.text
    assert "Page two text" in result.text
    assert result.language == "en"
    assert result.description == "A test image."
