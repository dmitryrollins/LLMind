from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from llmind.crypto import (
    derive_key_id,
    generate_key,
    load_key_file,
    save_key_file,
    sha256_file,
    sign_layer,
    verify_signature,
)
from llmind.models import KeyFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_key_file(file: str = "sample.txt") -> KeyFile:
    key = generate_key()
    key_id = derive_key_id(key)
    return KeyFile(
        key_id=key_id,
        creation_key=key,
        created=datetime.now(timezone.utc).isoformat(),
        file=file,
    )


# ---------------------------------------------------------------------------
# generate_key
# ---------------------------------------------------------------------------

def test_generate_key_length():
    key = generate_key()
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_generate_key_uniqueness():
    assert generate_key() != generate_key()


# ---------------------------------------------------------------------------
# derive_key_id
# ---------------------------------------------------------------------------

def test_derive_key_id_length():
    key = generate_key()
    key_id = derive_key_id(key)
    assert len(key_id) == 16
    assert all(c in "0123456789abcdef" for c in key_id)


def test_derive_key_id_deterministic():
    key = generate_key()
    assert derive_key_id(key) == derive_key_id(key)


# ---------------------------------------------------------------------------
# sha256_file
# ---------------------------------------------------------------------------

def test_sha256_file_known_value(tmp_path: Path):
    content = b"hello world"
    f = tmp_path / "test.txt"
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert sha256_file(f) == expected


# ---------------------------------------------------------------------------
# sign_layer / verify_signature
# ---------------------------------------------------------------------------

def test_sign_layer_length():
    key = generate_key()
    sig = sign_layer(key, {"a": 1, "b": "two"})
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_sign_layer_deterministic():
    key = generate_key()
    layer = {"version": 1, "text": "hello"}
    assert sign_layer(key, layer) == sign_layer(key, layer)


def test_verify_signature_correct_key():
    key = generate_key()
    layer = {"version": 1, "text": "hello"}
    sig = sign_layer(key, layer)
    assert verify_signature(key, layer, sig) is True


def test_verify_signature_wrong_key():
    key1 = generate_key()
    key2 = generate_key()
    layer = {"version": 1, "text": "hello"}
    sig = sign_layer(key1, layer)
    assert verify_signature(key2, layer, sig) is False


# ---------------------------------------------------------------------------
# save_key_file / load_key_file
# ---------------------------------------------------------------------------

def test_save_load_key_file_roundtrip(tmp_path: Path):
    kf = _make_key_file("roundtrip.txt")
    saved_path = save_key_file(tmp_path, kf)
    loaded = load_key_file(saved_path)

    assert loaded.key_id == kf.key_id
    assert loaded.creation_key == kf.creation_key
    assert loaded.created == kf.created
    assert loaded.file == kf.file
    assert loaded.note == kf.note


def test_save_key_file_creates_gitignore(tmp_path: Path):
    kf = _make_key_file("file.txt")
    save_key_file(tmp_path, kf)

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert ".llmind-keys/" in gitignore.read_text()


def test_save_key_file_gitignore_not_duplicated(tmp_path: Path):
    kf1 = _make_key_file("file1.txt")
    kf2 = _make_key_file("file2.txt")
    save_key_file(tmp_path, kf1)
    save_key_file(tmp_path, kf2)

    gitignore = tmp_path / ".gitignore"
    content = gitignore.read_text()
    assert content.count(".llmind-keys/") == 1


def test_save_key_file_gitignore_no_double_blank_line(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.pyc\n")

    kf = _make_key_file("file.txt")
    save_key_file(tmp_path, kf)

    content = gitignore.read_text()
    assert "\n\n" not in content
    assert content == "*.pyc\n.llmind-keys/\n"


def test_load_key_file_missing_field_raises(tmp_path: Path):
    broken = tmp_path / "bad.key"
    broken.write_text(json.dumps({"key_id": "abc"}))
    with pytest.raises(ValueError, match="missing field"):
        load_key_file(broken)
