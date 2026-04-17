"""Tests for llmind.gemini_client."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from llmind.gemini_client import query_gemini

MOCK_CONTENT = json.dumps({
    "language": "en",
    "description": "test",
    "text": "hello",
    "structure": {"type": "document", "regions": [], "figures": [], "tables": []},
})


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.gemini_client._genai_sdk")
def test_query_gemini_success(mock_sdk):
    """Successful call returns ExtractionResult with parsed data."""
    mock_response = MagicMock()
    mock_response.text = MOCK_CONTENT

    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response

    mock_client = MagicMock()
    mock_client.models = mock_model
    mock_sdk.Client.return_value = mock_client

    result = query_gemini(b"\xff\xd8\xff" + b"\x00" * 10, model="gemini-2.0-flash")

    assert result.language == "en"
    assert result.text == "hello"
    assert result.description == "test"
    mock_sdk.Client.assert_called_once_with(api_key="test-key")


def test_query_gemini_missing_api_key():
    """Missing GEMINI_API_KEY raises RuntimeError."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            query_gemini(b"\xff\xd8\xff" + b"\x00" * 10)


def test_query_gemini_missing_sdk():
    """Missing google-genai SDK raises RuntimeError with install hint."""
    with patch("llmind.gemini_client._genai_sdk", None):
        with pytest.raises(RuntimeError, match="pip install"):
            query_gemini(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.gemini_client._genai_sdk")
def test_query_gemini_api_error_raises_runtime(mock_sdk):
    """API errors are wrapped in RuntimeError."""
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = Exception("Network error")
    mock_client = MagicMock()
    mock_client.models = mock_model
    mock_sdk.Client.return_value = mock_client

    with pytest.raises(RuntimeError, match="Gemini API error"):
        query_gemini(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.gemini_client._genai_sdk")
def test_query_gemini_detects_png(mock_sdk):
    """PNG image bytes are correctly identified."""
    mock_response = MagicMock()
    mock_response.text = MOCK_CONTENT
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response
    mock_client = MagicMock()
    mock_client.models = mock_model
    mock_sdk.Client.return_value = mock_client

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    query_gemini(png_bytes)

    mock_model.generate_content.assert_called_once()
