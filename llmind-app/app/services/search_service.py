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
