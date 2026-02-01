# bot/database/session.py
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bot.database.base import Base


def _apply_sqlite_pragmas(dbapi_connection) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")  # 5s
    cursor.close()


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        is_sqlite = database_url.startswith("sqlite")

        self.engine: AsyncEngine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"timeout": 30} if is_sqlite else {},
        )

        if is_sqlite:
            @event.listens_for(self.engine.sync_engine, "connect")
            def _on_connect(dbapi_connection, _connection_record) -> None:  # type: ignore[no-redef]
                _apply_sqlite_pragmas(dbapi_connection)

        self.SessionLocal = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )

    async def init_models(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.SessionLocal() as s:
            yield s
