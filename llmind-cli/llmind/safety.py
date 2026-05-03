from pathlib import Path

_BLOCKED_NAMES: frozenset[str] = frozenset(
    {"Thumbs.db", "desktop.ini", ".DS_Store", "Icon\r"}
)
_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".pdf"})
AUDIO_EXTENSIONS: frozenset[str] = frozenset({".mp3", ".wav", ".m4a"})
_SUPPORTED_EXTENSIONS: frozenset[str] = _IMAGE_EXTENSIONS | AUDIO_EXTENSIONS


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


_CLOUD_AUDIO_LIMIT_BYTES = 25 * 1024 * 1024   # OpenAI Whisper hard limit
_CLOUD_AUDIO_PROVIDERS = frozenset({"openai", "gemini"})


def audio_size_ok(path: Path, provider: str) -> bool:
    """Return True if the file's size is within the provider's audio limit."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if provider in _CLOUD_AUDIO_PROVIDERS:
        return size <= _CLOUD_AUDIO_LIMIT_BYTES
    return True


def is_safe_file(path: Path) -> bool:
    """Return True if path is safe and supported for enrichment."""
    try:
        if not path.is_file():
            return False
        if path.is_symlink():
            return False
        if path.stat().st_size == 0:
            return False
        if path.name in _BLOCKED_NAMES:
            return False
        if path.name.startswith("."):
            return False
        for part in path.parts[:-1]:
            if part.startswith(".") or part == ".llmind-keys":
                return False
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            return False
        return True
    except (OSError, PermissionError):
        return False
