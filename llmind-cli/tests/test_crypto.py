from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from llmind.models import KeyFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_key_file(file: str = "sample.txt") -> KeyFile:
    from llmind.crypto import generate_key, derive_key_id
    from datetime import datetime, timezone

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
    from llmind.crypto import generate_key

    key = generate_key()
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_generate_key_uniqueness():
    from llmind.crypto import generate_key

    assert generate_key() != generate_key()


# ---------------------------------------------------------------------------
# derive_key_id
# ---------------------------------------------------------------------------

def test_derive_key_id_length():
    from llmind.crypto import generate_key, derive_key_id

    key = generate_key()
    key_id = derive_key_id(key)
    assert len(key_id) == 16
    assert all(c in "0123456789abcdef" for c in key_id)


def test_derive_key_id_deterministic():
    from llmind.crypto import generate_key, derive_key_id

    key = generate_key()
    assert derive_key_id(key) == derive_key_id(key)


# ---------------------------------------------------------------------------
# sha256_file
# ---------------------------------------------------------------------------

def test_sha256_file_known_value(tmp_path: Path):
    from llmind.crypto import sha256_file

    content = b"hello world"
    f = tmp_path / "test.txt"
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert sha256_file(f) == expected


# ---------------------------------------------------------------------------
# sign_layer / verify_signature
# ---------------------------------------------------------------------------

def test_sign_layer_length():
    from llmind.crypto import generate_key, sign_layer

    key = generate_key()
    sig = sign_layer(key, {"a": 1, "b": "two"})
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_sign_layer_deterministic():
    from llmind.crypto import generate_key, sign_layer

    key = generate_key()
    layer = {"version": 1, "text": "hello"}
    assert sign_layer(key, layer) == sign_layer(key, layer)


def test_verify_signature_correct_key():
    from llmind.crypto import generate_key, sign_layer, verify_signature

    key = generate_key()
    layer = {"version": 1, "text": "hello"}
    sig = sign_layer(key, layer)
    assert verify_signature(key, layer, sig) is True


def test_verify_signature_wrong_key():
    from llmind.crypto import generate_key, sign_layer, verify_signature

    key1 = generate_key()
    key2 = generate_key()
    layer = {"version": 1, "text": "hello"}
    sig = sign_layer(key1, layer)
    assert verify_signature(key2, layer, sig) is False


# ---------------------------------------------------------------------------
# save_key_file / load_key_file
# ---------------------------------------------------------------------------

def test_save_load_key_file_roundtrip(tmp_path: Path):
    from llmind.crypto import save_key_file, load_key_file

    kf = _make_key_file("roundtrip.txt")
    saved_path = save_key_file(tmp_path, kf)
    loaded = load_key_file(saved_path)

    assert loaded.key_id == kf.key_id
    assert loaded.creation_key == kf.creation_key
    assert loaded.created == kf.created
    assert loaded.file == kf.file
    assert loaded.note == kf.note


def test_save_key_file_creates_gitignore(tmp_path: Path):
    from llmind.crypto import save_key_file

    kf = _make_key_file("file.txt")
    save_key_file(tmp_path, kf)

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert ".llmind-keys/" in gitignore.read_text()


def test_save_key_file_gitignore_not_duplicated(tmp_path: Path):
    from llmind.crypto import save_key_file

    kf1 = _make_key_file("file1.txt")
    kf2 = _make_key_file("file2.txt")
    save_key_file(tmp_path, kf1)
    save_key_file(tmp_path, kf2)

    gitignore = tmp_path / ".gitignore"
    content = gitignore.read_text()
    assert content.count(".llmind-keys/") == 1
