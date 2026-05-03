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
