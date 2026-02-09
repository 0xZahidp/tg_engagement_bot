# bot/config/settings.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


def _require(env: dict[str, str], key: str) -> str:
    v = env.get(key)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {key}")
    return v.strip()


def _to_int(value: str, key_name: str) -> int:
    try:
        return int(value)
    except ValueError as e:
        raise RuntimeError(f"Invalid integer for {key_name}: {value!r}") from e


def _parse_int_list(raw: str | None, key_name: str) -> list[int]:
    """
    Parses comma/space/newline separated ints.
    Accepts:
      "951258732"
      "951258732,123"
      "951258732 123"
      "951258732\n123"
      "[951258732, 123]"  (brackets ignored)
    """
    if not raw:
        return []

    # remove common bracket wrappers
    cleaned = raw.strip().strip("[](){}").strip()
    if not cleaned:
        return []

    # split by comma OR any whitespace
    parts = [p for p in re.split(r"[,\s]+", cleaned) if p]

    out: list[int] = []
    for p in parts:
        # extra safety: strip any stray quotes
        p2 = p.strip().strip("'\"")
        if not p2:
            continue
        out.append(_to_int(p2, key_name))
    return out


@dataclass(frozen=True, slots=True)
class Settings:
    # --- required ---
    bot_token: str
    bot_username: str  # required for deep links

    # --- optional ---
    database_url: str = "sqlite+aiosqlite:///./bot.db"

    # --- security / admin ---
    root_admin_ids: tuple[int, ...] = ()

    # --- telegram targets ---
    group_id: Optional[int] = None
    admin_review_chat_id: Optional[int] = None

    # --- scheduler / time ---
    timezone: str = "UTC"

    # --- environment ---
    environment: str = "production"  # production | development

    @property
    def is_dev(self) -> bool:
        return self.environment.lower() in {"dev", "development", "local"}

    @classmethod
    def load(cls) -> "Settings":
        """
        Loads from process env (and .env if present).
        Fails fast for required fields.
        """
        load_dotenv()
        env = os.environ

        bot_token = _require(env, "BOT_TOKEN")
        bot_username = _require(env, "BOT_USERNAME")

        database_url = (env.get("DATABASE_URL") or "sqlite+aiosqlite:///./bot.db").strip()

        root_admin_ids = tuple(_parse_int_list(env.get("ROOT_ADMIN_IDS"), "ROOT_ADMIN_IDS"))

        group_id_raw = (env.get("GROUP_ID") or "").strip()
        group_id = _to_int(group_id_raw, "GROUP_ID") if group_id_raw else None

        admin_review_chat_id_raw = (env.get("ADMIN_REVIEW_CHAT_ID") or "").strip()
        admin_review_chat_id = (
            _to_int(admin_review_chat_id_raw, "ADMIN_REVIEW_CHAT_ID")
            if admin_review_chat_id_raw
            else None
        )

        timezone = (env.get("TIMEZONE") or "UTC").strip() or "UTC"
        environment = (env.get("ENVIRONMENT") or "production").strip() or "production"

        return cls(
            bot_token=bot_token,
            bot_username=bot_username,
            database_url=database_url,
            root_admin_ids=root_admin_ids,
            group_id=group_id,
            admin_review_chat_id=admin_review_chat_id,
            timezone=timezone,
            environment=environment,
        )