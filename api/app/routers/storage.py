"""Serve short-lived signed downloads for the local storage backend."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import get_settings
from app.storage import resolve_local_download_token

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/download")
def download_local(token: str = Query(...)) -> FileResponse:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise HTTPException(404, detail="Not found.")
    try:
        path = resolve_local_download_token(token, settings=settings)
    except ValueError as exc:
        code = str(exc)
        status = 404 if code == "not_found" else 403
        raise HTTPException(status, detail=code) from exc
    return FileResponse(path, filename=path.name)
