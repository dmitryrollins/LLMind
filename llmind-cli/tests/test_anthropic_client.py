"""Tests for llmind.anthropic_client."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from llmind.anthropic_client import query_anthropic

MOCK_CONTENT = json.dumps({
    "language": "en",
    "description": "test",
    "text": "hello",
    "structure": {"type": "document", "regions": [], "figures": [], "tables": []},
})


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
@patch("llmind.anthropic_client._anthropic_sdk")
def test_query_anthropic_success(mock_sdk):
    """Successful call returns ExtractionResult with parsed data."""
    mock_content = MagicMock()
    mock_content.text = MOCK_CONTENT

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_sdk.Anthropic.return_value = mock_client

    result = query_anthropic(b"\xff\xd8\xff" + b"\x00" * 10, model="claude-haiku-4-5-20251001")

    assert result.language == "en"
    assert result.text == "hello"
    assert result.description == "test"
    mock_sdk.Anthropic.assert_called_once_with(api_key="test-key")
    mock_client.messages.create.assert_called_once()


def test_query_anthropic_missing_api_key():
    """Missing ANTHROPIC_API_KEY raises RuntimeError."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            query_anthropic(b"\xff\xd8\xff" + b"\x00" * 10)


def test_query_anthropic_missing_sdk():
    """Missing anthropic SDK raises RuntimeError with install hint."""
    with patch("llmind.anthropic_client._anthropic_sdk", None):
        with pytest.raises(RuntimeError, match="pip install"):
            query_anthropic(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
@patch("llmind.anthropic_client._anthropic_sdk")
def test_query_anthropic_api_error_raises_runtime(mock_sdk):
    """API errors are wrapped in RuntimeError."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("Network error")
    mock_sdk.Anthropic.return_value = mock_client

    with pytest.raises(RuntimeError, match="Anthropic API error"):
        query_anthropic(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
@patch("llmind.anthropic_client._anthropic_sdk")
def test_query_anthropic_detects_png(mock_sdk):
    """PNG image bytes are correctly identified as image/png."""
    mock_content = MagicMock()
    mock_content.text = MOCK_CONTENT
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    mock_sdk.Anthropic.return_value = mock_client

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    query_anthropic(png_bytes)

    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0]
    content_blocks = messages[0]["content"] if isinstance(messages, list) else messages
    image_block = next(b for b in content_blocks if b.get("type") == "image")
    assert image_block["source"]["media_type"] == "image/png"
