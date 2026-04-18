"""High-level file reader: extracts and parses LLMind XMP metadata.

Dispatches to format-specific injector functions.
Task 7: JPEG only. PNG and PDF added in Task 8.
"""
from __future__ import annotations

from pathlib import Path

from llmind.audio_injector import read_xmp_audio
from llmind.injector import read_xmp_jpeg, read_xmp_pdf, read_xmp_png
from llmind.models import LLMindMeta
from llmind.safety import is_audio_file
from llmind.xmp import parse_xmp

_LLMIND_MARKER = "https://llmind.org/ns/1.0/"


def _read_raw_xmp(path: Path) -> str | None:
    """Return raw XMP string for any supported format, or None."""
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return read_xmp_jpeg(path)
    if suffix == ".png":
        return read_xmp_png(path)
    if suffix == ".pdf":
        return read_xmp_pdf(path)
    if is_audio_file(path):
        return read_xmp_audio(path)
    raise ValueError(f"Unsupported format: {path.suffix}")


def read(path: Path) -> LLMindMeta | None:
    """Parse and return LLMind metadata, or None if no LLMind layer present."""
    xmp = _read_raw_xmp(path)
    if xmp is None or _LLMIND_MARKER not in xmp:
        return None
    return parse_xmp(xmp)


def has_llmind_layer(path: Path) -> bool:
    """Return True if the file contains a LLMind XMP layer."""
    xmp = _read_raw_xmp(path)
    return xmp is not None and _LLMIND_MARKER in xmp


def is_fresh(path: Path, checksum: str) -> bool:
    """Return True if the stored LLMind checksum matches the given checksum."""
    meta = read(path)
    if meta is None:
        return False
    return meta.current.checksum == checksum
