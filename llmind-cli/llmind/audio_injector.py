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
