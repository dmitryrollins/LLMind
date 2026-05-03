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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
