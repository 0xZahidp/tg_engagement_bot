# bot/config/settings.py
from __future__ import annotations

import os
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


def _parse_int_list(raw: str, key_name: str) -> list[int]:
    raw = raw.strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    out: list[int] = []
    for p in parts:
        if not p:
            continue
        out.append(_to_int(p, key_name))
    return out


@dataclass(frozen=True, slots=True)
class Settings:
    # required
    bot_token: str

    # optional (will be required later by specific features)
    database_url: str = "sqlite+aiosqlite:///./bot.db"

    # security/admin
    root_admin_ids: tuple[int, ...] = ()

    # telegram targets (optional for now)
    group_id: Optional[int] = None              # main community group/channel (leaderboard posts, cards, etc.)
    admin_review_chat_id: Optional[int] = None  # where approvals can be routed (optional)

    # scheduler / time
    timezone: str = "UTC"

    # environment mode
    environment: str = "production"  # or "development"

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

        database_url = env.get("DATABASE_URL", "sqlite+aiosqlite:///./bot.db").strip()

        root_admin_ids_raw = env.get("ROOT_ADMIN_IDS", "").strip()
        root_admin_ids_list = _parse_int_list(root_admin_ids_raw, "ROOT_ADMIN_IDS")

        group_id_raw = env.get("GROUP_ID", "").strip()
        group_id = _to_int(group_id_raw, "GROUP_ID") if group_id_raw else None

        admin_review_chat_id_raw = env.get("ADMIN_REVIEW_CHAT_ID", "").strip()
        admin_review_chat_id = (
            _to_int(admin_review_chat_id_raw, "ADMIN_REVIEW_CHAT_ID")
            if admin_review_chat_id_raw
            else None
        )

        timezone = env.get("TIMEZONE", "UTC").strip() or "UTC"
        environment = env.get("ENVIRONMENT", "production").strip() or "production"

        return cls(
            bot_token=bot_token,
            database_url=database_url,
            root_admin_ids=tuple(root_admin_ids_list),
            group_id=group_id,
            admin_review_chat_id=admin_review_chat_id,
            timezone=timezone,
            environment=environment,
        )
