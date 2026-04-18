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


# ---------------------------------------------------------------------------
# Coverage: _LLMindHandler event handling and flush_pending
# ---------------------------------------------------------------------------

def test_handler_on_created_processes_file(tmp_path: Path) -> None:
    """_LLMindHandler.on_created should queue supported files."""
    from watchdog.events import FileCreatedEvent
    from llmind.watcher import _LLMindHandler

    calls: list[Path] = []
    handler = _LLMindHandler(lambda p: calls.append(p), frozenset({".jpg", ".jpeg"}), debounce_seconds=0.0)

    p = _jpeg_in(tmp_path, "new.jpg")
    event = FileCreatedEvent(str(p))
    handler.on_created(event)

    # debounce_seconds=0.0, so flush should process immediately
    import time
    time.sleep(0.01)
    handler.flush_pending()
    assert p in calls


def test_handler_on_modified_processes_file(tmp_path: Path) -> None:
    """_LLMindHandler.on_modified should queue supported files."""
    from watchdog.events import FileModifiedEvent
    from llmind.watcher import _LLMindHandler

    calls: list[Path] = []
    handler = _LLMindHandler(lambda p: calls.append(p), frozenset({".jpg", ".jpeg"}), debounce_seconds=0.0)

    p = _jpeg_in(tmp_path, "mod.jpg")
    event = FileModifiedEvent(str(p))
    handler.on_modified(event)

    import time
    time.sleep(0.01)
    handler.flush_pending()
    assert p in calls


def test_handler_skips_directory_events(tmp_path: Path) -> None:
    """_LLMindHandler should skip directory events."""
    from watchdog.events import FileCreatedEvent, FileModifiedEvent
    from llmind.watcher import _LLMindHandler

    calls: list[Path] = []
    handler = _LLMindHandler(lambda p: calls.append(p), frozenset({".jpg"}), debounce_seconds=0.0)

    # Simulate directory event (is_directory=True)
    created_event = FileCreatedEvent(str(tmp_path))
    created_event.is_directory = True
    modified_event = FileModifiedEvent(str(tmp_path))
    modified_event.is_directory = True

    handler.on_created(created_event)
    handler.on_modified(modified_event)
    handler.flush_pending()

    assert calls == []


def test_handler_skips_unsupported_extension(tmp_path: Path) -> None:
    """_LLMindHandler should not queue files with unsupported extensions."""
    from watchdog.events import FileCreatedEvent
    from llmind.watcher import _LLMindHandler

    exe = tmp_path / "bad.exe"
    exe.write_bytes(b"MZ\x00")

    calls: list[Path] = []
    handler = _LLMindHandler(lambda p: calls.append(p), frozenset({".jpg"}), debounce_seconds=0.0)
    handler.on_created(FileCreatedEvent(str(exe)))
    handler.flush_pending()

    assert calls == []


def test_run_watch_with_observer(tmp_path: Path) -> None:
    """run_watch starts and stops the Observer correctly via stop_event."""
    import threading

    calls: list[Path] = []
    stop = threading.Event()

    # Run in a background thread; set stop immediately so it exits the loop
    def _run():
        stop.set()
        run_watch(tmp_path, lambda p: calls.append(p), mode=WatchMode.NEW, stop_event=stop)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=5.0)
    assert not t.is_alive(), "run_watch should have exited"


from llmind.safety import is_safe_file


def test_watcher_accepts_audio_files(tmp_path):
    for name in ["a.mp3", "b.wav", "c.m4a"]:
        p = tmp_path / name
        p.write_bytes(b"\x00" * 64)
        assert is_safe_file(p) is True
