from __future__ import annotations

import json

import pytest
import requests
import responses as responses_lib

from llmind.ollama import _parse_response, query_ollama, query_ollama_pdf

MOCK_PAYLOAD = {
    "language": "en",
    "description": "A white test image.",
    "text": "Hello world",
    "structure": {
        "type": "document",
        "regions": [],
        "figures": [],
        "tables": [],
    },
}

MOCK_RESPONSE = {"message": {"content": json.dumps(MOCK_PAYLOAD)}}

OLLAMA_URL = "http://localhost:11434/api/chat"


# ---------------------------------------------------------------------------
# query_ollama — happy path
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_query_ollama_success():
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        json=MOCK_RESPONSE,
        status=200,
    )
    result = query_ollama(b"fake_image_bytes", retries=1, retry_delay=0)
    assert result.language == "en"
    assert result.description == "A white test image."
    assert result.text == "Hello world"
    assert result.structure["type"] == "document"


@responses_lib.activate
def test_query_ollama_strips_markdown_fences():
    fenced_content = "```json\n" + json.dumps(MOCK_PAYLOAD) + "\n```"
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        json={"message": {"content": fenced_content}},
        status=200,
    )
    result = query_ollama(b"fake_image_bytes", retries=1, retry_delay=0)
    assert result.language == "en"
    assert result.text == "Hello world"


# ---------------------------------------------------------------------------
# query_ollama — retry behaviour
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_query_ollama_retries_on_connection_error():
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        body=requests.ConnectionError("refused"),
    )
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        json=MOCK_RESPONSE,
        status=200,
    )
    result = query_ollama(b"img", retries=2, retry_delay=0)
    assert result.language == "en"
    assert len(responses_lib.calls) == 2


@responses_lib.activate
def test_query_ollama_raises_after_max_retries():
    for _ in range(3):
        responses_lib.add(
            responses_lib.POST,
            OLLAMA_URL,
            body=requests.ConnectionError("refused"),
        )
    with pytest.raises(RuntimeError, match="unreachable"):
        query_ollama(b"img", retries=3, retry_delay=0)


@responses_lib.activate
def test_query_ollama_raises_on_http_error():
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        json={"error": "internal"},
        status=500,
    )
    with pytest.raises(RuntimeError, match="Ollama error"):
        query_ollama(b"img", retries=1, retry_delay=0)


# ---------------------------------------------------------------------------
# query_ollama_pdf
# ---------------------------------------------------------------------------


@responses_lib.activate
def test_query_pdf_single_page():
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        json=MOCK_RESPONSE,
        status=200,
    )
    result = query_ollama_pdf([b"page1"], retries=1, retry_delay=0)
    assert result.language == "en"
    assert result.text == "Hello world"
    # No page separator for a single page
    assert "PAGE" not in result.text


@responses_lib.activate
def test_query_pdf_multi_page():
    page2_payload = dict(MOCK_PAYLOAD, text="Page two text")
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        json=MOCK_RESPONSE,
        status=200,
    )
    responses_lib.add(
        responses_lib.POST,
        OLLAMA_URL,
        json={"message": {"content": json.dumps(page2_payload)}},
        status=200,
    )
    result = query_ollama_pdf([b"page1", b"page2"], retries=1, retry_delay=0)
    assert "═══ PAGE 1 ═══" in result.text
    assert "═══ PAGE 2 ═══" in result.text
    assert "Hello world" in result.text
    assert "Page two text" in result.text
    # Metadata comes from first page
    assert result.language == "en"
    assert result.description == "A white test image."


# ---------------------------------------------------------------------------
# _parse_response — direct unit tests
# ---------------------------------------------------------------------------


def test_parse_response_valid_json():
    result = _parse_response(json.dumps(MOCK_PAYLOAD))
    assert result.language == "en"
    assert result.text == "Hello world"
    assert result.structure["type"] == "document"


def test_parse_response_strips_fences():
    fenced = "```json\n" + json.dumps(MOCK_PAYLOAD) + "\n```"
    result = _parse_response(fenced)
    assert result.language == "en"
    assert result.text == "Hello world"


def test_parse_response_raises_on_invalid_json():
    with pytest.raises(ValueError, match="Malformed JSON"):
        _parse_response("not valid json {{{")
