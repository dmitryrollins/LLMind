"""Tests for llmind.injector — JPEG, PNG, and PDF XMP injection (Tasks 7 & 8)."""
from __future__ import annotations

from pathlib import Path

import pytest

from llmind.injector import inject, read_xmp_pdf, read_xmp_png, remove_llmind_xmp

XMP_NS = b"http://ns.adobe.com/xap/1.0/\x00"
SAMPLE_XMP = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" llmind:version="1"/></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
OTHER_XMP = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" xmlns:llmind="https://llmind.org/ns/1.0/" llmind:version="2"/></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'


def test_inject_jpeg_adds_xmp(jpeg_file: Path) -> None:
    """Injecting XMP into a JPEG places the XMP namespace bytes in the file."""
    inject(jpeg_file, SAMPLE_XMP)
    data = jpeg_file.read_bytes()
    assert XMP_NS in data


def test_inject_jpeg_idempotent(jpeg_file: Path) -> None:
    """Injecting twice with different XMP results in only one XMP APP1 block."""
    inject(jpeg_file, SAMPLE_XMP)
    inject(jpeg_file, OTHER_XMP)
    data = jpeg_file.read_bytes()
    assert data.count(XMP_NS) == 1


def test_inject_jpeg_preserves_soi(jpeg_file: Path) -> None:
    """First two bytes remain FF D8 (JPEG SOI) after injection."""
    inject(jpeg_file, SAMPLE_XMP)
    data = jpeg_file.read_bytes()
    assert data[:2] == b"\xFF\xD8"


def test_inject_jpeg_position(jpeg_file: Path) -> None:
    """XMP APP1 block (FF E1) starts at byte offset 2, right after SOI.
    Bytes 4-5 are the 2-byte length field; namespace starts at byte 6."""
    inject(jpeg_file, SAMPLE_XMP)
    data = jpeg_file.read_bytes()
    assert data[2:4] == b"\xFF\xE1"
    assert data[6:6 + len(XMP_NS)] == XMP_NS


def test_remove_jpeg_xmp_removes_block(jpeg_file: Path) -> None:
    """After inject then remove, XMP namespace bytes are absent from the file."""
    inject(jpeg_file, SAMPLE_XMP)
    remove_llmind_xmp(jpeg_file)
    data = jpeg_file.read_bytes()
    assert XMP_NS not in data


def test_remove_jpeg_xmp_preserves_soi(jpeg_file: Path) -> None:
    """After remove, the first two bytes are still FF D8."""
    inject(jpeg_file, SAMPLE_XMP)
    remove_llmind_xmp(jpeg_file)
    data = jpeg_file.read_bytes()
    assert data[:2] == b"\xFF\xD8"


def test_inject_unsupported_extension_raises(tmp_path: Path) -> None:
    """inject() raises ValueError for truly unsupported extensions."""
    f = tmp_path / "test.bmp"
    f.write_bytes(b"fake")
    with pytest.raises(ValueError, match="Unsupported"):
        inject(f, SAMPLE_XMP)


def test_remove_unsupported_extension_raises(tmp_path: Path) -> None:
    """remove_llmind_xmp() raises ValueError for truly unsupported extensions."""
    f = tmp_path / "test.tiff"
    f.write_bytes(b"fake")
    with pytest.raises(ValueError, match="Unsupported"):
        remove_llmind_xmp(f)


# ── PNG tests ────────────────────────────────────────────────────────────────

PNG_ITXT_KEYWORD = b"XML:com.adobe.xmp"


def test_inject_png_adds_xmp(png_file: Path) -> None:
    """Injecting XMP into a PNG places the iTXt keyword bytes in the file."""
    inject(png_file, SAMPLE_XMP)
    data = png_file.read_bytes()
    assert PNG_ITXT_KEYWORD in data


def test_inject_png_idempotent(png_file: Path) -> None:
    """Injecting twice results in only one LLMind iTXt chunk."""
    inject(png_file, SAMPLE_XMP)
    inject(png_file, OTHER_XMP)
    data = png_file.read_bytes()
    assert data.count(PNG_ITXT_KEYWORD) == 1


def test_inject_png_roundtrip(png_file: Path) -> None:
    """Injected XMP can be read back unchanged via read_xmp_png."""
    inject(png_file, SAMPLE_XMP)
    result = read_xmp_png(png_file)
    assert result == SAMPLE_XMP


def test_remove_png_xmp_removes_block(png_file: Path) -> None:
    """After inject then remove, read_xmp_png returns None."""
    inject(png_file, SAMPLE_XMP)
    remove_llmind_xmp(png_file)
    assert read_xmp_png(png_file) is None


# ── PDF tests ────────────────────────────────────────────────────────────────

def test_inject_pdf_roundtrip(pdf_file: Path) -> None:
    """Injected XMP can be read back from PDF and contains the LLMind namespace."""
    inject(pdf_file, SAMPLE_XMP)
    result = read_xmp_pdf(pdf_file)
    assert result is not None
    assert "https://llmind.org/ns/1.0/" in result
    assert 'llmind:version="1"' in result


def test_remove_pdf_xmp(pdf_file: Path) -> None:
    """After inject then remove, read_xmp_pdf returns None."""
    inject(pdf_file, SAMPLE_XMP)
    remove_llmind_xmp(pdf_file)
    assert read_xmp_pdf(pdf_file) is None
