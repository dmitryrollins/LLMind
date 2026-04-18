import pytest
from pathlib import Path
from llmind.safety import is_safe_file


@pytest.mark.parametrize("name,expected", [
    ("photo.jpg", True),
    ("scan.jpeg", True),
    ("image.PNG", True),
    ("document.pdf", True),
    (".hidden.jpg", False),
    ("Thumbs.db", False),
    ("desktop.ini", False),
    (".DS_Store", False),
    ("photo.txt", False),
    ("photo.mp4", False),
])
def test_safe_file_by_name(tmp_path: Path, name: str, expected: bool):
    path = tmp_path / name
    path.write_bytes(b"\xff\xd8" if name.lower().endswith((".jpg", ".jpeg")) else b"data")
    assert is_safe_file(path) == expected


def test_rejects_symlink(tmp_path: Path):
    real = tmp_path / "photo.jpg"
    real.write_bytes(b"\xff\xd8")
    link = tmp_path / "link.jpg"
    link.symlink_to(real)
    assert is_safe_file(link) is False


def test_rejects_zero_byte_file(tmp_path: Path):
    path = tmp_path / "empty.jpg"
    path.touch()
    assert is_safe_file(path) is False


def test_rejects_file_in_llmind_keys(tmp_path: Path):
    keys_dir = tmp_path / ".llmind-keys"
    keys_dir.mkdir()
    path = keys_dir / "photo.jpg"
    path.write_bytes(b"\xff\xd8")
    assert is_safe_file(path) is False


def test_rejects_file_in_hidden_directory(tmp_path: Path):
    hidden = tmp_path / ".hidden_dir"
    hidden.mkdir()
    path = hidden / "photo.jpg"
    path.write_bytes(b"\xff\xd8")
    assert is_safe_file(path) is False


import pytest
from llmind.safety import is_safe_file, is_audio_file, AUDIO_EXTENSIONS


def test_audio_extensions_set():
    assert AUDIO_EXTENSIONS == frozenset({".mp3", ".wav", ".m4a"})


@pytest.mark.parametrize("name", ["memo.mp3", "memo.MP3", "test.wav", "voice.m4a"])
def test_audio_file_passes_safety(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"\x00" * 32)
    assert is_safe_file(p) is True
    assert is_audio_file(p) is True


def test_image_file_is_not_audio(tmp_path):
    p = tmp_path / "photo.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0")
    assert is_audio_file(p) is False


def test_flac_not_supported_yet(tmp_path):
    p = tmp_path / "song.flac"
    p.write_bytes(b"fLaC\x00")
    assert is_safe_file(p) is False
