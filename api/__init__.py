"""api — FastAPI application package.

Import routes to register all handlers, then expose the app instance
so `uvicorn api:app` works without changes.
"""
from api.app import app
import api.routes  # noqa: F401 — registers all route handlers

__all__ = ["app"]
