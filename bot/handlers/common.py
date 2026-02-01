# bot/handlers/common.py
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Welcome!\n\n"
        "Use /help to see commands.\n"
        "Use /whoami to check your account (DB-backed)."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📌 Available commands:\n"
        "/start — welcome\n"
        "/help — help\n"
        "/whoami — your DB profile + role\n\n"
        "You can also use the menu buttons."
    )
