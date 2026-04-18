# llmind-cli/tests/test_audio_signing.py
import shutil
from pathlib import Path
from unittest.mock import patch

from llmind.audio import AudioExtraction
from llmind.crypto import sign_layer, verify_signature
from llmind.enricher import enrich
from llmind.models import Layer, Segment
from llmind.reader import read
from llmind.verifier import verify
from llmind.xmp import layer_to_dict

FIX = Path(__file__).parent / "fixtures" / "audio"
KEY = "1" * 64


def _audio_extraction() -> AudioExtraction:
    return AudioExtraction(
        text="hi", summary="greeting",
        segments=(Segment(0.0, 1.0, "hi"),),
        language="en", duration_seconds=1.0,
    )


def test_audio_layer_signature_roundtrip(tmp_path):
    src = tmp_path / "memo.mp3"
    shutil.copy(FIX / "silent.mp3", src)
    with patch("llmind.enricher.query_audio", return_value=_audio_extraction()):
        result = enrich(src, provider="openai", creation_key=KEY)
    assert result.success
    out = src.with_name("memo.llmind.mp3")
    vr = verify(out, creation_key=KEY)
    assert vr.has_layer
    assert vr.signature_valid is True


def test_existing_image_signature_still_valid():
    """Adding audio fields to layer_to_dict must not break legacy image signatures."""
    # Legacy image layer (no audio fields) — simulates pre-audio signing.
    image_layer = Layer(
        version=1, timestamp="2026-01-01T00:00:00Z",
        generator="llmind-cli/0.1.0", generator_model="gpt-4o-mini",
        checksum="d" * 64, language="en",
        description="A photo.", text="some text",
        structure={"type": "photo"}, key_id="",
    )
    payload = layer_to_dict(image_layer, include_signature=False)
    # Audio-only keys must be absent for image layers.
    assert "segments" not in payload
    assert "duration_seconds" not in payload
    assert "media_type" not in payload
    sig = sign_layer(KEY, payload)
    assert verify_signature(KEY, payload, sig) is True
