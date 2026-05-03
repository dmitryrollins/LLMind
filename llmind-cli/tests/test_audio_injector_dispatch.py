import shutil
from pathlib import Path

import pytest

from llmind.audio_injector import (
    inject_audio, read_xmp_audio, remove_llmind_xmp_audio,
)

FIXTURES = Path(__file__).parent / "fixtures" / "audio"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


@pytest.mark.parametrize("name", ["silent.mp3", "silent.wav", "silent.m4a"])
def test_roundtrip(tmp_path, name):
    dst = tmp_path / name
    shutil.copy(FIXTURES / name, dst)
    inject_audio(dst, SAMPLE_XMP)
    assert read_xmp_audio(dst) == SAMPLE_XMP
    assert remove_llmind_xmp_audio(dst) is True
    assert read_xmp_audio(dst) is None


def test_unsupported_format(tmp_path):
    dst = tmp_path / "song.flac"
    dst.write_bytes(b"fLaC")
    with pytest.raises(ValueError, match="Unsupported"):
        inject_audio(dst, SAMPLE_XMP)
