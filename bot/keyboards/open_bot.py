from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def open_bot_kb(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➡️ Open Bot",
                    url=f"https://t.me/{bot_username}",
                )
            ]
        ]
    )
