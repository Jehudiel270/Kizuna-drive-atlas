"""KIZUNA ATLAS — API d'analyse du protocole de recherche KIZUNA DRIVE (ICPM Challenge 2026)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp

from .config import get_settings
from .db import create_all, session_scope
from .routers import analysis, auth, config, ingest, quali, report, snapshots
from .security import bootstrap_admin

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    with session_scope() as db:
        bootstrap_admin(db)
    yield


def create_app() -> ASGIApp:
    s = get_settings()
    app = FastAPI(title="KIZUNA ATLAS API", version=VERSION, lifespan=lifespan, docs_url="/docs", redoc_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/health", tags=["système"])
    def health():
        return {"status": "ok", "version": VERSION, "demo": s.demo_mode}

    for r in (auth, ingest, config, analysis, quali, snapshots, report):
        app.include_router(r.router)
    # Wrapping FastAPI ensures CORS headers are applied to unhandled 500 responses too.
    return CORSMiddleware(app=app, allow_origins=s.cors_origins, allow_origin_regex=s.cors_origin_regex or None, allow_credentials=False,
                          allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition"])


app = create_app()
