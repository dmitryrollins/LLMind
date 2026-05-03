import shutil
import struct
from pathlib import Path

from llmind.audio_injector import (
    _inject_wav, _read_xmp_wav, _remove_llmind_xmp_wav,
)

FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "silent.wav"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


def _riff_chunks(data: bytes):
    """Yield (chunk_id, payload) tuples at the RIFF top level."""
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    i = 12
    while i < len(data):
        chunk_id = data[i:i + 4]
        size = struct.unpack("<I", data[i + 4:i + 8])[0]
        payload = data[i + 8:i + 8 + size]
        yield chunk_id, payload
        i += 8 + size + (size & 1)


def _wav_data_payload(path: Path) -> bytes:
    for cid, payload in _riff_chunks(path.read_bytes()):
        if cid == b"data":
            return payload
    return b""


def test_inject_roundtrip(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    assert _read_xmp_wav(dst) == SAMPLE_XMP


def test_riff_size_header_updated(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    data = dst.read_bytes()
    declared = struct.unpack("<I", data[4:8])[0]
    assert declared == len(data) - 8


def test_inject_replaces_existing(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    updated = SAMPLE_XMP.replace('version="1"', 'version="2"')
    _inject_wav(dst, updated)
    assert _read_xmp_wav(dst) == updated
    pmx_count = sum(1 for cid, _ in _riff_chunks(dst.read_bytes()) if cid == b"_PMX")
    assert pmx_count == 1


def test_data_chunk_unchanged(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    before = _wav_data_payload(dst)
    _inject_wav(dst, SAMPLE_XMP)
    assert _wav_data_payload(dst) == before


def test_remove_xmp(tmp_path):
    dst = tmp_path / "copy.wav"
    shutil.copy(FIXTURE, dst)
    _inject_wav(dst, SAMPLE_XMP)
    assert _remove_llmind_xmp_wav(dst) is True
    assert _read_xmp_wav(dst) is None
