"""Pydantic request/response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    role: str = Field(
        ..., min_length=1,
        description="User's role, e.g. 'Clinical Documentation Specialist'",
    )
    tasks: list[str] = Field(
        ..., min_items=1,
        description="List of tasks the user needs to perform",
    )
    vendor: str | None = Field(
        None,
        description="Optional filter: 'Anthropic' or 'OpenAI'. If omitted, returns all vendors.",
    )
