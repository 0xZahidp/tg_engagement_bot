from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from bot.keyboards.main import (
    main_menu_kb,
    BTN_QUIZ, BTN_POLL, BTN_SCREENSHOT, BTN_SPIN, BTN_LEADERBOARD
)

router = Router()

STUBS = {
    
}

@router.message(lambda m: (m.text or "").strip() in STUBS)
async def stub(message: Message) -> None:
    key = (message.text or "").strip()
    await message.answer(STUBS[key], reply_markup=main_menu_kb())
