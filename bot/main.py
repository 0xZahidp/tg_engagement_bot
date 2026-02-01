# bot/main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import Settings
from bot.database import Database

# IMPORTANT: register models
from bot.database.models import *  # noqa: F401,F403

from bot.utils.middleware import DbSessionMiddleware
from bot.handlers import router as handlers_router


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

    # Silence SQLAlchemy + migrations noise
    for name in (
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        "alembic",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    # DB drivers can be chatty too
    for name in ("asyncpg", "aiosqlite", "psycopg", "psycopg2"):
        logging.getLogger(name).setLevel(logging.WARNING)


async def main() -> None:
    settings = Settings.load()
    setup_logging(settings.is_dev)
    log = logging.getLogger("bot")

    db = Database(settings.database_url)
    await db.init_models()
    log.info("DB initialized")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Inject Settings to handlers
    dp.workflow_data["settings"] = settings

    # DB session per update
    dp.update.middleware(DbSessionMiddleware(db))

    # Include routers
    dp.include_router(handlers_router)

    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        # Normal shutdown path on Ctrl+C / cancellation
        pass
    except KeyboardInterrupt:
        # Some environments raise this explicitly
        pass
    except Exception:
        log.exception("Bot crashed")
        raise
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
