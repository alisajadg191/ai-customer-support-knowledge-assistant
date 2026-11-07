import json
import logging
import os
from pathlib import Path
from time import perf_counter
from contextlib import asynccontextmanager
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from auth import auth_routes
from db import connect, initialize
from enquiries import enquiry_routes
from knowledge import Knowledge
from model import ModelUnavailable, Ollama

STATIC = Path(__file__).with_name("static")
logger = logging.getLogger("uvicorn.error")

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]
QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]


class Document(BaseModel):
    title: Title
    body: Body


class Question(BaseModel):
    question: QuestionText


def create_app(dsn=None, model=None):
    dsn = dsn or os.getenv("DATABASE_URL", "")
    knowledge = Knowledge(dsn, model or Ollama())

    @asynccontextmanager
    async def lifespan(_app):
        if not dsn:
            raise RuntimeError("Set DATABASE_URL before starting the API")
        initialize(dsn)
        yield

    api = FastAPI(title="AI Customer Support & Knowledge Assistant", lifespan=lifespan)

    auth, current_user, require_staff, require_customer = auth_routes(dsn)
    api.include_router(auth)
    api.include_router(enquiry_routes(dsn, knowledge, require_staff, require_customer))

    api.mount("/static", StaticFiles(directory=STATIC), name="static")

    @api.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    @api.middleware("http")
    async def log_request(request, call_next):
        start = perf_counter()
        response = await call_next(request)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "route": getattr(request.scope.get("route"), "path", "static_or_unmatched"),
            "status": response.status_code,
            "duration_ms": round((perf_counter() - start) * 1000, 2),
        }))
        return response

    @api.exception_handler(ModelUnavailable)
    async def model_error(_request, _error):
        return JSONResponse(status_code=503, content={"detail": "AI service unavailable"})

    @api.get("/health")
    def health():
        try:
            with connect(dsn) as connection:
                connection.execute("SELECT 1")
        except psycopg.OperationalError:
            raise HTTPException(503, "Database unavailable") from None
        return {"status": "ok", "database": "ready"}

    @api.post("/documents", status_code=201, dependencies=[Depends(require_staff)])
    def add_document(document: Document):
        return knowledge.add(document.title, document.body)

    @api.get("/documents/{document_id}", dependencies=[Depends(current_user)])
    def get_document(document_id: int):
        with connect(dsn) as connection:
            document = connection.execute("SELECT * FROM documents WHERE id = %s", (document_id,)).fetchone()
        if document is None:
            raise HTTPException(404, "Document not found")
        return document

    @api.post("/search", dependencies=[Depends(current_user)])
    def search(payload: Question):
        return knowledge.search(payload.question)

    @api.post("/ask", dependencies=[Depends(current_user)])
    def ask(payload: Question):
        return knowledge.answer(payload.question)

    return api


app = create_app()
