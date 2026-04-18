"""Generate deterministic silent audio fixtures for tests.

Run once; commit the outputs. Requires ffmpeg on PATH.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).parent


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True)


def generate_wav(out: Path) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono",
        "-t", "0.25", "-c:a", "pcm_s16le", str(out),
    ])


def generate_mp3(out: Path) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
        "-t", "0.5", "-b:a", "32k", "-c:a", "libmp3lame", str(out),
    ])


def generate_m4a(out: Path) -> None:
    _run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
        "-t", "0.5", "-b:a", "32k", "-c:a", "aac", str(out),
    ])


if __name__ == "__main__":
    generate_wav(HERE / "silent.wav")
    generate_mp3(HERE / "silent.mp3")
    generate_m4a(HERE / "silent.m4a")
    print("Fixtures written to", HERE)
