# bot/main.py
import asyncio
import contextlib
import logging

from aiogram import Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import Settings
from bot.database import Database

# IMPORTANT: register models
from bot.database.models import *  # noqa: F401,F403

from bot.handlers import router as handlers_router
from bot.scheduler import setup_scheduler
from bot.services.poll_scheduler import poll_scheduler_loop
from bot.utils.middleware import DbSessionMiddleware

# ✅ NEW: auto-delete bot messages + delete user commands in main group
from bot.utils.autodelete_bot import AutoDeleteBot
from bot.utils.autodelete_commands_mw import AutoDeleteCommandsMiddleware


def setup_logging(is_dev: bool) -> None:
    """
    Clean production logging:
    - app logs: INFO (or DEBUG in dev)
    - SQLAlchemy logs: WARNING+ (no query/pool spam)
    """
    app_level = logging.DEBUG if is_dev else logging.INFO

    logging.basicConfig(
        level=app_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    for name in (
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        "alembic",
        "asyncpg",
        "aiosqlite",
        "psycopg",
        "psycopg2",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


async def main() -> None:
    settings = Settings.load()
    setup_logging(settings.is_dev)
    log = logging.getLogger("bot")

    db = Database(settings.database_url)
    await db.init_models()
    log.info("DB initialized")

    # ✅ IMPORTANT: use AutoDeleteBot (NOT aiogram.Bot)
    bot = AutoDeleteBot(
        token=settings.bot_token,
        settings=settings,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # ✅ sanity log: must print "AutoDeleteBot"
    log.info("Bot class: %s", bot.__class__.__name__)

    dp = Dispatcher()

    # Inject workflow data
    dp.workflow_data["settings"] = settings
    dp.workflow_data["db"] = db

    # DB session per update
    dp.update.middleware(DbSessionMiddleware(db))

    # ✅ delete user command messages (/quiz, /leaderboard, etc.) in MAIN GROUP after 60s
    dp.message.middleware(AutoDeleteCommandsMiddleware(settings, delay_seconds=60))

    # Include routers (admin/user/common)
    dp.include_router(handlers_router)

    # APScheduler (your existing)
    scheduler = setup_scheduler(bot=bot, db=db, settings=settings)
    log.info("Scheduler started")

    # Poll scheduler loop
    poll_task = asyncio.create_task(poll_scheduler_loop(bot, db, interval_seconds=15))
    log.info("Poll scheduler loop started")

    try:
        await dp.start_polling(bot)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    except Exception:
        log.exception("Bot crashed")
        raise
    finally:
        # Stop poll loop
        try:
            poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poll_task
        except Exception:
            log.exception("Failed to cancel poll loop")

        # Stop scheduler
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            log.exception("Failed to shutdown scheduler")

        # Close DB + bot session
        try:
            await db.close()
        except Exception:
            log.exception("Failed to close DB")

        try:
            await bot.session.close()
        except Exception:
            log.exception("Failed to close bot session")


if __name__ == "__main__":
    asyncio.run(main())
