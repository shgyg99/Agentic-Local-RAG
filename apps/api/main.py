import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from packages.core.logging_config import configure_logging
from packages.core.settings import get_settings
from packages.notes.engine import create_note, export_notes_markdown, list_notes

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)


class NoteCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    project_id: str = "default"
    tags: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    creation_method: str = "manual"
    source_type: str = "manual"


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/projects/{project_id}/notes")
async def get_project_notes(project_id: str) -> list[dict[str, Any]]:
    return list_notes(project_id)


@app.post("/projects/{project_id}/notes")
async def create_project_note(project_id: str, payload: NoteCreateRequest) -> dict[str, Any]:
    return create_note(
        project_id=project_id,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        citations=payload.citations,
        creation_method=payload.creation_method,
        source_type=payload.source_type,
    )


@app.get("/projects/{project_id}/notes/export", response_class=PlainTextResponse)
async def export_project_notes(project_id: str) -> str:
    return export_notes_markdown(project_id)
