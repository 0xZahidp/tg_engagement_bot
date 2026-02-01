# bot/keyboards/main.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BTN_CHECKIN = "✅ Check-in"
BTN_STATUS = "📌 Status"
BTN_QUIZ = "🧠 Quiz"
BTN_POLL = "📊 Poll"
BTN_SCREENSHOT = "🖼 Screenshot"
BTN_SPIN = "🎰 Spin"
BTN_LEADERBOARD = "🏆 Leaderboard"


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CHECKIN), KeyboardButton(text=BTN_STATUS)],
            [KeyboardButton(text=BTN_QUIZ), KeyboardButton(text=BTN_POLL)],
            [KeyboardButton(text=BTN_SCREENSHOT), KeyboardButton(text=BTN_SPIN)],
            [KeyboardButton(text=BTN_LEADERBOARD)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose an action…",
        selective=False,
        one_time_keyboard=False,
    )
