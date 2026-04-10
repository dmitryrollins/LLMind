"""Tests for llmind.enricher — enrichment pipeline."""
from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import patch

import pytest

from llmind.crypto import sha256_file
from llmind.enricher import enrich
from llmind.injector import inject
from llmind.models import ExtractionResult
from llmind.reader import read as read_meta
from llmind.xmp import build_xmp

MOCK_EXTRACTION = ExtractionResult(
    language="en",
    description="A white test image.",
    text="Hello world",
    structure={"type": "document", "regions": [], "figures": [], "tables": []},
)

MOCK_EXTRACTION_WITH_STRUCTURE = ExtractionResult(
    language="en",
    description="A document with regions and tables.",
    text="Some text",
    structure={
        "type": "document",
        "regions": [{"label": "header", "type": "text"}],
        "figures": [{"caption": "Figure 1"}],
        "tables": [{"headers": ["Col A", "Col B"], "rows": 3}],
    },
)


@patch("llmind.enricher.inject")
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_success(mock_query, mock_inject, jpeg_file: Path) -> None:
    """Successful enrichment returns success=True, skipped=False, version=1, no error."""
    result = enrich(jpeg_file)

    assert result.success is True
    assert result.skipped is False
    assert result.version == 1
    assert result.error is None
    assert result.regions == 0
    assert result.figures == 0
    assert result.tables == 0
    assert result.elapsed >= 0.0
    mock_query.assert_called_once()
    mock_inject.assert_called_once()


@patch("llmind.enricher.is_fresh", return_value=True)
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_skips_fresh_file(mock_query, mock_is_fresh, jpeg_file: Path) -> None:
    """Enrichment is skipped when is_fresh() reports the file is already enriched."""
    result = enrich(jpeg_file)

    assert result.skipped is True
    assert result.success is False
    assert result.version is None
    assert result.error is None
    # query_image should NOT be called for a fresh file
    mock_query.assert_not_called()


@patch("llmind.enricher.inject")
@patch("llmind.enricher.is_fresh", return_value=True)
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_force_overwrites(mock_query, mock_is_fresh, mock_inject, jpeg_file: Path) -> None:
    """force=True re-enriches even when is_fresh() reports the file is fresh."""
    result = enrich(jpeg_file, force=True)

    assert result.success is True
    assert result.skipped is False
    # is_fresh should not have been consulted when force=True
    mock_is_fresh.assert_not_called()
    mock_query.assert_called_once()


@patch("llmind.enricher.inject", wraps=inject)
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_increments_version(mock_query, mock_inject, jpeg_file: Path, sample_layer) -> None:
    """Second enrichment produces version=2 (appended to existing layer history)."""
    # Inject existing layer with a different checksum so freshness check doesn't skip
    inject(jpeg_file, build_xmp([sample_layer]))

    result = enrich(jpeg_file)

    assert result.success is True
    assert result.version == 2


@patch("llmind.enricher.inject", wraps=inject)
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_signs_layer_when_key_provided(mock_query, mock_inject, jpeg_file: Path) -> None:
    """When creation_key is given, the stored layer has a non-empty signature."""
    creation_key = "a" * 64  # 256-bit hex key

    result = enrich(jpeg_file, creation_key=creation_key)

    assert result.success is True
    # Read back the XMP and verify the signature was set
    meta = read_meta(jpeg_file)
    assert meta is not None
    assert meta.current.signature is not None
    assert len(meta.current.signature) > 0


@patch("llmind.enricher.inject")
@patch("llmind.enricher.query_image", side_effect=RuntimeError("Provider unreachable"))
def test_enrich_captures_exception(mock_query, mock_inject, jpeg_file: Path) -> None:
    """Exceptions during enrichment are captured into EnrichResult.error."""
    result = enrich(jpeg_file)

    assert result.success is False
    assert result.skipped is False
    assert result.error is not None
    assert len(result.error) > 0
    assert result.version is None


def test_enrich_unsafe_file_returns_error(tmp_path: Path) -> None:
    """Passing an unsupported file extension results in success=False with an error."""
    exe_file = tmp_path / "malware.exe"
    exe_file.write_bytes(b"MZ\x90\x00" * 10)  # fake PE header bytes

    result = enrich(exe_file)

    assert result.success is False
    assert result.skipped is False
    assert result.error is not None
    assert "Unsafe" in result.error


@patch("llmind.enricher.inject")
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION_WITH_STRUCTURE)
def test_enrich_counts_structure_elements(mock_query, mock_inject, jpeg_file: Path) -> None:
    """EnrichResult correctly counts regions, figures, and tables from extraction."""
    result = enrich(jpeg_file)

    assert result.success is True
    assert result.regions == 1
    assert result.figures == 1
    assert result.tables == 1


# ---------------------------------------------------------------------------
# Provider tests
# ---------------------------------------------------------------------------


@patch("llmind.enricher.inject")
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_provider_default_is_ollama(mock_query, mock_inject, jpeg_file: Path) -> None:
    """Default provider is ollama."""
    result = enrich(jpeg_file)

    assert result.success is True
    call_kwargs = mock_query.call_args.kwargs
    assert call_kwargs.get("provider") == "ollama"


@patch("llmind.enricher.inject")
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_anthropic_provider(mock_query, mock_inject, jpeg_file: Path) -> None:
    """provider='anthropic' is passed through to query_image."""
    result = enrich(jpeg_file, provider="anthropic")

    assert result.success is True
    call_kwargs = mock_query.call_args.kwargs
    assert call_kwargs.get("provider") == "anthropic"


@patch("llmind.enricher.inject")
@patch("llmind.enricher.query_image", return_value=MOCK_EXTRACTION)
def test_enrich_openai_provider(mock_query, mock_inject, jpeg_file: Path) -> None:
    """provider='openai' is passed through to query_image."""
    result = enrich(jpeg_file, provider="openai")

    assert result.success is True
    call_kwargs = mock_query.call_args.kwargs
    assert call_kwargs.get("provider") == "openai"
