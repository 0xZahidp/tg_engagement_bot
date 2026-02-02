# bot/keyboards/admin.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def admin_panel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧠 Quiz Admin"), KeyboardButton(text="📊 Poll Admin")],
            [KeyboardButton(text="🖼 Screenshot Admin"), KeyboardButton(text="⚙️ Settings")],
            [KeyboardButton(text="⬅️ Back to Menu")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Admin panel…",
        selective=False,
        one_time_keyboard=False,
    )
