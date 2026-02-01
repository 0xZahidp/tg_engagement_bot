# bot/config/__init__.py
from __future__ import annotations

from .settings import Settings

# Load once at import time (fail-fast if BOT_TOKEN missing)
settings = Settings.load()

__all__ = ["Settings", "settings"]
