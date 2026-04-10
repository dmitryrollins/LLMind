"""Pure-bytes XMP injection/removal for image files.

Knows nothing about LLMind semantics — just embeds/extracts XMP strings.
Task 7: JPEG only. PNG and PDF added in Task 8.
"""
from __future__ import annotations

import struct
from pathlib import Path

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


# ── Public dispatch ──────────────────────────────────────────────────────────

def inject(path: Path, xmp_string: str) -> None:
    """Inject XMP into a file. Raises ValueError for unsupported formats."""
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        _inject_jpeg(path, xmp_string)
    else:
        raise ValueError(f"Unsupported format for inject: {path.suffix}")


def remove_llmind_xmp(path: Path) -> bool:
    """Remove LLMind XMP from a file. Returns True if removed, False if absent."""
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return _remove_llmind_xmp_jpeg(path)
    else:
        raise ValueError(f"Unsupported format for remove_llmind_xmp: {path.suffix}")
