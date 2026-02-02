from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AppConfig


CONFIG_ID = 1


@dataclass(frozen=True, slots=True)
class ConfigDTO:
    screenshot_enabled: bool
    screenshot_points: int
    screenshot_claim_ttl_minutes: int


async def get_or_create_config(session: AsyncSession) -> AppConfig:
    res = await session.execute(select(AppConfig).where(AppConfig.id == CONFIG_ID))
    cfg = res.scalar_one_or_none()
    if cfg:
        return cfg

    cfg = AppConfig(id=CONFIG_ID)
    session.add(cfg)
    await session.flush()
    return cfg


async def get_config(session: AsyncSession) -> ConfigDTO:
    cfg = await get_or_create_config(session)
    return ConfigDTO(
        screenshot_enabled=bool(cfg.screenshot_enabled),
        screenshot_points=int(cfg.screenshot_points),
        screenshot_claim_ttl_minutes=int(cfg.screenshot_claim_ttl_minutes),
    )


async def set_screenshot_enabled(session: AsyncSession, enabled: bool) -> None:
    await get_or_create_config(session)
    await session.execute(
        update(AppConfig).where(AppConfig.id == CONFIG_ID).values(screenshot_enabled=enabled)
    )


async def set_screenshot_points(session: AsyncSession, points: int) -> None:
    await get_or_create_config(session)
    await session.execute(
        update(AppConfig).where(AppConfig.id == CONFIG_ID).values(screenshot_points=points)
    )


async def set_screenshot_ttl_minutes(session: AsyncSession, minutes: int) -> None:
    await get_or_create_config(session)
    await session.execute(
        update(AppConfig)
        .where(AppConfig.id == CONFIG_ID)
        .values(screenshot_claim_ttl_minutes=minutes)
    )
