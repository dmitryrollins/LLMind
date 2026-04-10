from pathlib import Path

_BLOCKED_NAMES: frozenset[str] = frozenset(
    {"Thumbs.db", "desktop.ini", ".DS_Store", "Icon\r"}
)
_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".pdf"})


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
        # Reject files inside hidden directories or .llmind-keys
        for part in path.parts[:-1]:
            if part.startswith(".") or part == ".llmind-keys":
                return False
        if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            return False
        return True
    except (OSError, PermissionError):
        return False
