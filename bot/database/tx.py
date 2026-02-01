# bot/database/tx.py
from __future__ import annotations

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def transactional(session: AsyncSession):
    """
    Safe transactional context for SQLAlchemy 2.x autobegin.

    - If a transaction is already active, use SAVEPOINT (begin_nested)
    - Otherwise, start a new transaction
    """
    if session.in_transaction():
        async with session.begin_nested():
            yield
    else:
        async with session.begin():
            yield
