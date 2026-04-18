"""Format-aware XMP injection for audio files (MP3/WAV/M4A).

Follows Adobe XMP spec slots:
- MP3  → ID3v2 PRIV frame, owner "XMP"
- WAV  → RIFF "_PMX" top-level chunk
- M4A  → top-level "uuid" atom, UUID BE7ACFCB-97A9-42E8-9C71-999491E3AFAC
"""
from __future__ import annotations

from pathlib import Path

_LLMIND_MARKER = b"https://llmind.org/ns/1.0/"

# ── MP3 ─────────────────────────────────────────────────────────────────────

def _inject_mp3(path: Path, xmp_string: str) -> None:
    from mutagen.id3 import ID3, ID3NoHeaderError, PRIV
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    # Remove any prior LLMind PRIV:XMP frames (defensive, allows replace).
    priv_frames = [f for f in tags.getall("PRIV") if f.owner == "XMP"]
    for f in priv_frames:
        tags.delall("PRIV:XMP")
        break
    tags.add(PRIV(owner="XMP", data=xmp_string.encode("utf-8")))
    tags.save(path)


def _read_xmp_mp3(path: Path) -> str | None:
    from mutagen.id3 import ID3, ID3NoHeaderError
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return None
    for frame in tags.getall("PRIV"):
        if frame.owner == "XMP":
            data = frame.data
            if _LLMIND_MARKER in data:
                return data.decode("utf-8")
    return None


def _remove_llmind_xmp_mp3(path: Path) -> bool:
    from mutagen.id3 import ID3, ID3NoHeaderError
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        return False
    priv_frames = [f for f in tags.getall("PRIV") if f.owner == "XMP"
                   and _LLMIND_MARKER in f.data]
    if not priv_frames:
        return False
    tags.delall("PRIV:XMP")
    tags.save(path)
    return True


import struct as _struct

# ── WAV / RIFF ──────────────────────────────────────────────────────────────

_PMX_ID = b"_PMX"


def _iter_riff_chunks(data: bytes):
    """Yield (offset, chunk_id, size, payload)."""
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Not a RIFF/WAVE file")
    i = 12
    while i + 8 <= len(data):
        chunk_id = data[i:i + 4]
        size = _struct.unpack("<I", data[i + 4:i + 8])[0]
        payload = data[i + 8:i + 8 + size]
        yield i, chunk_id, size, payload
        i += 8 + size + (size & 1)


def _strip_pmx_chunks(data: bytes) -> bytes:
    out = bytearray(data[:12])  # RIFF header preserved
    for _, cid, size, payload in _iter_riff_chunks(data):
        if cid == _PMX_ID and _LLMIND_MARKER in payload:
            continue
        out += cid + _struct.pack("<I", size) + payload
        if size & 1:
            out += b"\x00"
    new_riff_size = len(out) - 8
    out[4:8] = _struct.pack("<I", new_riff_size)
    return bytes(out)


def _inject_wav(path: Path, xmp_string: str) -> None:
    data = path.read_bytes()
    data = _strip_pmx_chunks(data)
    payload = xmp_string.encode("utf-8")
    chunk = _PMX_ID + _struct.pack("<I", len(payload)) + payload
    if len(payload) & 1:
        chunk += b"\x00"
    out = bytearray(data + chunk)
    new_riff_size = len(out) - 8
    out[4:8] = _struct.pack("<I", new_riff_size)
    path.write_bytes(bytes(out))


def _read_xmp_wav(path: Path) -> str | None:
    data = path.read_bytes()
    try:
        chunks = list(_iter_riff_chunks(data))
    except ValueError:
        return None
    for _, cid, _, payload in chunks:
        if cid == _PMX_ID and _LLMIND_MARKER in payload:
            return payload.decode("utf-8")
    return None


def _remove_llmind_xmp_wav(path: Path) -> bool:
    data = path.read_bytes()
    new_data = _strip_pmx_chunks(data)
    if new_data == data:
        return False
    path.write_bytes(new_data)
    return True


# ── M4A / MP4 ───────────────────────────────────────────────────────────────

XMP_UUID = bytes.fromhex("BE7ACFCB97A942E89C71999491E3AFAC")


def _iter_mp4_boxes(data: bytes):
    """Yield (offset, atom_type, full_size, payload, header_size) for top-level MP4 boxes."""
    i = 0
    while i + 8 <= len(data):
        size = _struct.unpack(">I", data[i:i + 4])[0]
        atom = data[i + 4:i + 8]
        header = 8
        if size == 1:
            if i + 16 > len(data):
                break
            size = _struct.unpack(">Q", data[i + 8:i + 16])[0]
            header = 16
        elif size == 0:
            size = len(data) - i
        if size < header or i + size > len(data):
            break
        payload = data[i + header:i + size]
        yield i, atom, size, payload, header
        i += size


def _build_uuid_box(uuid_bytes: bytes, payload: bytes) -> bytes:
    """Build a top-level MP4 uuid box: [size:4][type:'uuid'][uuid:16][payload]."""
    assert len(uuid_bytes) == 16
    total = 8 + 16 + len(payload)
    return _struct.pack(">I", total) + b"uuid" + uuid_bytes + payload


def _strip_llmind_uuid_boxes(data: bytes) -> bytes:
    out = bytearray()
    for _, atom, size, payload, header in _iter_mp4_boxes(data):
        if atom == b"uuid" and payload[:16] == XMP_UUID and _LLMIND_MARKER in payload[16:]:
            continue
        box_size = header + len(payload)
        if header == 16:
            out += _struct.pack(">I", 1) + atom + _struct.pack(">Q", box_size) + payload
        else:
            out += _struct.pack(">I", box_size) + atom + payload
    return bytes(out)


def _inject_m4a(path: Path, xmp_string: str) -> None:
    data = path.read_bytes()
    data = _strip_llmind_uuid_boxes(data)
    xmp_bytes = xmp_string.encode("utf-8")
    box = _build_uuid_box(XMP_UUID, xmp_bytes)
    # Append at end — top level, safe for QuickTime/iTunes parsers.
    path.write_bytes(data + box)


def _read_xmp_m4a(path: Path) -> str | None:
    data = path.read_bytes()
    for _, atom, _size, payload, _header in _iter_mp4_boxes(data):
        if atom == b"uuid" and payload[:16] == XMP_UUID:
            xmp = payload[16:]
            if _LLMIND_MARKER in xmp:
                return xmp.decode("utf-8")
    return None


def _remove_llmind_xmp_m4a(path: Path) -> bool:
    data = path.read_bytes()
    new_data = _strip_llmind_uuid_boxes(data)
    if new_data == data:
        return False
    path.write_bytes(new_data)
    return True


# ── Public dispatch ─────────────────────────────────────────────────────────

def inject_audio(path: Path, xmp_string: str) -> None:
    """Inject XMP into an audio file, replacing any prior LLMind XMP packet."""
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        _inject_mp3(path, xmp_string)
    elif suffix == ".wav":
        _inject_wav(path, xmp_string)
    elif suffix == ".m4a":
        _inject_m4a(path, xmp_string)
    else:
        raise ValueError(f"Unsupported audio format: {suffix}")


def read_xmp_audio(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return _read_xmp_mp3(path)
    if suffix == ".wav":
        return _read_xmp_wav(path)
    if suffix == ".m4a":
        return _read_xmp_m4a(path)
    raise ValueError(f"Unsupported audio format: {suffix}")


def remove_llmind_xmp_audio(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".mp3":
        return _remove_llmind_xmp_mp3(path)
    if suffix == ".wav":
        return _remove_llmind_xmp_wav(path)
    if suffix == ".m4a":
        return _remove_llmind_xmp_m4a(path)
    raise ValueError(f"Unsupported audio format: {suffix}")
