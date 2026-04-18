from llmind.models import Layer, Segment
from llmind.xmp import build_xmp, parse_xmp, layer_to_dict


def _audio_layer(signature: str | None = None) -> Layer:
    return Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="whisper-1",
        checksum="a" * 64, language="en",
        description="A short voice memo greeting.",
        text="hello world", structure={}, key_id="",
        signature=signature,
        segments=(Segment(0.0, 1.0, "hello"), Segment(1.0, 2.0, "world")),
        duration_seconds=2.0,
        media_type="audio",
    )


def test_audio_layer_roundtrip():
    layer = _audio_layer()
    xmp = build_xmp([layer])
    meta = parse_xmp(xmp)
    assert meta.current.media_type == "audio"
    assert meta.current.duration_seconds == 2.0
    assert meta.current.segments == layer.segments


def test_layer_to_dict_includes_audio_fields_when_present():
    layer = _audio_layer()
    d = layer_to_dict(layer, include_signature=False)
    assert d["media_type"] == "audio"
    assert d["duration_seconds"] == 2.0
    assert d["segments"] == [
        {"start": 0.0, "end": 1.0, "text": "hello"},
        {"start": 1.0, "end": 2.0, "text": "world"},
    ]


def test_layer_to_dict_omits_audio_fields_when_absent():
    # Image layer: no audio fields serialized → signatures remain stable
    layer = Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="gpt-4o-mini",
        checksum="b" * 64, language="en",
        description="A photograph.", text="sign text",
        structure={"type": "photo"}, key_id="",
    )
    d = layer_to_dict(layer, include_signature=False)
    assert "media_type" not in d
    assert "duration_seconds" not in d
    assert "segments" not in d
