from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ui_backend.api import create_router


_DEFAULT_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}


def _configure_cors(app: FastAPI) -> None:
    raw = os.environ.get("UI_BACKEND_ALLOWED_ORIGINS")
    if raw:
        origins = {origin.strip() for origin in raw.split(",") if origin.strip()}
    else:
        origins = set(_DEFAULT_ORIGINS)

    if not origins:
        origins = {"*"}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def create_app() -> FastAPI:
    app = FastAPI()
    _configure_cors(app)
    app.include_router(create_router(), prefix="/api")
    return app


app = create_app()
