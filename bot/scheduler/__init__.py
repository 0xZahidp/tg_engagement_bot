# bot/scheduler/__init__.py
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from bot.config.settings import Settings
from bot.scheduler.jobs import build_scheduler


def setup_scheduler(bot: Bot, db, settings: Settings) -> AsyncIOScheduler:
    scheduler = build_scheduler(bot=bot, db=db, settings=settings)
    scheduler.start()
    return scheduler
