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
