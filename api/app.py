"""FastAPI application factory — creates and configures the app instance."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db
import llm_client as llm
from logging_config import setup_logging

log = logging.getLogger("tes.api")

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

app = FastAPI(
    title="Healthcare AI Tool Recommender",
    version="4.0.0",
    description=(
        "Recommends Claude for Healthcare and ChatGPT for Healthcare tools "
        "for given roles and tasks. Results are cached by (role, task) pair."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    setup_logging()
    log.info("API server starting up ...")
    db.init_db()
    log.info("LLM base_url=%s", llm.LLM_BASE_URL)
    log.info("LLM model=%s", LLM_MODEL)
    log.info("API server ready — all routes registered")


# ── Serve UI (must be registered after all API routes) ────────────────────────
_UI_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
if os.path.isdir(_UI_DIR):
    app.mount("/ui", StaticFiles(directory=_UI_DIR, html=True), name="ui")

    @app.get("/", include_in_schema=False)
    def serve_root():
        return FileResponse(os.path.join(_UI_DIR, "index.html"))
