import shutil
from pathlib import Path

import pytest

from llmind.audio_injector import (
    _inject_mp3, _read_xmp_mp3, _remove_llmind_xmp_mp3,
)

FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "silent.mp3"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


def _mpeg_audio_bytes(path: Path) -> bytes:
    """Return MP3 audio frames only (skip any ID3v2 header)."""
    data = path.read_bytes()
    if data[:3] == b"ID3":
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) \
             | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        return data[10 + size:]
    return data


def test_inject_roundtrip(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    _inject_mp3(dst, SAMPLE_XMP)
    assert _read_xmp_mp3(dst) == SAMPLE_XMP


def test_inject_replaces_existing(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    _inject_mp3(dst, SAMPLE_XMP)
    updated = SAMPLE_XMP.replace('version="1"', 'version="2"')
    _inject_mp3(dst, updated)
    assert _read_xmp_mp3(dst) == updated
    # Ensure no duplicate PRIV:XMP frames remain
    from mutagen.id3 import ID3
    tags = ID3(dst)
    priv_frames = [f for f in tags.getall("PRIV") if f.owner == "XMP"]
    assert len(priv_frames) == 1


def test_audio_samples_unchanged_after_inject(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    original_samples = _mpeg_audio_bytes(dst)
    _inject_mp3(dst, SAMPLE_XMP)
    assert _mpeg_audio_bytes(dst) == original_samples


def test_remove_xmp(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    _inject_mp3(dst, SAMPLE_XMP)
    assert _remove_llmind_xmp_mp3(dst) is True
    assert _read_xmp_mp3(dst) is None


def test_remove_xmp_absent(tmp_path):
    dst = tmp_path / "copy.mp3"
    shutil.copy(FIXTURE, dst)
    assert _remove_llmind_xmp_mp3(dst) is False
