"""File watcher: monitors directories and enriches new/modified files."""
from __future__ import annotations

import threading
import time
from enum import Enum
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from llmind.reader import has_llmind_layer
from llmind.safety import is_safe_file


class WatchMode(str, Enum):
    NEW = "new"          # watch for new files only
    BACKFILL = "backfill"  # process existing files that lack LLMind XMP, then watch for new
    EXISTING = "existing"  # process ALL files in folder (including already-enriched), then watch


class _LLMindHandler(FileSystemEventHandler):
    def __init__(
        self,
        enrich_fn: Callable[[Path], None],
        extensions: frozenset[str],
        debounce_seconds: float,
    ) -> None:
        self.enrich_fn = enrich_fn
        self.extensions = extensions
        self.debounce_seconds = debounce_seconds
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def _should_process(self, path: Path) -> bool:
        return (
            path.suffix.lower() in self.extensions
            and is_safe_file(path)
        )

    def on_created(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            path = Path(event.src_path)
            if self._should_process(path):
                with self._lock:
                    self._pending[str(path)] = time.monotonic()

    def on_modified(self, event) -> None:  # type: ignore[override]
        if not event.is_directory:
            path = Path(event.src_path)
            if self._should_process(path):
                with self._lock:
                    self._pending[str(path)] = time.monotonic()

    def flush_pending(self) -> None:
        """Process files whose debounce period has elapsed."""
        now = time.monotonic()
        with self._lock:
            ready = [p for p, t in self._pending.items() if now - t >= self.debounce_seconds]
            for p in ready:
                del self._pending[p]
        for p in ready:
            self.enrich_fn(Path(p))


def run_watch(
    directory: Path,
    enrich_fn: Callable[[Path], None],
    mode: WatchMode = WatchMode.NEW,
    extensions: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".pdf"}),
    debounce_seconds: float = 2.0,
    stop_event: threading.Event | None = None,
) -> None:
    """Watch directory for new/modified files and enrich them.

    stop_event: if provided, watching stops when event is set.
    """
    directory = Path(directory)

    # Backfill / existing pre-scan
    if mode in (WatchMode.BACKFILL, WatchMode.EXISTING):
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in extensions:
                continue
            if not is_safe_file(path):
                continue
            if mode == WatchMode.BACKFILL and has_llmind_layer(path):
                continue
            enrich_fn(path)

    handler = _LLMindHandler(enrich_fn, extensions, debounce_seconds)
    observer = Observer()
    observer.schedule(handler, str(directory), recursive=True)
    observer.start()

    try:
        while stop_event is None or not stop_event.is_set():
            time.sleep(0.1)
            handler.flush_pending()
    finally:
        observer.stop()
        observer.join()
