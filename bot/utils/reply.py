from __future__ import annotations

from aiogram.types import Message

from bot.keyboards.main import main_menu_kb


async def reply_safe(message: Message, text: str, **kwargs) -> None:
    """
    Safe reply helper:
    - By default, attaches main_menu_kb()
    - Allows callers to override reply_markup by passing reply_markup=...
    """
    kwargs.setdefault("reply_markup", main_menu_kb())
    await message.answer(text, **kwargs)