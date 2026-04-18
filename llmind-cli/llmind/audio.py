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


def _get_openai_client():
    from openai import OpenAI
    return OpenAI()


def _query_openai(path: Path, model: str, summarizer: str) -> AudioExtraction:
    client = _get_openai_client()
    with open(path, "rb") as fh:
        resp = client.audio.transcriptions.create(
            model=model,
            file=fh,
            response_format="verbose_json",
        )
    segments = tuple(
        Segment(start=float(s.start), end=float(s.end), text=str(s.text).strip())
        for s in (resp.segments or [])
    )
    transcript = str(resp.text or "").strip()
    summary_resp = client.chat.completions.create(
        model=summarizer,
        messages=[
            {"role": "system", "content": "Summarize the following transcript in 1-2 sentences."},
            {"role": "user", "content": transcript or "(empty transcript)"},
        ],
    )
    summary = str(summary_resp.choices[0].message.content or "").strip()
    return AudioExtraction(
        text=transcript,
        summary=summary,
        segments=segments,
        language=str(resp.language or "en"),
        duration_seconds=float(resp.duration or 0.0),
    )


import json as _json


_GEMINI_PROMPT = (
    "Transcribe this audio. Return ONLY a JSON object with keys: "
    '"transcript" (full text), "language" (BCP-47 code), '
    '"duration" (seconds, float), '
    '"summary" (1-2 sentence description), '
    '"segments" (list of {start, end, text}).'
)


def _get_gemini_client():
    from google import genai
    return genai.Client()


def _query_gemini(path: Path, model: str) -> AudioExtraction:
    client = _get_gemini_client()
    uploaded = client.files.upload(file=str(path))
    response = client.models.generate_content(
        model=model,
        contents=[_GEMINI_PROMPT, uploaded],
    )
    raw = (response.text or "").strip()
    if raw.startswith("```"):
        raw = raw[raw.index("\n") + 1:]
    if raw.endswith("```"):
        raw = raw[:raw.rindex("```")].strip()
    data = _json.loads(raw)
    segments = tuple(
        Segment(start=float(s["start"]), end=float(s["end"]),
                text=str(s["text"]).strip())
        for s in data.get("segments", [])
    )
    return AudioExtraction(
        text=str(data.get("transcript", "")).strip(),
        summary=str(data.get("summary", "")).strip(),
        segments=segments,
        language=str(data.get("language", "en")),
        duration_seconds=float(data.get("duration", 0.0)),
    )


import re as _re


def _extractive_summary(text: str) -> str:
    """Return first sentence + longest sentence (deduped) as a 2-line summary."""
    text = text.strip()
    if not text:
        return ""
    sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= 1:
        return sentences[0] if sentences else ""
    first = sentences[0]
    longest = max(sentences[1:], key=len)
    if longest == first:
        return first
    return f"{first} {longest}"


def _load_whisper_local(model_size: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise UnsupportedProviderError(
            "Install `faster-whisper` to use the whisper_local provider."
        ) from exc
    return WhisperModel(model_size, compute_type="int8")


def _query_whisper_local(path: Path, model: str) -> AudioExtraction:
    whisper = _load_whisper_local(model or "base")
    segments_iter, info = whisper.transcribe(str(path))
    segments: list[Segment] = []
    parts: list[str] = []
    for s in segments_iter:
        text = str(s.text).strip()
        segments.append(Segment(start=float(s.start), end=float(s.end), text=text))
        parts.append(text)
    transcript = "\n".join(parts)
    return AudioExtraction(
        text=transcript,
        summary=_extractive_summary(transcript.replace("\n", " ")),
        segments=tuple(segments),
        language=str(info.language or "en"),
        duration_seconds=float(info.duration or 0.0),
    )


_UNSUPPORTED = {"anthropic", "ollama"}


def query_audio(
    path: Path,
    provider: str,
    model: str | None = None,
) -> AudioExtraction:
    """Dispatch audio transcription to the requested provider.

    Supported: openai, gemini, whisper_local.
    Raises UnsupportedProviderError for anthropic, ollama, or unknown providers.
    """
    if provider in _UNSUPPORTED:
        raise UnsupportedProviderError(
            f"Provider {provider!r} does not support audio. "
            f"Supported: openai, gemini, whisper_local."
        )
    if provider not in AUDIO_PROVIDER_DEFAULTS:
        raise UnsupportedProviderError(
            f"Unknown audio provider {provider!r}. "
            f"Supported: openai, gemini, whisper_local."
        )
    resolved_model = model or AUDIO_PROVIDER_DEFAULTS[provider]
    if provider == "openai":
        return _query_openai(
            path, model=resolved_model,
            summarizer=AUDIO_SUMMARIZER_DEFAULTS["openai"],
        )
    if provider == "gemini":
        return _query_gemini(path, model=resolved_model)
    if provider == "whisper_local":
        return _query_whisper_local(path, model=resolved_model)
    raise UnsupportedProviderError(f"Unreachable provider: {provider!r}")
