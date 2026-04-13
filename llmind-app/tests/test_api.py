from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "llmind-cli"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_scan_missing_dir() -> None:
    r = client.get("/api/scan?dir=/nonexistent/path/xyz")
    assert r.status_code == 404


def test_scan_valid_dir(tmp_path) -> None:
    (tmp_path / "photo.llmind.jpg").touch()
    r = client.get(f"/api/scan?dir={tmp_path}")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["files"][0]["name"] == "photo.llmind.jpg"


def test_search_empty_query() -> None:
    r = client.get("/api/search?q=&dir=/tmp")
    assert r.status_code == 400


def test_search_missing_dir() -> None:
    r = client.get("/api/search?q=ring&dir=/nonexistent/xyz")
    assert r.status_code == 404


@patch("app.routers.search.search_files", return_value=[])
def test_search_empty_results(mock_search, tmp_path) -> None:
    r = client.get(f"/api/search?q=ring&dir={tmp_path}&mode=keyword")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_thumbnail_missing_file() -> None:
    r = client.get("/api/thumbnail?path=/nonexistent/file.jpg")
    assert r.status_code in (403, 404)


def test_reveal_nonexistent() -> None:
    r = client.post("/api/reveal", json={"path": "/nonexistent/file.jpg"})
    assert r.status_code in (403, 404)
