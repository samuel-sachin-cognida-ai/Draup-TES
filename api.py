"""
api.py — entry point for uvicorn.

Run with:
    uvicorn api:app --reload --port 8000

All application logic lives in the api/ package.
"""
from api import app  # noqa: F401 — uvicorn looks for `app` in this module

__all__ = ["app"]
