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
    threshold: float = Query(0.01, ge=0.0, le=1.0),
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
