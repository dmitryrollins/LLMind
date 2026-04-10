"""Tests for llmind.watcher."""
from __future__ import annotations

import io
import threading
from pathlib import Path

import pytest
from PIL import Image

from llmind.injector import inject
from llmind.models import Layer
from llmind.watcher import WatchMode, run_watch
from llmind.xmp import build_xmp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(0, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def _jpeg_in(tmp_path: Path, name: str = "test.jpg") -> Path:
    p = tmp_path / name
    p.write_bytes(_make_jpeg_bytes())
    return p


def _sample_layer(path: Path) -> Layer:
    return Layer(
        version=1,
        timestamp="2026-04-10T00:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum="a" * 64,
        language="en",
        description="Test",
        text="Hello",
        structure={},
        key_id="",
        signature=None,
    )


def _stopped_event() -> threading.Event:
    e = threading.Event()
    e.set()
    return e


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_watch_mode_enum_values() -> None:
    assert WatchMode.NEW == "new"
    assert WatchMode.BACKFILL == "backfill"
    assert WatchMode.EXISTING == "existing"


def test_run_watch_backfill_processes_existing(tmp_path: Path) -> None:
    f1 = _jpeg_in(tmp_path, "a.jpg")
    f2 = _jpeg_in(tmp_path, "b.jpg")

    calls: list[Path] = []
    run_watch(tmp_path, lambda p: calls.append(p), mode=WatchMode.BACKFILL, stop_event=_stopped_event())

    assert f1 in calls
    assert f2 in calls


def test_run_watch_existing_processes_all(tmp_path: Path) -> None:
    f1 = _jpeg_in(tmp_path, "a.jpg")
    f2 = _jpeg_in(tmp_path, "b.jpg")

    calls: list[Path] = []
    run_watch(tmp_path, lambda p: calls.append(p), mode=WatchMode.EXISTING, stop_event=_stopped_event())

    assert f1 in calls
    assert f2 in calls


def test_run_watch_new_skips_existing(tmp_path: Path) -> None:
    f1 = _jpeg_in(tmp_path, "a.jpg")
    f2 = _jpeg_in(tmp_path, "b.jpg")

    calls: list[Path] = []
    run_watch(tmp_path, lambda p: calls.append(p), mode=WatchMode.NEW, stop_event=_stopped_event())

    assert f1 not in calls
    assert f2 not in calls


def test_run_watch_skips_unsafe_files(tmp_path: Path) -> None:
    exe_file = tmp_path / "malware.exe"
    exe_file.write_bytes(b"MZ\x00\x00")

    calls: list[Path] = []
    run_watch(tmp_path, lambda p: calls.append(p), mode=WatchMode.EXISTING, stop_event=_stopped_event())

    assert exe_file not in calls


def test_run_watch_backfill_skips_enriched(tmp_path: Path) -> None:
    """BACKFILL should skip a file that already has a LLMind XMP layer."""
    p = _jpeg_in(tmp_path, "enriched.jpg")
    layer = _sample_layer(p)
    inject(p, build_xmp([layer]))

    calls: list[Path] = []
    run_watch(tmp_path, lambda path: calls.append(path), mode=WatchMode.BACKFILL, stop_event=_stopped_event())

    assert p not in calls
