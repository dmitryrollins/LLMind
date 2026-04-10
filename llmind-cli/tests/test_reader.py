"""Tests for llmind.reader — JPEG, PNG, and PDF XMP reading (Tasks 7 & 8)."""
from __future__ import annotations

from pathlib import Path

import pytest

from llmind.injector import inject
from llmind.models import LLMindMeta
from llmind.reader import has_llmind_layer, is_fresh, read
from llmind.xmp import build_xmp


def test_has_llmind_layer_false_for_plain_jpeg(jpeg_file: Path) -> None:
    """A plain JPEG with no XMP returns False."""
    assert has_llmind_layer(jpeg_file) is False


def test_has_llmind_layer_true_after_inject(jpeg_file: Path, sample_layer) -> None:
    """After injecting valid llmind XMP, has_llmind_layer returns True."""
    xmp = build_xmp([sample_layer])
    inject(jpeg_file, xmp)
    assert has_llmind_layer(jpeg_file) is True


def test_read_returns_none_for_plain_jpeg(jpeg_file: Path) -> None:
    """read() returns None for a plain JPEG with no llmind XMP."""
    assert read(jpeg_file) is None


def test_read_returns_llmind_meta_after_inject(jpeg_file: Path, sample_layer) -> None:
    """read() returns a LLMindMeta instance after injecting valid llmind XMP."""
    xmp = build_xmp([sample_layer])
    inject(jpeg_file, xmp)
    result = read(jpeg_file)
    assert isinstance(result, LLMindMeta)
    assert result.layer_count == 1
    assert result.current.checksum == sample_layer.checksum


def test_is_fresh_false_for_plain_jpeg(jpeg_file: Path) -> None:
    """is_fresh() returns False for a plain JPEG with no llmind layer."""
    assert is_fresh(jpeg_file, "abc") is False


def test_is_fresh_true_when_checksum_matches(jpeg_file: Path, sample_layer) -> None:
    """is_fresh() returns True when the stored checksum matches the given checksum."""
    xmp = build_xmp([sample_layer])
    inject(jpeg_file, xmp)
    assert is_fresh(jpeg_file, sample_layer.checksum) is True


def test_is_fresh_false_when_checksum_differs(jpeg_file: Path, sample_layer) -> None:
    """is_fresh() returns False when the stored checksum differs from the given checksum."""
    xmp = build_xmp([sample_layer])
    inject(jpeg_file, xmp)
    assert is_fresh(jpeg_file, "xyz") is False


# ── PNG tests ────────────────────────────────────────────────────────────────

def test_has_llmind_layer_true_after_inject_png(png_file: Path, sample_layer) -> None:
    """After injecting valid llmind XMP into PNG, has_llmind_layer returns True."""
    xmp = build_xmp([sample_layer])
    inject(png_file, xmp)
    assert has_llmind_layer(png_file) is True


def test_read_returns_llmind_meta_after_inject_png(png_file: Path, sample_layer) -> None:
    """read() returns a LLMindMeta instance after injecting valid llmind XMP into PNG."""
    xmp = build_xmp([sample_layer])
    inject(png_file, xmp)
    result = read(png_file)
    assert isinstance(result, LLMindMeta)
    assert result.layer_count == 1
    assert result.current.checksum == sample_layer.checksum


# ── PDF tests ────────────────────────────────────────────────────────────────

def test_has_llmind_layer_true_after_inject_pdf(pdf_file: Path, sample_layer) -> None:
    """After injecting valid llmind XMP into PDF, has_llmind_layer returns True."""
    xmp = build_xmp([sample_layer])
    inject(pdf_file, xmp)
    assert has_llmind_layer(pdf_file) is True


def test_read_returns_llmind_meta_after_inject_pdf(pdf_file: Path, sample_layer) -> None:
    """read() returns a LLMindMeta instance after injecting valid llmind XMP into PDF."""
    xmp = build_xmp([sample_layer])
    inject(pdf_file, xmp)
    result = read(pdf_file)
    assert isinstance(result, LLMindMeta)
    assert result.layer_count == 1
    assert result.current.checksum == sample_layer.checksum
