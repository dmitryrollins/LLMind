"""Pure-bytes XMP injection/removal for image files.

Knows nothing about LLMind semantics — just embeds/extracts XMP strings.
Task 7: JPEG only. PNG and PDF added in Task 8.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

from llmind.safety import is_audio_file

_XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
_LLMIND_MARKER = b"https://llmind.org/ns/1.0/"

# ── JPEG ────────────────────────────────────────────────────────────────────

def _build_app1(xmp_string: str) -> bytes:
    xmp_bytes = xmp_string.encode("utf-8")
    # Length field = 2 (length itself) + len(namespace) + len(xmp)
    length = 2 + len(_XMP_NS) + len(xmp_bytes)
    return b"\xff\xe1" + struct.pack(">H", length) + _XMP_NS + xmp_bytes


def _remove_llmind_app1(data: bytes) -> bytes:
    """Return JPEG bytes with any LLMind XMP APP1 block removed."""
    result = bytearray(data[:2])  # SOI
    i = 2
    while i < len(data) - 1:
        if data[i] != 0xFF:
            result += data[i:]
            break
        marker = data[i + 1]
        i += 2
        # Markers with no payload
        if marker == 0xD9:
            result += b"\xff\xd9" + data[i:]
            break
        if 0xD0 <= marker <= 0xD7:
            result += bytes([0xFF, marker])
            continue
        # Read length field (includes 2 bytes for itself)
        if i + 2 > len(data):
            break
        length = struct.unpack(">H", data[i : i + 2])[0]
        segment = data[i : i + length]  # includes the 2-byte length field
        i += length
        # Identify LLMind XMP APP1 blocks and skip them
        if marker == 0xE1:
            payload = segment[2:]  # strip the 2-byte length from the segment
            if payload.startswith(_XMP_NS) and _LLMIND_MARKER in payload:
                continue  # drop this block
        result += bytes([0xFF, marker]) + segment
    return bytes(result)


def _inject_jpeg(path: Path, xmp_string: str) -> None:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"Not a valid JPEG: {path}")
    data = _remove_llmind_app1(data)
    app1 = _build_app1(xmp_string)
    path.write_bytes(data[:2] + app1 + data[2:])


def _remove_llmind_xmp_jpeg(path: Path) -> bool:
    data = path.read_bytes()
    new_data = _remove_llmind_app1(data)
    if new_data == data:
        return False
    path.write_bytes(new_data)
    return True


def read_xmp_jpeg(path: Path) -> str | None:
    """Read and return the XMP string from a JPEG, or None if absent."""
    data = path.read_bytes()
    i = 2  # skip SOI
    while i < len(data) - 1:
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        i += 2
        if marker == 0xD9:
            break
        if 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > len(data):
            break
        length = struct.unpack(">H", data[i : i + 2])[0]
        payload = data[i + 2 : i + length]  # skip 2-byte length field
        i += length
        if marker == 0xE1 and payload.startswith(_XMP_NS):
            return payload[len(_XMP_NS) :].decode("utf-8")
    return None


# ── PNG ─────────────────────────────────────────────────────────────────────

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_ITXT_KEYWORD = b"XML:com.adobe.xmp"


def _build_itxt_chunk(xmp_string: str) -> bytes:
    """Build a PNG iTXt chunk containing XMP data."""
    xmp_bytes = xmp_string.encode("utf-8")
    chunk_data = (
        _PNG_ITXT_KEYWORD + b"\x00"  # keyword + null terminator
        + b"\x00"                     # compression flag (0 = uncompressed)
        + b"\x00"                     # compression method
        + b"\x00"                     # language tag (empty)
        + b"\x00"                     # translated keyword (empty)
        + xmp_bytes                   # text (no null terminator)
    )
    chunk_type = b"iTXt"
    crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
    return struct.pack(">I", len(chunk_data)) + chunk_type + chunk_data + struct.pack(">I", crc)


def _walk_png_chunks(data: bytes) -> list[tuple[int, bytes, bytes, bytes]]:
    """Walk PNG chunks, returning list of (offset, type, chunk_data, crc_bytes)."""
    chunks = []
    i = 8  # skip signature
    while i < len(data):
        if i + 8 > len(data):
            break
        length = struct.unpack(">I", data[i : i + 4])[0]
        chunk_type = data[i + 4 : i + 8]
        chunk_data = data[i + 8 : i + 8 + length]
        crc_bytes = data[i + 8 + length : i + 12 + length]
        chunks.append((i, chunk_type, chunk_data, crc_bytes))
        i += 12 + length
    return chunks


def _is_llmind_itxt(chunk_type: bytes, chunk_data: bytes) -> bool:
    """Return True if this chunk is a LLMind XMP iTXt chunk."""
    if chunk_type != b"iTXt":
        return False
    if not chunk_data.startswith(_PNG_ITXT_KEYWORD):
        return False
    return _LLMIND_MARKER in chunk_data


def _remove_llmind_png_chunks(data: bytes) -> bytes:
    """Return PNG bytes with LLMind XMP iTXt chunks removed."""
    chunks = _walk_png_chunks(data)
    result = bytearray(_PNG_SIGNATURE)
    for _, chunk_type, chunk_data, crc_bytes in chunks:
        if _is_llmind_itxt(chunk_type, chunk_data):
            continue
        length = len(chunk_data)
        result += struct.pack(">I", length) + chunk_type + chunk_data + crc_bytes
    return bytes(result)


def _inject_png(path: Path, xmp_string: str) -> None:
    data = path.read_bytes()
    if data[:8] != _PNG_SIGNATURE:
        raise ValueError(f"Not a valid PNG: {path}")
    data = _remove_llmind_png_chunks(data)
    chunks = _walk_png_chunks(data)
    if not chunks:
        raise ValueError(f"PNG has no chunks: {path}")
    # Find IHDR chunk (should be the first chunk)
    ihdr_offset = None
    ihdr_end = None
    for offset, chunk_type, chunk_data, crc_bytes in chunks:
        if chunk_type == b"IHDR":
            ihdr_end = offset + 12 + len(chunk_data)
            ihdr_offset = offset
            break
    if ihdr_end is None:
        raise ValueError(f"PNG has no IHDR chunk: {path}")
    itxt_chunk = _build_itxt_chunk(xmp_string)
    path.write_bytes(data[:ihdr_end] + itxt_chunk + data[ihdr_end:])


def _remove_llmind_xmp_png(path: Path) -> bool:
    data = path.read_bytes()
    new_data = _remove_llmind_png_chunks(data)
    if new_data == data:
        return False
    path.write_bytes(new_data)
    return True


def read_xmp_png(path: Path) -> str | None:
    """Read and return the XMP string from a PNG, or None if absent."""
    data = path.read_bytes()
    if data[:8] != _PNG_SIGNATURE:
        return None
    chunks = _walk_png_chunks(data)
    for _, chunk_type, chunk_data, _ in chunks:
        if chunk_type != b"iTXt":
            continue
        if not chunk_data.startswith(_PNG_ITXT_KEYWORD + b"\x00"):
            continue
        # Skip: keyword\0 + compression_flag(1) + compression_method(1) + lang\0 + translated\0
        prefix = _PNG_ITXT_KEYWORD + b"\x00"
        rest = chunk_data[len(prefix):]
        # compression_flag + compression_method + language_tag\0 + translated_keyword\0
        # language tag and translated keyword are both empty, so we skip 4 bytes total
        text = rest[4:]  # skip flag(1) + method(1) + \0(1) + \0(1)
        return text.decode("utf-8")
    return None


# ── PDF ─────────────────────────────────────────────────────────────────────

def _inject_pdf(path: Path, xmp_string: str) -> None:
    import pikepdf
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        xmp_bytes = xmp_string.encode("utf-8")
        pdf.Root.Metadata = pdf.make_stream(xmp_bytes)
        pdf.Root.Metadata["/Type"] = pikepdf.Name("/Metadata")
        pdf.Root.Metadata["/Subtype"] = pikepdf.Name("/XML")
        pdf.save(path)


def _remove_llmind_xmp_pdf(path: Path) -> bool:
    import pikepdf
    with pikepdf.open(path, allow_overwriting_input=True) as pdf:
        if "/Metadata" not in pdf.Root:
            return False
        content = pdf.Root.Metadata.read_bytes().decode("utf-8", errors="replace")
        if "https://llmind.org/ns/1.0/" not in content:
            return False
        del pdf.Root["/Metadata"]
        pdf.save(path)
    return True


def read_xmp_pdf(path: Path) -> str | None:
    """Read and return the XMP string from a PDF, or None if absent."""
    import pikepdf
    with pikepdf.open(path) as pdf:
        if "/Metadata" not in pdf.Root:
            return None
        return pdf.Root.Metadata.read_bytes().decode("utf-8")


# ── Public dispatch ──────────────────────────────────────────────────────────

def inject(path: Path, xmp_string: str) -> None:
    """Inject XMP into a file. Raises ValueError for unsupported formats."""
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        _inject_jpeg(path, xmp_string)
    elif suffix == ".png":
        _inject_png(path, xmp_string)
    elif suffix == ".pdf":
        _inject_pdf(path, xmp_string)
    elif is_audio_file(path):
        from llmind.audio_injector import inject_audio
        inject_audio(path, xmp_string)
    else:
        raise ValueError(f"Unsupported format for inject: {path.suffix}")


def remove_llmind_xmp(path: Path) -> bool:
    """Remove LLMind XMP from a file. Returns True if removed, False if absent."""
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return _remove_llmind_xmp_jpeg(path)
    elif suffix == ".png":
        return _remove_llmind_xmp_png(path)
    elif suffix == ".pdf":
        return _remove_llmind_xmp_pdf(path)
    elif is_audio_file(path):
        from llmind.audio_injector import remove_llmind_xmp_audio
        return remove_llmind_xmp_audio(path)
    else:
        raise ValueError(f"Unsupported format for remove_llmind_xmp: {path.suffix}")
