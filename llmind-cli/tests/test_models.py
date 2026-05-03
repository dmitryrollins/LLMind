import pytest
from dataclasses import FrozenInstanceError
from pathlib import Path
from llmind.models import ExtractionResult, KeyFile, Layer, LLMindMeta, EnrichResult, VerifyResult


def test_layer_instantiation():
    layer = Layer(
        version=1,
        timestamp="2026-04-09T12:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum="a" * 64,
        language="en",
        description="A test image",
        text="Hello world",
        structure={"type": "test", "regions": [], "figures": [], "tables": []},
        key_id="abcdef1234567890",
    )
    assert layer.version == 1
    assert layer.signature is None


def test_layer_is_frozen():
    layer = Layer(
        version=1, timestamp="t", generator="g", generator_model="m",
        checksum="c" * 64, language="en", description="d", text="t",
        structure={}, key_id="k",
    )
    with pytest.raises(FrozenInstanceError):
        layer.version = 2  # type: ignore


def test_key_file_has_default_note():
    kf = KeyFile(
        key_id="abc", creation_key="k" * 64,
        created="2026-04-09T12:00:00Z", file="photo.jpg",
    )
    assert "Not recoverable" in kf.note


def test_llmind_meta_current_is_last_layer():
    layer1 = Layer(version=1, timestamp="t", generator="g", generator_model="m",
                   checksum="c" * 64, language="en", description="d", text="t",
                   structure={}, key_id="k")
    layer2 = Layer(version=2, timestamp="t", generator="g", generator_model="m",
                   checksum="c" * 64, language="en", description="d2", text="t2",
                   structure={}, key_id="k")
    meta = LLMindMeta(layers=(layer1, layer2), current=layer2, layer_count=2, immutable=True)
    assert meta.current.version == 2


def test_llmind_meta_rejects_invalid_state():
    layer1 = Layer(version=1, timestamp="t", generator="g", generator_model="m",
                   checksum="c" * 64, language="en", description="d", text="t",
                   structure={}, key_id="k")
    layer2 = Layer(version=2, timestamp="t", generator="g", generator_model="m",
                   checksum="c" * 64, language="en", description="d", text="t",
                   structure={}, key_id="k")
    with pytest.raises(ValueError):
        LLMindMeta(layers=(layer1, layer2), current=layer1, layer_count=2, immutable=True)


def test_enrich_result_instantiation():
    er = EnrichResult(
        path=Path("/test.jpg"),
        success=True,
        skipped=False,
        version=1,
        regions=5,
        figures=2,
        tables=1,
        elapsed=0.5,
        error=None,
    )
    assert er.path.name == "test.jpg"
    assert er.success is True
    assert er.error is None


def test_verify_result_with_none_values():
    vr = VerifyResult(
        path=Path("/test.jpg"),
        has_layer=False,
        checksum_valid=False,
        signature_valid=None,
        layer_count=0,
        current_version=None,
    )
    assert vr.signature_valid is None
    assert vr.current_version is None
