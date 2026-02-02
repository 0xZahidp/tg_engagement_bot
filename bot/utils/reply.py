# bot/utils/reply.py
from aiogram.types import Message
from bot.keyboards.main import main_menu_kb


async def reply_safe(
    message: Message,
    text: str,
    **kwargs,
):
    """
    Send message with main menu ONLY in private chat.
    Groups will never receive reply keyboards.
    """
    if message.chat.type == "private":
        await message.answer(text, reply_markup=main_menu_kb(), **kwargs)
    else:
        await message.answer(text, **kwargs)
