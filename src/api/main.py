"""
main.py (api)
-------------
FastAPI application for SentinelGraph AI.

Run locally:

    pip install -r requirements.txt
    uvicorn src.api.main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs

Route groups (see src/api/routes.py):
    /api/pipeline /api/data /api/graph /api/evidence /api/findings
    /api/simulation /api/dossiers /api/cases /api/search /api/audit

Hardening (Phase R / AC): CORS allow-list via env, request size limits,
consistent error envelope, graph query limits, structured error logging,
and an append-only audit log for investigator actions.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import ALL_ROUTERS
from src.api.services import MAX_UPLOAD_BYTES

logging.basicConfig(
    level=os.environ.get("SENTINELGRAPH_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sentinelgraph.api")

app = FastAPI(
    title="SentinelGraph AI API",
    description=(
        "Synthetic dataset generation -> preprocessing -> NLP extraction -> "
        "entity resolution -> knowledge graph -> analytics -> ghost-node "
        "inference -> evidence-grounded XAI (findings, dossiers) and "
        "counterfactual simulation, exposed for the investigator UI."
    ),
    version="2.0.0",
)

# CORS: comma-separated origins via CORS_ORIGINS env var, defaults cover the
# usual React dev servers (CRA on 3000, Vite on 5173).
_default_origins = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:8000"
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", _default_origins).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_guard(request: Request, call_next):
    """Request size limit + light-touch structured logging."""
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"error": "PAYLOAD_TOO_LARGE",
                     "detail": f"Request body exceeds {MAX_UPLOAD_BYTES} bytes"},
        )
    response = await call_next(request)
    if response.status_code >= 500:
        logger.error("%s %s -> %s", request.method, request.url.path,
                     response.status_code)
    return response


@app.exception_handler(FileNotFoundError)
async def artifact_missing_handler(request: Request, exc: FileNotFoundError):
    """Missing pipeline artifacts become a consistent 404 payload."""
    return JSONResponse(
        status_code=404,
        content={"error": "ARTIFACT_NOT_FOUND", "detail": str(exc)},
    )


for router in ALL_ROUTERS:
    app.include_router(router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "service": "sentinelgraph-ai", "version": "2.0.0"}
