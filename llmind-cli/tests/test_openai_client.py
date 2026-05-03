"""Tests for llmind.openai_client."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from llmind.openai_client import query_openai

MOCK_CONTENT = json.dumps({
    "language": "en",
    "description": "test",
    "text": "hello",
    "structure": {"type": "document", "regions": [], "figures": [], "tables": []},
})


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
@patch("llmind.openai_client._openai_sdk")
def test_query_openai_success(mock_sdk):
    """Successful call returns ExtractionResult with parsed data."""
    mock_message = MagicMock()
    mock_message.content = MOCK_CONTENT

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_sdk.OpenAI.return_value = mock_client

    result = query_openai(b"\xff\xd8\xff" + b"\x00" * 10, model="gpt-4o-mini")

    assert result.language == "en"
    assert result.text == "hello"
    assert result.description == "test"
    mock_sdk.OpenAI.assert_called_once_with(api_key="test-key")
    mock_client.chat.completions.create.assert_called_once()


def test_query_openai_missing_api_key():
    """Missing OPENAI_API_KEY raises RuntimeError."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            query_openai(b"\xff\xd8\xff" + b"\x00" * 10)


def test_query_openai_missing_sdk():
    """Missing openai SDK raises RuntimeError with install hint."""
    with patch("llmind.openai_client._openai_sdk", None):
        with pytest.raises(RuntimeError, match="pip install"):
            query_openai(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
@patch("llmind.openai_client._openai_sdk")
def test_query_openai_api_error_raises_runtime(mock_sdk):
    """API errors are wrapped in RuntimeError."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("Network error")
    mock_sdk.OpenAI.return_value = mock_client

    with pytest.raises(RuntimeError, match="OpenAI API error"):
        query_openai(b"\xff\xd8\xff" + b"\x00" * 10)


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
@patch("llmind.openai_client._openai_sdk")
def test_query_openai_image_url_format(mock_sdk):
    """Image is sent as data URL with correct media type."""
    mock_message = MagicMock()
    mock_message.content = MOCK_CONTENT
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_sdk.OpenAI.return_value = mock_client

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    query_openai(png_bytes)

    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0]
    content_blocks = messages[0]["content"]
    image_block = next(b for b in content_blocks if b.get("type") == "image_url")
    assert "data:image/png;base64," in image_block["image_url"]["url"]
