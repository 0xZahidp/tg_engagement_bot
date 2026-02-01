from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from bot.keyboards.main import (
    main_menu_kb,
    BTN_QUIZ, BTN_POLL, BTN_SCREENSHOT, BTN_SPIN, BTN_LEADERBOARD
)

router = Router()

STUBS = {
    BTN_QUIZ: "🧠 Quiz is coming next. (Step 7)",
    BTN_POLL: "📊 Poll automation is coming later. (Step 8)",
    BTN_SCREENSHOT: "🖼 Screenshot approvals are coming later. (Step 9)",
    BTN_SPIN: "🎰 Spin unlock is coming later. (Step 10)",
    BTN_LEADERBOARD: "🏆 Leaderboard is coming later. (Step 11)",
}

@router.message(lambda m: (m.text or "").strip() in STUBS)
async def stub(message: Message) -> None:
    key = (message.text or "").strip()
    await message.answer(STUBS[key], reply_markup=main_menu_kb())
