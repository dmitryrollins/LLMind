# LLMind Mac App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a native macOS Raycast-style popup app that searches LLMind-enriched image files using a global hotkey, backed by a FastAPI companion server.

**Architecture:** A SwiftUI+AppKit app (`llmind-mac/`) manages a floating NSPanel popup triggered by ⌘⇧Space. It starts and monitors a FastAPI companion server (`llmind-app/`) via NSTask on port 58421. The server wraps the existing `llmind-cli` search/embedding logic. Swift talks to the server over HTTP; all search intelligence stays in Python.

**Tech Stack:** Swift 6 / SwiftUI / AppKit, Xcode 26, FastAPI + uvicorn, Python 3.13, llmind-cli (existing)

---

## File Map

### llmind-app/ (Python — build first)
| File | Purpose |
|---|---|
| `pyproject.toml` | Package metadata + deps (fastapi, uvicorn, pillow) |
| `app/__init__.py` | Empty |
| `app/main.py` | FastAPI app, CORS, router wiring, static mount |
| `app/services/search_service.py` | `scan_directory()`, `search_files()`, `SearchResult` dataclass |
| `app/routers/search.py` | `GET /api/search` |
| `app/routers/files.py` | `GET /api/thumbnail`, `POST /api/reveal` |
| `app/routers/directories.py` | `GET /api/scan` |
| `app/services/__init__.py` | Empty |
| `app/routers/__init__.py` | Empty |
| `tests/__init__.py` | Empty |
| `tests/test_search_service.py` | Unit tests for search_service |
| `tests/test_api.py` | FastAPI TestClient integration tests |

### llmind-mac/ (Swift — build second)
| File | Purpose |
|---|---|
| `LLMindMac.xcodeproj` | Xcode project (created via `swift package init` then converted) |
| `LLMindMac/App/LLMindMacApp.swift` | `@main`, owns ServerManager + MenuBarController |
| `LLMindMac/App/AppDelegate.swift` | NSApplication setup, `applicationShouldTerminateAfterLastWindowClosed = false` |
| `LLMindMac/Services/ServerManager.swift` | NSTask lifecycle, health-check, auto-restart |
| `LLMindMac/Services/HotkeyManager.swift` | CGEventTap global hotkey registration |
| `LLMindMac/Services/MenuBarController.swift` | NSStatusItem + menu |
| `LLMindMac/Services/FileIndexManager.swift` | FSEventStream, sorted `.llmind.*` file list |
| `LLMindMac/Network/LLMindAPI.swift` | URLSession wrappers for all 4 endpoints |
| `LLMindMac/Features/Search/SearchViewModel.swift` | `@Observable` query state, debounce, results |
| `LLMindMac/Features/Search/SearchWindowController.swift` | NSPanel show/hide, key event routing |
| `LLMindMac/Features/Search/SearchView.swift` | Root SwiftUI view wired to SearchViewModel |
| `LLMindMac/Features/Search/SearchBarView.swift` | Input field + mode badge + model badge |
| `LLMindMac/Features/Search/ResultRow.swift` | Single result row with thumbnail |
| `LLMindMac/Features/Search/ModelPickerView.swift` | Provider/model dropdown |
| `LLMindMac/Features/Search/FooterView.swift` | Keyboard hints + result count |
| `LLMindMac/Features/Settings/SettingsView.swift` | Hotkey, API keys, repo root picker |
| `LLMindMac/Models/SearchModels.swift` | `SearchResult`, `SearchMode`, `EmbedProvider` structs |
| `LLMindMac/Models/AppSettings.swift` | `@Observable` UserDefaults + Keychain wrapper |

---

## Task 1: llmind-app — project skeleton + pyproject.toml

**Files:**
- Create: `llmind-app/pyproject.toml`
- Create: `llmind-app/app/__init__.py`
- Create: `llmind-app/app/services/__init__.py`
- Create: `llmind-app/app/routers/__init__.py`
- Create: `llmind-app/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app/app/services"
mkdir -p "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app/app/routers"
mkdir -p "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app/tests"
touch "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app/app/__init__.py"
touch "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app/app/services/__init__.py"
touch "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app/app/routers/__init__.py"
touch "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app/tests/__init__.py"
```

- [ ] **Step 2: Write pyproject.toml**

```toml
# llmind-app/pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "llmind-app"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "pillow>=10.0",
    "requests>=2.31",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "httpx>=0.27",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
```

- [ ] **Step 3: Install dependencies**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]" -q
pip install -e "../llmind-cli" -q
echo "OK"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-app/pyproject.toml llmind-app/app/__init__.py llmind-app/app/services/__init__.py llmind-app/app/routers/__init__.py llmind-app/tests/__init__.py
git commit -m "chore(app): project skeleton and dependencies"
```

---

## Task 2: llmind-app — search_service.py

**Files:**
- Create: `llmind-app/app/services/search_service.py`
- Create: `llmind-app/tests/test_search_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# llmind-app/tests/test_search_service.py
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
        mock_xmp.return_value = "<xmp/>"
        mock_emb.return_value = None
        meta = MagicMock()
        meta.current.description = desc
        meta.current.text = ""

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
```

- [ ] **Step 2: Run — expect failure**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app"
source .venv/bin/activate
python -m pytest tests/test_search_service.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write search_service.py**

```python
# llmind-app/app/services/search_service.py
from __future__ import annotations
import sys
from dataclasses import dataclass
from pathlib import Path

_CLI = Path(__file__).parent.parent.parent.parent / "llmind-cli"
if str(_CLI) not in sys.path:
    sys.path.insert(0, str(_CLI))

from llmind.embedder import cosine_similarity, embed_text, keyword_score, read_embedding_from_xmp
from llmind.injector import read_xmp_jpeg, read_xmp_png, read_xmp_pdf
from llmind.reader import read as read_meta

LLMIND_SUFFIXES = {".jpg", ".jpeg", ".png", ".pdf"}


@dataclass(frozen=True)
class SearchResult:
    path: Path
    filename: str
    score: float
    vector_score: float
    keyword_score_val: float
    description: str
    file_type: str


def scan_directory(directory: Path, recursive: bool = False) -> list[Path]:
    pattern = "**/*.llmind.*" if recursive else "*.llmind.*"
    return sorted(
        p for p in directory.glob(pattern)
        if p.suffix.lower() in LLMIND_SUFFIXES and p.is_file()
    )


def _read_xmp(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return read_xmp_jpeg(path)
    if suffix == ".png":
        return read_xmp_png(path)
    if suffix == ".pdf":
        return read_xmp_pdf(path)
    return None


def search_files(
    query: str,
    files: list[Path],
    mode: str = "hybrid",
    vector_weight: float = 0.5,
    provider: str = "ollama",
    model: str | None = None,
    api_key: str | None = None,
    base_url: str = "http://localhost:11434/api/embeddings",
    top_k: int = 20,
    threshold: float = 0.0,
) -> list[SearchResult]:
    if mode not in {"hybrid", "vector", "keyword"}:
        raise ValueError(f"Invalid mode: {mode!r}")

    use_vector = mode in {"hybrid", "vector"}
    use_keyword = mode in {"hybrid", "keyword"}
    kw_weight = 1.0 - vector_weight

    query_vec: list[float] | None = None
    if use_vector:
        query_vec = embed_text(query, provider=provider, model=model,
                               api_key=api_key, base_url=base_url)

    results: list[SearchResult] = []
    for path in files:
        xmp_string = _read_xmp(path)
        if xmp_string is None:
            continue

        vec_score = 0.0
        if use_vector and query_vec is not None:
            vec = read_embedding_from_xmp(xmp_string)
            if vec is not None:
                vec_score = cosine_similarity(query_vec, vec)
            elif mode == "vector":
                continue

        kw_score = 0.0
        description = ""
        meta = read_meta(path)
        if meta is not None:
            description = meta.current.description or ""
            if use_keyword:
                kw_score = keyword_score(query, f"{description} {meta.current.text or ''}")

        if mode == "vector":
            combined = vec_score
        elif mode == "keyword":
            combined = kw_score
        else:
            combined = (vector_weight * vec_score) + (kw_weight * kw_score)

        if combined < threshold:
            continue

        suffix = path.suffix.lower()
        file_type = "pdf" if suffix == ".pdf" else ("jpeg" if suffix in {".jpg", ".jpeg"} else "png")
        results.append(SearchResult(
            path=path, filename=path.name,
            score=round(combined, 4),
            vector_score=round(vec_score, 4),
            keyword_score_val=round(kw_score, 4),
            description=description, file_type=file_type,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]
```

- [ ] **Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_search_service.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-app/app/services/search_service.py llmind-app/tests/test_search_service.py
git commit -m "feat(app): add search_service with scan_directory and search_files"
```

---

## Task 3: llmind-app — API routers + main.py

**Files:**
- Create: `llmind-app/app/routers/directories.py`
- Create: `llmind-app/app/routers/search.py`
- Create: `llmind-app/app/routers/files.py`
- Create: `llmind-app/app/main.py`
- Create: `llmind-app/tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# llmind-app/tests/test_api.py
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
```

- [ ] **Step 2: Run — expect failure**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app"
source .venv/bin/activate
python -m pytest tests/test_api.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write directories.py**

```python
# llmind-app/app/routers/directories.py
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.search_service import scan_directory

router = APIRouter(prefix="/api", tags=["directories"])


class FileInfo(BaseModel):
    path: str
    name: str
    file_type: str
    size_bytes: int


class ScanResponse(BaseModel):
    directory: str
    count: int
    files: list[FileInfo]


@router.get("/scan", response_model=ScanResponse)
def scan(
    dir: str = Query(...),
    recursive: bool = Query(False),
) -> ScanResponse:
    directory = Path(dir).expanduser().resolve()
    if not directory.exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {dir}")
    if not directory.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {dir}")
    files = scan_directory(directory, recursive=recursive)
    infos: list[FileInfo] = []
    for p in files:
        suffix = p.suffix.lower()
        file_type = "pdf" if suffix == ".pdf" else ("jpeg" if suffix in {".jpg", ".jpeg"} else "png")
        infos.append(FileInfo(path=str(p), name=p.name, file_type=file_type,
                               size_bytes=p.stat().st_size if p.exists() else 0))
    return ScanResponse(directory=str(directory), count=len(infos), files=infos)
```

- [ ] **Step 4: Write search.py**

```python
# llmind-app/app/routers/search.py
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.services.search_service import scan_directory, search_files, SearchResult

router = APIRouter(prefix="/api", tags=["search"])


class SearchResultDTO(BaseModel):
    path: str
    filename: str
    score: float
    vector_score: float
    keyword_score: float
    description: str
    file_type: str


class SearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    results: list[SearchResultDTO]


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(...),
    dir: str = Query(...),
    mode: str = Query("hybrid"),
    vector_weight: float = Query(0.5, ge=0.0, le=1.0),
    provider: str = Query("ollama"),
    model: str | None = Query(None),
    api_key: str | None = Query(None),
    top: int = Query(20, ge=1, le=100),
    threshold: float = Query(0.0, ge=0.0, le=1.0),
    recursive: bool = Query(True),
) -> SearchResponse:
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    directory = Path(dir).expanduser().resolve()
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory not found: {dir}")
    files = scan_directory(directory, recursive=recursive)
    if not files:
        return SearchResponse(query=q, mode=mode, total=0, results=[])
    try:
        results: list[SearchResult] = search_files(
            query=q, files=files, mode=mode,
            vector_weight=vector_weight, provider=provider,
            model=model or None, api_key=api_key or None,
            top_k=top, threshold=threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Search error: {exc}") from exc
    return SearchResponse(
        query=q, mode=mode, total=len(results),
        results=[SearchResultDTO(
            path=str(r.path), filename=r.filename,
            score=r.score, vector_score=r.vector_score,
            keyword_score=r.keyword_score_val,
            description=r.description, file_type=r.file_type,
        ) for r in results],
    )
```

- [ ] **Step 5: Write files.py**

```python
# llmind-app/app/routers/files.py
from __future__ import annotations
import io
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["files"])
THUMBNAIL_SIZE = (280, 280)
_HOME = Path.home()


def _safe_path(raw: str) -> Path:
    p = Path(raw).expanduser().resolve()
    try:
        p.relative_to(_HOME)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside home directory")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return p


@router.get("/thumbnail")
def thumbnail(path: str = Query(...)) -> Response:
    p = _safe_path(path)
    try:
        from PIL import Image
        if p.suffix.lower() == ".pdf":
            try:
                from pdf2image import convert_from_path
                pages = convert_from_path(str(p), dpi=72, first_page=1, last_page=1)
                img = pages[0].convert("RGB")
            except Exception:
                img = Image.new("RGB", THUMBNAIL_SIZE, (220, 220, 220))
        else:
            img = Image.open(p).convert("RGB")
        img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return Response(content=buf.getvalue(), media_type="image/jpeg",
                        headers={"Cache-Control": "max-age=3600"})
    except Exception:
        from PIL import Image
        img = Image.new("RGB", THUMBNAIL_SIZE, (40, 40, 40))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return Response(content=buf.getvalue(), media_type="image/jpeg")


class RevealRequest(BaseModel):
    path: str


class RevealResponse(BaseModel):
    revealed: bool
    path: str


@router.post("/reveal", response_model=RevealResponse)
def reveal(body: RevealRequest) -> RevealResponse:
    p = _safe_path(body.path)
    if sys.platform != "darwin":
        raise HTTPException(status_code=501, detail="Finder reveal only on macOS")
    result = subprocess.run(["open", "-R", str(p)], capture_output=True)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail="Failed to reveal in Finder")
    return RevealResponse(revealed=True, path=str(p))
```

- [ ] **Step 6: Write main.py**

```python
# llmind-app/app/main.py
from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import directories, files, search

app = FastAPI(title="LLMind Search", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:58421", "http://127.0.0.1:58421"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(directories.router)
app.include_router(search.router)
app.include_router(files.router)
```

- [ ] **Step 7: Run all tests — expect pass**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app"
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: all tests pass (no failures)

- [ ] **Step 8: Smoke test the server**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app"
source .venv/bin/activate
uvicorn app.main:app --port 58421 &
sleep 2
curl -s "http://localhost:58421/api/scan?dir=$HOME/Desktop" | python3 -m json.tool | head -10
kill %1
```

Expected: JSON with `count` and `files` array.

- [ ] **Step 9: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-app/app/ llmind-app/tests/
git commit -m "feat(app): FastAPI server with search, thumbnail, reveal, scan endpoints"
```

---

## Task 4: Swift project scaffold

**Files:**
- Create: `llmind-mac/` (Xcode project via command line)

- [ ] **Step 1: Create Xcode project using xcodebuild**

Open Xcode manually:
1. Launch **Xcode**
2. **File → New → Project**
3. Choose **macOS → App**
4. Product Name: `LLMindMac`
5. Team: (your team or Personal)
6. Organization ID: `com.llmind`
7. Interface: **SwiftUI**
8. Language: **Swift**
9. Uncheck "Include Tests" (we'll add unit tests manually)
10. Save to: `/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-mac/`

- [ ] **Step 2: Configure Info.plist for menu-bar-only app**

In Xcode, open `LLMindMac/Info.plist` (or `LLMindMac-Info.plist`) and add:

```xml
<key>LSUIElement</key>
<true/>
```

This hides the app from the Dock and makes it menu-bar only.

- [ ] **Step 3: Delete default ContentView.swift**

Delete `ContentView.swift` from the project (we'll replace with our own views).

- [ ] **Step 4: Create folder structure in Xcode**

Add groups (folders) in the project navigator:
- `App/`
- `Features/Search/`
- `Features/Settings/`
- `Services/`
- `Network/`
- `Models/`

- [ ] **Step 5: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "chore(mac): scaffold Xcode project"
```

---

## Task 5: Models + AppSettings

**Files:**
- Create: `llmind-mac/LLMindMac/Models/SearchModels.swift`
- Create: `llmind-mac/LLMindMac/Models/AppSettings.swift`

- [ ] **Step 1: Write SearchModels.swift**

```swift
// LLMindMac/Models/SearchModels.swift
import Foundation

enum SearchMode: String, CaseIterable {
    case hybrid, vector, keyword

    var label: String {
        switch self {
        case .hybrid: return "hybrid"
        case .vector: return "vector"
        case .keyword: return "keyword"
        }
    }

    var icon: String {
        switch self {
        case .hybrid: return "⚡"
        case .vector: return "〈v〉"
        case .keyword: return "Aa"
        }
    }

    // Cycles to next mode
    var next: SearchMode {
        let all = SearchMode.allCases
        let idx = all.firstIndex(of: self)!
        return all[(idx + 1) % all.count]
    }
}

enum EmbedProvider: String, CaseIterable, Identifiable {
    case ollama, openai, voyage
    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .ollama: return "Ollama (local)"
        case .openai: return "OpenAI"
        case .voyage: return "Voyage AI"
        }
    }

    var models: [String] {
        switch self {
        case .ollama: return ["nomic-embed-text"]
        case .openai: return ["text-embedding-3-small", "text-embedding-3-large"]
        case .voyage: return ["voyage-3.5"]
        }
    }

    var requiresAPIKey: Bool { self != .ollama }
}

struct SearchResult: Identifiable {
    let id = UUID()
    let path: String
    let filename: String
    let score: Double
    let vectorScore: Double
    let keywordScore: Double
    let description: String
    let fileType: String
}
```

- [ ] **Step 2: Write AppSettings.swift**

```swift
// LLMindMac/Models/AppSettings.swift
import Foundation
import Security

@Observable
final class AppSettings {
    static let shared = AppSettings()

    // UserDefaults keys
    private enum Keys {
        static let repoRoot = "repoRoot"
        static let provider = "embedProvider"
        static let model = "embedModel"
        static let searchMode = "searchMode"
        static let searchScope = "searchScope"
    }

    var repoRoot: String {
        get { UserDefaults.standard.string(forKey: Keys.repoRoot) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: Keys.repoRoot) }
    }

    var provider: EmbedProvider {
        get {
            let raw = UserDefaults.standard.string(forKey: Keys.provider) ?? "ollama"
            return EmbedProvider(rawValue: raw) ?? .ollama
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: Keys.provider) }
    }

    var model: String {
        get { UserDefaults.standard.string(forKey: Keys.model) ?? "nomic-embed-text" }
        set { UserDefaults.standard.set(newValue, forKey: Keys.model) }
    }

    var searchMode: SearchMode {
        get {
            let raw = UserDefaults.standard.string(forKey: Keys.searchMode) ?? "hybrid"
            return SearchMode(rawValue: raw) ?? .hybrid
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: Keys.searchMode) }
    }

    var searchScope: String {
        get { UserDefaults.standard.string(forKey: Keys.searchScope) ?? "~/" }
        set { UserDefaults.standard.set(newValue, forKey: Keys.searchScope) }
    }

    // MARK: - Keychain API keys

    func apiKey(for provider: EmbedProvider) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.llmind.\(provider.rawValue)",
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func setAPIKey(_ key: String, for provider: EmbedProvider) {
        let data = key.data(using: .utf8)!
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.llmind.\(provider.rawValue)",
            kSecValueData as String: data,
        ]
        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
    }
}
```

- [ ] **Step 3: Build to verify no compiler errors**

In Xcode: **⌘B**. Expected: Build Succeeded with 0 errors.

- [ ] **Step 4: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): add SearchModels and AppSettings"
```

---

## Task 6: LLMindAPI.swift — network layer

**Files:**
- Create: `llmind-mac/LLMindMac/Network/LLMindAPI.swift`

- [ ] **Step 1: Write LLMindAPI.swift**

```swift
// LLMindMac/Network/LLMindAPI.swift
import Foundation

enum LLMindAPIError: Error {
    case serverUnreachable
    case badResponse(Int)
    case decodingFailed
}

// Codable response types matching FastAPI schemas
struct ScanResponse: Codable {
    let directory: String
    let count: Int
    let files: [FileInfo]

    struct FileInfo: Codable {
        let path: String
        let name: String
        let fileType: String
        let sizeBytes: Int

        enum CodingKeys: String, CodingKey {
            case path, name
            case fileType = "file_type"
            case sizeBytes = "size_bytes"
        }
    }
}

struct SearchResponse: Codable {
    let query: String
    let mode: String
    let total: Int
    let results: [SearchResultDTO]

    struct SearchResultDTO: Codable {
        let path: String
        let filename: String
        let score: Double
        let vectorScore: Double
        let keywordScore: Double
        let description: String
        let fileType: String

        enum CodingKeys: String, CodingKey {
            case path, filename, score, description
            case vectorScore = "vector_score"
            case keywordScore = "keyword_score"
            case fileType = "file_type"
        }
    }
}

actor LLMindAPI {
    static let shared = LLMindAPI()
    private let base = URL(string: "http://127.0.0.1:58421")!
    private let session = URLSession.shared
    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        return d
    }()

    func isReachable() async -> Bool {
        var req = URLRequest(url: base.appendingPathComponent("/api/scan"))
        var comps = URLComponents(url: base.appendingPathComponent("/api/scan"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "dir", value: NSHomeDirectory())]
        req = URLRequest(url: comps.url!)
        req.timeoutInterval = 2
        do {
            let (_, resp) = try await session.data(for: req)
            return (resp as? HTTPURLResponse)?.statusCode == 200
        } catch {
            return false
        }
    }

    func search(
        query: String,
        mode: SearchMode,
        provider: EmbedProvider,
        model: String,
        apiKey: String?,
        scope: String,
        top: Int = 20
    ) async throws -> [SearchResult] {
        var comps = URLComponents(url: base.appendingPathComponent("/api/search"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "dir", value: (scope as NSString).expandingTildeInPath),
            URLQueryItem(name: "mode", value: mode.rawValue),
            URLQueryItem(name: "provider", value: provider.rawValue),
            URLQueryItem(name: "model", value: model),
            URLQueryItem(name: "top", value: String(top)),
            URLQueryItem(name: "recursive", value: "true"),
        ]
        if let key = apiKey {
            comps.queryItems?.append(URLQueryItem(name: "api_key", value: key))
        }
        let req = URLRequest(url: comps.url!, timeoutInterval: 30)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw LLMindAPIError.serverUnreachable }
        guard http.statusCode == 200 else { throw LLMindAPIError.badResponse(http.statusCode) }
        let dto = try decoder.decode(SearchResponse.self, from: data)
        return dto.results.map { r in
            SearchResult(
                path: r.path, filename: r.filename,
                score: r.score, vectorScore: r.vectorScore,
                keywordScore: r.keywordScore,
                description: r.description, fileType: r.fileType
            )
        }
    }

    func thumbnailURL(for path: String) -> URL {
        var comps = URLComponents(url: base.appendingPathComponent("/api/thumbnail"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [URLQueryItem(name: "path", value: path)]
        return comps.url!
    }

    func reveal(path: String) async throws {
        let url = base.appendingPathComponent("/api/reveal")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["path": path])
        let (_, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw LLMindAPIError.badResponse(0)
        }
    }

    func recentFiles(scope: String, limit: Int = 10) async throws -> [ScanResponse.FileInfo] {
        var comps = URLComponents(url: base.appendingPathComponent("/api/scan"), resolvingAgainstBaseURL: false)!
        comps.queryItems = [
            URLQueryItem(name: "dir", value: (scope as NSString).expandingTildeInPath),
            URLQueryItem(name: "recursive", value: "true"),
        ]
        let req = URLRequest(url: comps.url!, timeoutInterval: 10)
        let (data, _) = try await session.data(for: req)
        let dto = try decoder.decode(ScanResponse.self, from: data)
        return Array(dto.files.prefix(limit))
    }
}
```

- [ ] **Step 2: Build to verify — ⌘B in Xcode**

Expected: Build Succeeded.

- [ ] **Step 3: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): add LLMindAPI network layer"
```

---

## Task 7: ServerManager

**Files:**
- Create: `llmind-mac/LLMindMac/Services/ServerManager.swift`

- [ ] **Step 1: Write ServerManager.swift**

```swift
// LLMindMac/Services/ServerManager.swift
import Foundation

@Observable
final class ServerManager {
    private(set) var isRunning = false
    private var task: Process?
    private var healthTimer: Timer?

    func start(repoRoot: String) {
        let uvicorn = "\(repoRoot)/llmind-app/.venv/bin/uvicorn"
        guard FileManager.default.fileExists(atPath: uvicorn) else {
            print("[ServerManager] uvicorn not found at \(uvicorn)")
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: uvicorn)
        process.arguments = ["app.main:app", "--port", "58421", "--no-access-log"]
        process.currentDirectoryURL = URL(fileURLWithPath: "\(repoRoot)/llmind-app")
        process.terminationHandler = { [weak self] _ in
            Task { @MainActor in
                self?.isRunning = false
                // Auto-restart after 2s
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                self?.start(repoRoot: repoRoot)
            }
        }
        do {
            try process.run()
            task = process
            scheduleHealthCheck(repoRoot: repoRoot)
        } catch {
            print("[ServerManager] Failed to start: \(error)")
        }
    }

    func stop() {
        healthTimer?.invalidate()
        task?.terminate()
        task = nil
        isRunning = false
    }

    private func scheduleHealthCheck(repoRoot: String) {
        healthTimer?.invalidate()
        healthTimer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { [weak self] _ in
            Task { @MainActor in
                let reachable = await LLMindAPI.shared.isReachable()
                self?.isRunning = reachable
            }
        }
    }
}
```

- [ ] **Step 2: Build — ⌘B**

Expected: Build Succeeded.

- [ ] **Step 3: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): add ServerManager with auto-restart"
```

---

## Task 8: HotkeyManager + MenuBarController

**Files:**
- Create: `llmind-mac/LLMindMac/Services/HotkeyManager.swift`
- Create: `llmind-mac/LLMindMac/Services/MenuBarController.swift`

- [ ] **Step 1: Write HotkeyManager.swift**

```swift
// LLMindMac/Services/HotkeyManager.swift
import Cocoa

final class HotkeyManager {
    private var eventTap: CFMachPort?
    var onHotkey: (() -> Void)?

    func register() {
        let mask = CGEventMask(
            (1 << CGEventType.keyDown.rawValue)
        )
        eventTap = CGEvent.tapCreate(
            tap: .cgSessionEventTap,
            place: .headInsertEventTap,
            options: .defaultTap,
            eventsOfInterest: mask,
            callback: { proxy, type, event, refcon in
                guard let refcon else { return Unmanaged.passRetained(event) }
                let manager = Unmanaged<HotkeyManager>.fromOpaque(refcon).takeUnretainedValue()
                // ⌘⇧Space = keyCode 49, flags: command + shift
                let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
                let flags = event.flags
                let isCmd   = flags.contains(.maskCommand)
                let isShift = flags.contains(.maskShift)
                let isSpace = keyCode == 49
                if isCmd && isShift && isSpace {
                    DispatchQueue.main.async { manager.onHotkey?() }
                    return nil // consume event
                }
                return Unmanaged.passRetained(event)
            },
            userInfo: Unmanaged.passRetained(self).toOpaque()
        )
        if let tap = eventTap {
            let loop = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
            CFRunLoopAddSource(CFRunLoopGetCurrent(), loop, .commonModes)
            CGEvent.tapEnable(tap: tap, enable: true)
        }
    }

    func unregister() {
        if let tap = eventTap {
            CGEvent.tapEnable(tap: tap, enable: false)
        }
    }
}
```

- [ ] **Step 2: Write MenuBarController.swift**

```swift
// LLMindMac/Services/MenuBarController.swift
import Cocoa
import SwiftUI

final class MenuBarController {
    private var statusItem: NSStatusItem?
    var onShow: (() -> Void)?
    var onSettings: (() -> Void)?

    func setup() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem?.button {
            button.title = "⬡"
            button.font = NSFont.systemFont(ofSize: 14, weight: .medium)
            button.action = #selector(statusBarClicked)
            button.target = self
        }
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Show LLMind Search", action: #selector(showSearch), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Settings…", action: #selector(openSettings), keyEquivalent: ","))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit LLMind", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q"))
        for item in menu.items { item.target = self }
        statusItem?.menu = menu
    }

    @objc private func statusBarClicked() { onShow?() }
    @objc private func showSearch() { onShow?() }
    @objc private func openSettings() { onSettings?() }
}
```

- [ ] **Step 3: Add Accessibility usage description to Info.plist**

In Xcode, open Info.plist and add:
```xml
<key>NSAppleEventsUsageDescription</key>
<string>LLMind needs accessibility access to register a global hotkey.</string>
```

- [ ] **Step 4: Build — ⌘B**

Expected: Build Succeeded.

- [ ] **Step 5: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): add HotkeyManager and MenuBarController"
```

---

## Task 9: SearchViewModel

**Files:**
- Create: `llmind-mac/LLMindMac/Features/Search/SearchViewModel.swift`

- [ ] **Step 1: Write SearchViewModel.swift**

```swift
// LLMindMac/Features/Search/SearchViewModel.swift
import Foundation

@Observable
final class SearchViewModel {
    var query: String = "" {
        didSet { scheduleSearch() }
    }
    var results: [SearchResult] = []
    var selectedIndex: Int = 0
    var isLoading: Bool = false
    var mode: SearchMode = AppSettings.shared.searchMode {
        didSet { AppSettings.shared.searchMode = mode; triggerSearch() }
    }
    var showModelPicker: Bool = false

    private var debounceTask: Task<Void, Never>?
    private let api = LLMindAPI.shared
    private let settings = AppSettings.shared

    // MARK: - Search

    private func scheduleSearch() {
        debounceTask?.cancel()
        debounceTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 300_000_000) // 300ms
            guard !Task.isCancelled else { return }
            await performSearch()
        }
    }

    private func triggerSearch() {
        debounceTask?.cancel()
        Task { @MainActor in await performSearch() }
    }

    @MainActor
    private func performSearch() async {
        let q = query.trimmingCharacters(in: .whitespaces)

        // Empty query: show recent files
        if q.isEmpty {
            await loadRecentFiles()
            return
        }

        isLoading = true
        defer { isLoading = false }

        let provider = settings.provider
        let model = settings.model
        let apiKey = settings.apiKey(for: provider)
        let scope = settings.searchScope

        do {
            let found = try await api.search(
                query: q, mode: mode,
                provider: provider, model: model,
                apiKey: apiKey, scope: scope
            )
            results = found
            selectedIndex = 0
        } catch {
            // Fallback to keyword if vector/hybrid fails
            if mode != .keyword {
                mode = .keyword
                await performSearch()
            } else {
                results = []
            }
        }
    }

    @MainActor
    private func loadRecentFiles() async {
        do {
            let files = try await api.recentFiles(scope: settings.searchScope)
            results = files.map { f in
                SearchResult(
                    path: f.path, filename: f.name,
                    score: 0, vectorScore: 0, keywordScore: 0,
                    description: "", fileType: f.fileType
                )
            }
            selectedIndex = 0
        } catch {
            results = []
        }
    }

    // MARK: - Keyboard actions

    func moveUp() {
        guard !results.isEmpty else { return }
        selectedIndex = max(0, selectedIndex - 1)
    }

    func moveDown() {
        guard !results.isEmpty else { return }
        selectedIndex = min(results.count - 1, selectedIndex + 1)
    }

    func openSelected() {
        guard let result = selectedResult else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: result.path))
    }

    func revealSelected() {
        guard let result = selectedResult else { return }
        Task { try? await api.reveal(path: result.path) }
    }

    func copySelectedPath() {
        guard let result = selectedResult else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(result.path, forType: .string)
    }

    func cycleMode() {
        mode = mode.next
    }

    var selectedResult: SearchResult? {
        guard !results.isEmpty, selectedIndex < results.count else { return nil }
        return results[selectedIndex]
    }
}
```

- [ ] **Step 2: Build — ⌘B**

Expected: Build Succeeded.

- [ ] **Step 3: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): add SearchViewModel with debounce, keyboard actions, Ollama fallback"
```

---

## Task 10: Search UI views

**Files:**
- Create: `llmind-mac/LLMindMac/Features/Search/SearchBarView.swift`
- Create: `llmind-mac/LLMindMac/Features/Search/ModelPickerView.swift`
- Create: `llmind-mac/LLMindMac/Features/Search/ResultRow.swift`
- Create: `llmind-mac/LLMindMac/Features/Search/FooterView.swift`
- Create: `llmind-mac/LLMindMac/Features/Search/SearchView.swift`

- [ ] **Step 1: Write SearchBarView.swift**

```swift
// LLMindMac/Features/Search/SearchBarView.swift
import SwiftUI

struct SearchBarView: View {
    @Binding var query: String
    @Binding var mode: SearchMode
    @Binding var showModelPicker: Bool

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.tertiary)
                .font(.system(size: 16))

            TextField("Search images…", text: $query)
                .textFieldStyle(.plain)
                .font(.system(size: 17))
                .foregroundStyle(.primary)

            // Mode badge — click to cycle
            Button(action: { mode = mode.next }) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(modeColor)
                        .frame(width: 6, height: 6)
                    Text(mode.label)
                        .font(.system(size: 11, weight: .semibold))
                }
                .padding(.horizontal, 7)
                .padding(.vertical, 4)
                .background(modeColor.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 5))
                .overlay(RoundedRectangle(cornerRadius: 5).stroke(modeColor.opacity(0.3)))
            }
            .buttonStyle(.plain)
            .foregroundStyle(modeColor)

            // Model badge — click to open picker
            Button(action: { showModelPicker.toggle() }) {
                HStack(spacing: 4) {
                    Circle()
                        .fill(Color.indigo)
                        .frame(width: 6, height: 6)
                    Text(AppSettings.shared.model.components(separatedBy: "-").first ?? AppSettings.shared.model)
                        .font(.system(size: 11, weight: .semibold))
                }
                .padding(.horizontal, 7)
                .padding(.vertical, 4)
                .background(Color.indigo.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 5))
                .overlay(RoundedRectangle(cornerRadius: 5).stroke(Color.indigo.opacity(0.3)))
            }
            .buttonStyle(.plain)
            .foregroundStyle(Color.indigo)
            .popover(isPresented: $showModelPicker, arrowEdge: .bottom) {
                ModelPickerView()
            }

            Text("ESC")
                .font(.system(size: 11))
                .foregroundStyle(.quaternary)
        }
        .padding(.horizontal, 14)
        .frame(height: 52)
    }

    private var modeColor: Color {
        switch mode {
        case .hybrid: return .green
        case .vector: return .blue
        case .keyword: return .red
        }
    }
}
```

- [ ] **Step 2: Write ModelPickerView.swift**

```swift
// LLMindMac/Features/Search/ModelPickerView.swift
import SwiftUI

struct ModelPickerView: View {
    @Environment(\.dismiss) private var dismiss
    private let settings = AppSettings.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(EmbedProvider.allCases) { provider in
                Section {
                    ForEach(provider.models, id: \.self) { model in
                        Button(action: {
                            settings.provider = provider
                            settings.model = model
                            dismiss()
                        }) {
                            HStack(spacing: 10) {
                                Circle()
                                    .fill(providerColor(provider))
                                    .frame(width: 7, height: 7)
                                Text(model)
                                    .font(.system(size: 13))
                                Spacer()
                                if settings.provider == provider && settings.model == model {
                                    Image(systemName: "checkmark")
                                        .font(.system(size: 11, weight: .semibold))
                                        .foregroundStyle(.indigo)
                                } else if provider.requiresAPIKey {
                                    Text("API key required")
                                        .font(.system(size: 10))
                                        .foregroundStyle(.tertiary)
                                }
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .background(
                            settings.provider == provider && settings.model == model
                            ? Color.indigo.opacity(0.08) : Color.clear
                        )
                    }
                } header: {
                    Text(provider.displayName.uppercased())
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(.tertiary)
                        .padding(.horizontal, 12)
                        .padding(.top, 10)
                        .padding(.bottom, 4)
                }
            }

            Divider().padding(.top, 4)
            Text("⌘, to manage API keys")
                .font(.system(size: 10))
                .foregroundStyle(.quaternary)
                .padding(10)
        }
        .frame(width: 260)
        .background(.regularMaterial)
    }

    private func providerColor(_ provider: EmbedProvider) -> Color {
        switch provider {
        case .ollama: return .green
        case .openai: return .blue
        case .voyage: return .pink
        }
    }
}
```

- [ ] **Step 3: Write ResultRow.swift**

```swift
// LLMindMac/Features/Search/ResultRow.swift
import SwiftUI

struct ResultRow: View {
    let result: SearchResult
    let isSelected: Bool
    let showScore: Bool

    var body: some View {
        HStack(spacing: 12) {
            AsyncImage(url: LLMindAPI.shared.thumbnailURL(for: result.path)) { phase in
                switch phase {
                case .success(let image):
                    image.resizable().aspectRatio(contentMode: .fill)
                default:
                    RoundedRectangle(cornerRadius: 7)
                        .fill(Color(white: 0.2))
                }
            }
            .frame(width: 44, height: 44)
            .clipShape(RoundedRectangle(cornerRadius: 7))

            VStack(alignment: .leading, spacing: 2) {
                Text(result.filename)
                    .font(.system(size: 13))
                    .lineLimit(1)
                    .foregroundStyle(isSelected ? .primary : .secondary)
                if !result.description.isEmpty {
                    Text(result.description)
                        .font(.system(size: 11))
                        .lineLimit(1)
                        .foregroundStyle(.tertiary)
                }
            }

            Spacer()

            if isSelected {
                HStack(spacing: 4) {
                    KeyHint("↵", label: "Open")
                    KeyHint("⌘↵", label: "Reveal")
                    KeyHint("⌘C", label: "Copy")
                }
            } else if showScore && result.score > 0 {
                Text(String(format: "%.3f", result.score))
                    .font(.system(size: 12, weight: .semibold, design: .monospaced))
                    .foregroundStyle(scoreColor)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
        .background(isSelected ? Color(white: 0.18) : Color.clear)
        .contentShape(Rectangle())
    }

    private var scoreColor: Color {
        if result.score > 0.35 { return .cyan }
        if result.score > 0.20 { return .secondary }
        return .tertiary
    }
}

private struct KeyHint: View {
    let key: String
    let label: String
    init(_ key: String, label: String) { self.key = key; self.label = label }
    var body: some View {
        Text("\(key) \(label)")
            .font(.system(size: 10))
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .background(Color(white: 0.25))
            .clipShape(RoundedRectangle(cornerRadius: 4))
            .foregroundStyle(.secondary)
    }
}
```

- [ ] **Step 4: Write FooterView.swift**

```swift
// LLMindMac/Features/Search/FooterView.swift
import SwiftUI

struct FooterView: View {
    let resultCount: Int
    let mode: SearchMode
    let scope: String

    var body: some View {
        HStack(spacing: 16) {
            Group {
                keyHint("↑↓", "navigate")
                keyHint("↵", "open")
                keyHint("⌘↵", "reveal")
                keyHint("⌘C", "copy")
            }
            Spacer()
            Text("\(resultCount) result\(resultCount == 1 ? "" : "s") · \(scope) · \(mode.label)")
                .font(.system(size: 11))
                .foregroundStyle(.quaternary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
    }

    @ViewBuilder
    private func keyHint(_ key: String, _ action: String) -> some View {
        HStack(spacing: 3) {
            Text(key)
                .padding(.horizontal, 4)
                .padding(.vertical, 1)
                .background(Color(white: 0.2))
                .clipShape(RoundedRectangle(cornerRadius: 3))
                .font(.system(size: 10))
                .foregroundStyle(.quaternary)
            Text(action)
                .font(.system(size: 11))
                .foregroundStyle(.quaternary)
        }
    }
}
```

- [ ] **Step 5: Write SearchView.swift**

```swift
// LLMindMac/Features/Search/SearchView.swift
import SwiftUI

struct SearchView: View {
    @State private var vm = SearchViewModel()

    var body: some View {
        VStack(spacing: 0) {
            SearchBarView(
                query: $vm.query,
                mode: $vm.mode,
                showModelPicker: $vm.showModelPicker
            )

            Divider()

            if vm.results.isEmpty && !vm.isLoading && vm.query.isEmpty {
                Text("Type to search enriched images…")
                    .font(.system(size: 13))
                    .foregroundStyle(.tertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 32)
            } else if vm.results.isEmpty && !vm.isLoading {
                Text("No matches for "\(vm.query)"")
                    .font(.system(size: 13))
                    .foregroundStyle(.tertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 32)
            } else {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(Array(vm.results.enumerated()), id: \.element.id) { idx, result in
                                ResultRow(
                                    result: result,
                                    isSelected: idx == vm.selectedIndex,
                                    showScore: !vm.query.isEmpty
                                )
                                .id(idx)
                                .onTapGesture { vm.selectedIndex = idx; vm.openSelected() }
                                Divider().padding(.leading, 70)
                            }
                        }
                    }
                    .onChange(of: vm.selectedIndex) { _, new in
                        withAnimation(.easeInOut(duration: 0.1)) { proxy.scrollTo(new) }
                    }
                }
                .frame(maxHeight: 360)
            }

            Divider()

            FooterView(
                resultCount: vm.results.count,
                mode: vm.mode,
                scope: AppSettings.shared.searchScope
            )
        }
        .frame(width: 580)
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: .black.opacity(0.5), radius: 32, y: 16)
        .onKeyPress(.upArrow) { vm.moveUp(); return .handled }
        .onKeyPress(.downArrow) { vm.moveDown(); return .handled }
        .onKeyPress(.return) { vm.openSelected(); return .handled }
        .onKeyPress(.return, phases: .down) { event in
            if event.modifiers.contains(.command) { vm.revealSelected(); return .handled }
            return .ignored
        }
        .onKeyPress("c", phases: .down) { event in
            if event.modifiers.contains(.command) { vm.copySelectedPath(); return .handled }
            return .ignored
        }
    }
}
```

- [ ] **Step 6: Build — ⌘B**

Expected: Build Succeeded.

- [ ] **Step 7: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): add Search UI views (SearchBar, ResultRow, Footer, ModelPicker, SearchView)"
```

---

## Task 11: SearchWindowController + NSPanel

**Files:**
- Create: `llmind-mac/LLMindMac/Features/Search/SearchWindowController.swift`

- [ ] **Step 1: Write SearchWindowController.swift**

```swift
// LLMindMac/Features/Search/SearchWindowController.swift
import Cocoa
import SwiftUI

final class SearchWindowController: NSWindowController {
    convenience init() {
        let panel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 580, height: 500),
            styleMask: [.nonactivatingPanel, .fullSizeContentView, .borderless],
            backing: .buffered,
            defer: false
        )
        panel.isFloatingPanel = true
        panel.level = .floating
        panel.backgroundColor = .clear
        panel.isOpaque = false
        panel.hasShadow = false  // SwiftUI view provides its own shadow
        panel.isMovableByWindowBackground = true
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.contentView = NSHostingView(rootView: SearchView())
        self.init(window: panel)
    }

    func toggle() {
        guard let window else { return }
        if window.isVisible {
            hide()
        } else {
            show()
        }
    }

    func show() {
        guard let window, let screen = NSScreen.main else { return }
        // Center horizontally, position in upper-third vertically
        let sw = screen.visibleFrame.width
        let sh = screen.visibleFrame.height
        let x = screen.visibleFrame.minX + (sw - window.frame.width) / 2
        let y = screen.visibleFrame.minY + sh * 0.62
        window.setFrameOrigin(NSPoint(x: x, y: y))
        window.makeKeyAndOrderFront(nil)
        window.contentView?.window?.makeFirstResponder(window.contentView)
    }

    func hide() {
        window?.orderOut(nil)
    }
}
```

- [ ] **Step 2: Build — ⌘B**

Expected: Build Succeeded.

- [ ] **Step 3: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): add SearchWindowController NSPanel"
```

---

## Task 12: App entry point + wiring

**Files:**
- Modify: `llmind-mac/LLMindMac/App/LLMindMacApp.swift`
- Create: `llmind-mac/LLMindMac/App/AppDelegate.swift`

- [ ] **Step 1: Write AppDelegate.swift**

```swift
// LLMindMac/App/AppDelegate.swift
import Cocoa

final class AppDelegate: NSObject, NSApplicationDelegate {
    let serverManager = ServerManager()
    let menuBarController = MenuBarController()
    let hotkeyManager = HotkeyManager()
    lazy var searchWindowController = SearchWindowController()

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Ensure repo root is configured
        let repoRoot = AppSettings.shared.repoRoot
        if repoRoot.isEmpty {
            promptForRepoRoot()
        } else {
            serverManager.start(repoRoot: repoRoot)
        }

        menuBarController.setup()
        menuBarController.onShow = { [weak self] in self?.searchWindowController.toggle() }
        menuBarController.onSettings = { [weak self] in self?.openSettings() }

        hotkeyManager.onHotkey = { [weak self] in self?.searchWindowController.toggle() }
        hotkeyManager.register()
    }

    func applicationWillTerminate(_ notification: Notification) {
        serverManager.stop()
        hotkeyManager.unregister()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false
    }

    private func openSettings() {
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 400, height: 320),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: false
        )
        window.title = "LLMind Settings"
        window.center()
        window.contentView = NSHostingView(rootView: SettingsView())
        window.makeKeyAndOrderFront(nil)
    }

    private func promptForRepoRoot() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Select the LLMind repository root folder"
        panel.prompt = "Select"
        if panel.runModal() == .OK, let url = panel.url {
            AppSettings.shared.repoRoot = url.path
            serverManager.start(repoRoot: url.path)
        }
    }
}
```

- [ ] **Step 2: Write LLMindMacApp.swift**

```swift
// LLMindMac/App/LLMindMacApp.swift
import SwiftUI

@main
struct LLMindMacApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        // No main window — menu bar only (LSUIElement = true)
        Settings {
            SettingsView()
        }
    }
}
```

- [ ] **Step 3: Write SettingsView.swift**

```swift
// LLMindMac/Features/Settings/SettingsView.swift
import SwiftUI

struct SettingsView: View {
    private let settings = AppSettings.shared
    @State private var openAIKey: String = ""
    @State private var voyageKey: String = ""

    var body: some View {
        Form {
            Section("Server") {
                HStack {
                    Text("Repo Root")
                    Spacer()
                    Text(settings.repoRoot.isEmpty ? "Not set" : settings.repoRoot)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Button("Change…") { pickRepoRoot() }
                }
            }

            Section("Search") {
                Picker("Default Mode", selection: Binding(
                    get: { settings.searchMode },
                    set: { settings.searchMode = $0 }
                )) {
                    ForEach(SearchMode.allCases, id: \.self) { mode in
                        Text(mode.label).tag(mode)
                    }
                }
                HStack {
                    Text("Search Scope")
                    Spacer()
                    Text(settings.searchScope)
                        .foregroundStyle(.secondary)
                    Button("Change…") { pickScope() }
                }
            }

            Section("API Keys") {
                SecureField("OpenAI API Key", text: $openAIKey)
                    .onSubmit { settings.setAPIKey(openAIKey, for: .openai) }
                SecureField("Voyage AI API Key", text: $voyageKey)
                    .onSubmit { settings.setAPIKey(voyageKey, for: .voyage) }
            }
        }
        .formStyle(.grouped)
        .padding()
        .frame(width: 400)
        .onAppear {
            openAIKey = settings.apiKey(for: .openai) ?? ""
            voyageKey = settings.apiKey(for: .voyage) ?? ""
        }
    }

    private func pickRepoRoot() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Select the LLMind repository root"
        if panel.runModal() == .OK, let url = panel.url {
            settings.repoRoot = url.path
        }
    }

    private func pickScope() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.message = "Select default search folder"
        if panel.runModal() == .OK, let url = panel.url {
            settings.searchScope = url.path
        }
    }
}
```

- [ ] **Step 4: Build — ⌘B**

Expected: Build Succeeded.

- [ ] **Step 5: Run the app**

Press **⌘R** in Xcode.

Expected:
- ⬡ appears in menu bar
- System prompts for repo root (first launch) → select `/Users/dzmitrytryhubenka/APP DEV/LLMind`
- Accessibility permission prompt appears → grant it in System Settings

- [ ] **Step 6: Commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add llmind-mac/
git commit -m "feat(mac): wire up AppDelegate, hotkey, menu bar, and settings"
```

---

## Task 13: End-to-end smoke test

- [ ] **Step 1: Start the FastAPI server manually to verify it works**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind/llmind-app"
source .venv/bin/activate
uvicorn app.main:app --port 58421 --no-access-log
```

- [ ] **Step 2: Test search endpoint**

```bash
curl -s "http://localhost:58421/api/search?q=ring&dir=$HOME/Desktop/Screen%20Shoot&mode=keyword&recursive=false" | python3 -m json.tool | head -30
```

Expected: JSON with `total`, `results` array, each with `filename`, `score`, `description`.

- [ ] **Step 3: Test thumbnail endpoint**

```bash
# Replace with an actual .llmind.png path from your search results above
curl -s "http://localhost:58421/api/thumbnail?path=$HOME/Desktop/Screen%20Shoot/Screenshot%202026-03-24%20at%2009.54.37.llmind.png" -o /tmp/thumb.jpg && open /tmp/thumb.jpg
```

Expected: thumbnail image opens in Preview.

- [ ] **Step 4: Press ⌘⇧Space in the running app**

Expected:
- Floating popup appears centered in upper third of screen
- Text field is focused
- Typing "ring" shows results within 500ms (keyword mode) or ~1s (hybrid with Ollama)
- ↑↓ moves selection
- ↵ opens the file
- ⌘↵ reveals in Finder
- ESC dismisses popup

- [ ] **Step 5: Final commit**

```bash
cd "/Users/dzmitrytryhubenka/APP DEV/LLMind"
git add -A
git commit -m "feat(mac): complete LLMind Mac app v1"
git push origin feature/llmind-cli
```

---

## Success Criteria

- [ ] `⌘⇧Space` summons popup in < 50ms
- [ ] Search results appear within 500ms of last keystroke (Ollama running)
- [ ] Keyword fallback works instantly when Ollama is offline (mode badge turns red)
- [ ] Thumbnails load for JPEG and PNG files
- [ ] `↵` opens file, `⌘↵` reveals in Finder, `⌘C` copies path
- [ ] Model picker shows all configured providers; selection persists across launches
- [ ] App survives FastAPI server crash (ServerManager auto-restarts)
- [ ] FSEventStream picks up newly enriched files without app restart (covered by ServerManager scan)
- [ ] Empty query shows 10 most recently modified `.llmind.*` files
