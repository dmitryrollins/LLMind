"""Tests for llmind.verifier."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from llmind.crypto import generate_key, sign_layer
from llmind.injector import inject
from llmind.models import Layer
from llmind.verifier import verify
from llmind.xmp import build_xmp, layer_to_dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signed_layer(path: Path, creation_key: str) -> Layer:
    """Build and return a Layer signed with the given key (checksum matches file)."""
    from llmind.crypto import sha256_file, derive_key_id
    checksum = sha256_file(path)
    layer = Layer(
        version=1,
        timestamp="2026-04-10T00:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum=checksum,
        language="en",
        description="Signed test layer",
        text="Signed text",
        structure={"type": "test", "regions": [], "figures": [], "tables": []},
        key_id=derive_key_id(creation_key),
        signature=None,
    )
    sig = sign_layer(creation_key, layer_to_dict(layer, include_signature=False))
    return dataclasses.replace(layer, signature=sig)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_verify_no_layer(jpeg_file: Path) -> None:
    result = verify(jpeg_file)
    assert result.has_layer is False
    assert result.checksum_valid is False
    assert result.signature_valid is None
    assert result.layer_count == 0
    assert result.current_version is None


def test_verify_has_layer(jpeg_file: Path, sample_layer: Layer) -> None:
    inject(jpeg_file, build_xmp([sample_layer]))
    result = verify(jpeg_file)
    assert result.has_layer is True


def test_verify_checksum_invalid(jpeg_file: Path) -> None:
    """Inject a layer with a fake checksum that won't match the real file."""
    fake_layer = Layer(
        version=1,
        timestamp="2026-04-10T00:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum="0" * 64,  # definitely wrong
        language="en",
        description="Fake checksum layer",
        text="test",
        structure={},
        key_id="",
        signature=None,
    )
    inject(jpeg_file, build_xmp([fake_layer]))
    result = verify(jpeg_file)
    assert result.has_layer is True
    assert result.checksum_valid is False


def test_verify_signature_none_without_key(jpeg_file: Path) -> None:
    """Verify a signed layer without providing a key → signature_valid is None."""
    key = generate_key()
    signed_layer = _make_signed_layer(jpeg_file, key)
    inject(jpeg_file, build_xmp([signed_layer]))
    result = verify(jpeg_file)  # no key
    assert result.signature_valid is None


def test_verify_signature_valid(jpeg_file: Path) -> None:
    """Enrich with a key and verify with the same key → signature_valid is True."""
    key = generate_key()
    signed_layer = _make_signed_layer(jpeg_file, key)
    inject(jpeg_file, build_xmp([signed_layer]))
    result = verify(jpeg_file, creation_key=key)
    assert result.signature_valid is True


def test_verify_signature_invalid(jpeg_file: Path) -> None:
    """Verify a signed layer with the wrong key → signature_valid is False."""
    key = generate_key()
    wrong_key = generate_key()
    signed_layer = _make_signed_layer(jpeg_file, key)
    inject(jpeg_file, build_xmp([signed_layer]))
    result = verify(jpeg_file, creation_key=wrong_key)
    assert result.signature_valid is False
