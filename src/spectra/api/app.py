"""FastAPI application factory."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from spectra import __version__
from spectra.api.v1 import api_router
from spectra.core.db import init_db
from spectra.core.logging import setup_logging


def create_app() -> FastAPI:
    setup_logging()
    init_db()
    app = FastAPI(
        title="Spectra API",
        version=__version__,
        description=(
            "AI-native security research platform API. "
            "PolicyEngine is the sole execution gate. "
            "The web UI cannot execute arbitrary commands."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal error", "code": "internal", "request_id": rid},
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": "Spectra", "version": __version__, "api": "/api/v1/health"}

    return app


app = create_app()
