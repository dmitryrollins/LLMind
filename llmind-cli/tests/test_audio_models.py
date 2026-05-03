from llmind.models import Layer, Segment


def test_segment_is_frozen():
    s = Segment(start=0.0, end=1.5, text="hello")
    assert s.start == 0.0
    assert s.end == 1.5
    assert s.text == "hello"


def test_layer_audio_fields_default_none():
    layer = Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="whisper-1",
        checksum="a" * 64, language="en", description="A voice memo.",
        text="hello world", structure={}, key_id="",
    )
    assert layer.segments is None
    assert layer.duration_seconds is None
    assert layer.media_type == "image"


def test_layer_audio_fields_populated():
    seg = (Segment(0.0, 1.0, "hi"),)
    layer = Layer(
        version=1, timestamp="2026-04-18T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="whisper-1",
        checksum="a" * 64, language="en", description="summary",
        text="hi", structure={}, key_id="",
        segments=seg, duration_seconds=1.0, media_type="audio",
    )
    assert layer.media_type == "audio"
    assert layer.segments == seg
    assert layer.duration_seconds == 1.0
