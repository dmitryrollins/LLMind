"""Tests for Gemini embedding provider in llmind.embedder."""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


MOCK_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.embedder.requests")
def test_embed_gemini_success(mock_requests):
    """Successful Gemini embedding returns normalised vector."""
    from llmind.embedder import embed_text

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": {"values": MOCK_EMBEDDING}}
    mock_requests.post.return_value = mock_resp

    result = embed_text("test text", provider="gemini", api_key="test-key")

    assert isinstance(result, list)
    assert len(result) == 5
    import math
    mag = math.sqrt(sum(x * x for x in result))
    assert abs(mag - 1.0) < 0.001
    mock_requests.post.assert_called_once()
    call_url = mock_requests.post.call_args[0][0]
    assert "embedContent" in call_url
    assert "key=test-key" in call_url


def test_embed_gemini_missing_api_key():
    """Missing API key raises ValueError."""
    from llmind.embedder import embed_text

    env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            embed_text("test", provider="gemini")


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.embedder.requests")
def test_embed_gemini_api_error(mock_requests):
    """API error raises ValueError."""
    from llmind.embedder import embed_text

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = Exception("Server error")
    mock_requests.post.return_value = mock_resp

    with pytest.raises(ValueError, match="Gemini embedding error"):
        embed_text("test", provider="gemini", api_key="test-key")


@patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
@patch("llmind.embedder.requests")
def test_embed_gemini_default_model(mock_requests):
    """Default model is text-embedding-004."""
    from llmind.embedder import embed_text

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"embedding": {"values": MOCK_EMBEDDING}}
    mock_requests.post.return_value = mock_resp

    embed_text("test", provider="gemini", api_key="test-key")

    call_url = mock_requests.post.call_args[0][0]
    assert "text-embedding-004" in call_url
