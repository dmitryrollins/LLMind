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
