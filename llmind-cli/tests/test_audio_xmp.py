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


# Legacy XMP (no media_type, no segments, no duration) — pre-audio format.
# Must parse successfully and default media_type to "image".
LEGACY_XMP = '''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
    xmlns:llmind="https://llmind.org/ns/1.0/"
    llmind:version="1"
    llmind:format_version="1.0"
    llmind:generator="llmind-cli/0.1.0"
    llmind:generator_model="gpt-4o-mini"
    llmind:timestamp="2026-01-01T00:00:00Z"
    llmind:language="en"
    llmind:checksum="deadbeef"
    llmind:key_id=""
    llmind:signature=""
    llmind:layer_count="1"
    llmind:immutable="true"
    >
      <llmind:description>A photo.</llmind:description>
      <llmind:text>some text</llmind:text>
      <llmind:structure>{}</llmind:structure>
      <llmind:history>[{"version":1,"timestamp":"2026-01-01T00:00:00Z","generator":"llmind-cli/0.1.0","generator_model":"gpt-4o-mini","checksum":"deadbeef","language":"en","description":"A photo.","text":"some text","structure":{},"key_id":"","signature":null}]</llmind:history>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''


def test_legacy_xmp_parses_with_image_defaults():
    meta = parse_xmp(LEGACY_XMP)
    assert meta.current.media_type == "image"
    assert meta.current.segments is None
    assert meta.current.duration_seconds is None
