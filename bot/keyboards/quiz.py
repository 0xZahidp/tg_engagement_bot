# bot/keyboards/quiz.py
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def quiz_kb(*, quiz_id: int, options: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    """
    options = [(option_id, option_text), ...]
    """
    kb = InlineKeyboardBuilder()
    for option_id, text in options:
        kb.add(
            InlineKeyboardButton(
                text=text,
                callback_data=f"quiz:{quiz_id}:{option_id}",
            )
        )
    kb.adjust(1)
    return kb.as_markup()
