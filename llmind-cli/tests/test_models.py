import pytest
from llmind.models import ExtractionResult, KeyFile, Layer, LLMindMeta


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
    with pytest.raises(Exception):  # FrozenInstanceError
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
