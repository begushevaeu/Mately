from aiogram.types import InlineKeyboardMarkup

from app.bot.keyboards.blocks import build_close_block_keyboard
from app.services.chat_blocks import PLACES_BLOCK_KEY


def build_places_keyboard() -> InlineKeyboardMarkup:
    return build_close_block_keyboard(PLACES_BLOCK_KEY)
