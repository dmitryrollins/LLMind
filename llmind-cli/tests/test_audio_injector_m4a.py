import shutil
import struct
from pathlib import Path

from llmind.audio_injector import (
    _inject_m4a, _read_xmp_m4a, _remove_llmind_xmp_m4a,
    XMP_UUID,
)

FIXTURE = Path(__file__).parent / "fixtures" / "audio" / "silent.m4a"
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" '
    'llmind:version="1"/></rdf:RDF></x:xmpmeta>'
    '<?xpacket end="w"?>'
)


def _iter_boxes(data: bytes):
    """Yield (offset, atom_type, size, payload) for top-level MP4 boxes."""
    i = 0
    while i + 8 <= len(data):
        size = struct.unpack(">I", data[i:i + 4])[0]
        atom = data[i + 4:i + 8]
        if size == 1:
            size = struct.unpack(">Q", data[i + 8:i + 16])[0]
            payload = data[i + 16:i + size]
        elif size == 0:
            payload = data[i + 8:]
            yield i, atom, len(data) - i, payload
            break
        else:
            payload = data[i + 8:i + size]
        yield i, atom, size, payload
        i += size


def _mdat_payload(path: Path) -> bytes:
    for _, atom, _, payload in _iter_boxes(path.read_bytes()):
        if atom == b"mdat":
            return payload
    return b""


def test_inject_roundtrip(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    _inject_m4a(dst, SAMPLE_XMP)
    assert _read_xmp_m4a(dst) == SAMPLE_XMP


def test_inject_replaces_existing(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    _inject_m4a(dst, SAMPLE_XMP)
    updated = SAMPLE_XMP.replace('version="1"', 'version="2"')
    _inject_m4a(dst, updated)
    assert _read_xmp_m4a(dst) == updated
    uuid_count = 0
    for _, atom, _, payload in _iter_boxes(dst.read_bytes()):
        if atom == b"uuid" and payload[:16] == XMP_UUID:
            uuid_count += 1
    assert uuid_count == 1


def test_mdat_unchanged(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    before = _mdat_payload(dst)
    _inject_m4a(dst, SAMPLE_XMP)
    assert _mdat_payload(dst) == before


def test_remove_xmp(tmp_path):
    dst = tmp_path / "copy.m4a"
    shutil.copy(FIXTURE, dst)
    _inject_m4a(dst, SAMPLE_XMP)
    assert _remove_llmind_xmp_m4a(dst) is True
    assert _read_xmp_m4a(dst) is None
