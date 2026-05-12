"""Shared mutable state for the crawler (avoids circular imports)."""

stop_requested: bool = False
