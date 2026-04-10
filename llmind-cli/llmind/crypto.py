"""Cryptographic utilities for LLMind CLI.

All functions use stdlib only: hashlib, hmac, secrets, json, pathlib.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from pathlib import Path

from llmind.models import KeyFile


def generate_key() -> str:
    """Return secrets.token_hex(32) — 256-bit hex string (64 chars)."""
    return secrets.token_hex(32)


def derive_key_id(creation_key: str) -> str:
    """Return sha256(creation_key.encode()).hexdigest()[:16]."""
    return hashlib.sha256(creation_key.encode()).hexdigest()[:16]


def sha256_file(path: Path) -> str:
    """Return SHA-256 hex digest of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sign_layer(creation_key: str, layer_dict: dict[str, object]) -> str:
    """Return HMAC-SHA256(creation_key, json.dumps(layer_dict, sort_keys=True))."""
    message = json.dumps(layer_dict, sort_keys=True).encode()
    return hmac.new(
        creation_key.encode(),
        msg=message,
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_signature(creation_key: str, layer_dict: dict[str, object], signature: str) -> bool:
    """Constant-time HMAC comparison. Returns True if valid."""
    expected = sign_layer(creation_key, layer_dict)
    return hmac.compare_digest(expected, signature)


def save_key_file(output_dir: Path, key_file: KeyFile) -> Path:
    """Write JSON to output_dir/.llmind-keys/<key_file.file>.key.

    Creates .llmind-keys/ directory if needed.
    Auto-adds '.llmind-keys/' to output_dir/.gitignore if not already present.
    Returns path to the .key file.
    """
    keys_dir = output_dir / ".llmind-keys"
    keys_dir.mkdir(parents=True, exist_ok=True)

    key_path = keys_dir / f"{key_file.file}.key"
    payload = {
        "key_id": key_file.key_id,
        "creation_key": key_file.creation_key,
        "created": key_file.created,
        "file": key_file.file,
        "note": key_file.note,
    }
    key_path.write_text(json.dumps(payload, indent=2))

    _update_gitignore(output_dir)

    return key_path


def load_key_file(path: Path) -> KeyFile:
    """Read JSON from path, return KeyFile dataclass."""
    data = json.loads(path.read_text())
    try:
        return KeyFile(
            key_id=data["key_id"],
            creation_key=data["creation_key"],
            created=data["created"],
            file=data["file"],
            note=data["note"],
        )
    except KeyError as exc:
        raise ValueError(f"Malformed key file {path}: missing field {exc}") from exc


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _update_gitignore(output_dir: Path) -> None:
    """Add '.llmind-keys/' to .gitignore in output_dir if not already present."""
    gitignore_path = output_dir / ".gitignore"
    entry = ".llmind-keys/\n"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if ".llmind-keys/" not in content:
            gitignore_path.write_text(content.rstrip("\n") + "\n" + entry)
    else:
        gitignore_path.write_text(entry)
