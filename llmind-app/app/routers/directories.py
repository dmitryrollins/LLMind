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
