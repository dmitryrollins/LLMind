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
