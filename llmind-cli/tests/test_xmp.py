"""Tests for llmind.xmp — XMP builder and parser.

Written TDD-first: tests define the contract before implementation exists.
"""

from __future__ import annotations

import json

import pytest

from llmind.models import Layer, LLMindMeta
from llmind.xmp import (
    LLMIND_NS,
    XMP_PACKET_BEGIN,
    XMP_PACKET_END,
    build_xmp,
    layer_to_dict,
    parse_xmp,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_layer() -> Layer:
    return Layer(
        version=1,
        timestamp="2026-04-09T13:00:00Z",
        generator="llmind-cli/0.1",
        generator_model="qwen2.5-vl:7b",
        checksum="a" * 64,
        language="en",
        description="A test image",
        text="Hello world",
        structure={"type": "document", "regions": []},
        key_id="abcdef1234567890",
        signature="s" * 64,
    )


# ---------------------------------------------------------------------------
# layer_to_dict tests
# ---------------------------------------------------------------------------


def test_layer_to_dict_includes_signature(sample_layer: Layer) -> None:
    d = layer_to_dict(sample_layer, include_signature=True)
    assert "signature" in d
    assert d["signature"] == sample_layer.signature


def test_layer_to_dict_excludes_signature(sample_layer: Layer) -> None:
    d = layer_to_dict(sample_layer, include_signature=False)
    assert "signature" not in d


# ---------------------------------------------------------------------------
# build_xmp tests
# ---------------------------------------------------------------------------


def test_build_xmp_contains_namespace(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    assert LLMIND_NS in xmp


def test_build_xmp_contains_packet_markers(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    assert XMP_PACKET_BEGIN in xmp
    assert XMP_PACKET_END in xmp


def test_build_xmp_escapes_ampersand() -> None:
    layer = Layer(
        version=1,
        timestamp="2026-04-09T13:00:00Z",
        generator="llmind-cli/0.1",
        generator_model="qwen2.5-vl:7b",
        checksum="b" * 64,
        language="en",
        description="cats & dogs",
        text="normal text",
        structure={},
        key_id="abcdef1234567890",
        signature="t" * 64,
    )
    xmp = build_xmp([layer])
    assert "&amp;" in xmp
    assert "cats & dogs" not in xmp


def test_build_xmp_escapes_lt_gt() -> None:
    layer = Layer(
        version=1,
        timestamp="2026-04-09T13:00:00Z",
        generator="llmind-cli/0.1",
        generator_model="qwen2.5-vl:7b",
        checksum="c" * 64,
        language="en",
        description="normal",
        text="<tag>content</tag>",
        structure={},
        key_id="abcdef1234567890",
        signature="u" * 64,
    )
    xmp = build_xmp([layer])
    assert "&lt;tag&gt;" in xmp
    assert "<tag>" not in xmp.split("<?xpacket")[1]  # not in body


def test_build_xmp_escapes_quotes() -> None:
    layer = Layer(
        version=1,
        timestamp="2026-04-09T13:00:00Z",
        generator="llmind-cli/0.1",
        generator_model="qwen2.5-vl:7b",
        checksum="d" * 64,
        language="en",
        description='"quoted"',
        text="normal",
        structure={},
        key_id="abcdef1234567890",
        signature="v" * 64,
    )
    xmp = build_xmp([layer])
    assert "&quot;quoted&quot;" in xmp


def test_build_xmp_layer_count(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    assert 'llmind:layer_count="1"' in xmp


def test_build_xmp_immutable_true(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    assert 'llmind:immutable="true"' in xmp


# ---------------------------------------------------------------------------
# parse_xmp tests
# ---------------------------------------------------------------------------


def test_parse_xmp_returns_llmind_meta(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    meta = parse_xmp(xmp)
    assert isinstance(meta, LLMindMeta)


def test_parse_xmp_current_is_last_layer(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    meta = parse_xmp(xmp)
    assert meta.current == meta.layers[-1]


def test_parse_xmp_layer_count(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    meta = parse_xmp(xmp)
    assert meta.layer_count == len(meta.layers)


def test_build_parse_roundtrip(sample_layer: Layer) -> None:
    xmp = build_xmp([sample_layer])
    meta = parse_xmp(xmp)
    recovered = meta.current
    assert recovered.version == sample_layer.version
    assert recovered.timestamp == sample_layer.timestamp
    assert recovered.generator == sample_layer.generator
    assert recovered.generator_model == sample_layer.generator_model
    assert recovered.checksum == sample_layer.checksum
    assert recovered.language == sample_layer.language
    assert recovered.description == sample_layer.description
    assert recovered.text == sample_layer.text
    assert recovered.structure == sample_layer.structure
    assert recovered.key_id == sample_layer.key_id
    assert recovered.signature == sample_layer.signature


def test_parse_xmp_missing_version_raises() -> None:
    # Build a minimal XMP without llmind:version
    xmp_no_version = (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""'
        ' xmlns:llmind="https://llmind.org/ns/1.0/"'
        ' llmind:generator="llmind-cli/0.1"'
        ">"
        "</rdf:Description>"
        "</rdf:RDF>"
        "</x:xmpmeta>"
        '<?xpacket end="w"?>'
    )
    with pytest.raises(ValueError):
        parse_xmp(xmp_no_version)
