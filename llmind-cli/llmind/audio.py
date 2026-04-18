# llmind-cli/llmind/audio.py
"""Audio transcription providers and dispatch."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llmind.models import Segment


class UnsupportedProviderError(ValueError):
    """Raised when a provider does not support audio input."""


@dataclass(frozen=True)
class AudioExtraction:
    text: str
    summary: str
    segments: tuple[Segment, ...]
    language: str
    duration_seconds: float


AUDIO_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "whisper-1",
    "gemini": "gemini-2.5-flash",
    "whisper_local": "base",
}

AUDIO_SUMMARIZER_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",   # same model handles both transcript + summary
    "whisper_local": "",            # extractive summary, no model
}
