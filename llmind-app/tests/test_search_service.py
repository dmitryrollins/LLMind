from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "llmind-cli"))

from app.services.search_service import scan_directory, search_files, SearchResult


def test_scan_directory_finds_llmind_files(tmp_path: Path) -> None:
    (tmp_path / "photo.llmind.jpg").touch()
    (tmp_path / "doc.llmind.png").touch()
    (tmp_path / "plain.jpg").touch()
    results = scan_directory(tmp_path)
    names = {p.name for p in results}
    assert "photo.llmind.jpg" in names
    assert "doc.llmind.png" in names
    assert "plain.jpg" not in names


def test_scan_directory_empty(tmp_path: Path) -> None:
    assert scan_directory(tmp_path) == []


def test_scan_directory_recursive(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.llmind.png").touch()
    results = scan_directory(tmp_path, recursive=True)
    assert any(p.name == "nested.llmind.png" for p in results)


@patch("app.services.search_service.read_meta")
@patch("app.services.search_service.read_embedding_from_xmp")
@patch("app.services.search_service._read_xmp")
@patch("app.services.search_service.embed_text")
def test_search_files_keyword_mode(
    mock_embed, mock_xmp, mock_emb, mock_meta, tmp_path: Path
) -> None:
    f = tmp_path / "a.llmind.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    mock_xmp.return_value = "<xmp/>"
    mock_emb.return_value = None
    meta = MagicMock()
    meta.current.description = "a gold ring on the table"
    meta.current.text = ""
    mock_meta.return_value = meta

    results = search_files("ring", [f], mode="keyword")

    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].score > 0
    assert results[0].filename == "a.llmind.png"
    mock_embed.assert_not_called()


@patch("app.services.search_service.read_meta")
@patch("app.services.search_service.read_embedding_from_xmp")
@patch("app.services.search_service._read_xmp")
@patch("app.services.search_service.embed_text")
def test_search_files_returns_sorted_by_score(
    mock_embed, mock_xmp, mock_emb, mock_meta, tmp_path: Path
) -> None:
    files = []
    descriptions = ["a gold ring", "wedding ring ceremony", "beach sunset photo"]
    for i, desc in enumerate(descriptions):
        f = tmp_path / f"file{i}.llmind.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        files.append(f)

    def side_effect(path):
        return "<xmp/>"
    mock_xmp.side_effect = side_effect

    def meta_side(path):
        idx = int(path.stem.replace("file", "").replace(".llmind", ""))
        m = MagicMock()
        m.current.description = descriptions[idx]
        m.current.text = ""
        return m
    mock_meta.side_effect = meta_side
    mock_emb.return_value = None

    results = search_files("ring", files, mode="keyword")
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
