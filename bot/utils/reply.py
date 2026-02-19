# bot/utils/reply.py
from __future__ import annotations

from aiogram.types import Message

from bot.keyboards.main import main_menu_kb


async def reply_safe(message: Message, text: str, **kwargs) -> None:
    """
    Safe reply helper:
    - Attach menu ONLY in private (or only in group, depending on your rule)
    """
    # ✅ If you want COMMANDS-ONLY in GROUP: do NOT attach ReplyKeyboard in groups.
    if message.chat.type == "private":
        kwargs.setdefault("reply_markup", main_menu_kb())
    else:
        # ensure no reply keyboard is sent in groups
        kwargs.setdefault("reply_markup", None)

    await message.answer(text, **kwargs)
