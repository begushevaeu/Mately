from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.blocks import with_close_button
from app.services.chat_blocks import SETTINGS_BLOCK_KEY

SETUP_PARTNER_ALIAS_CALLBACK = "settings:partner_alias"


def build_settings_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Настроить имя партнера", callback_data=SETUP_PARTNER_ALIAS_CALLBACK)]
            ]
        ),
        SETTINGS_BLOCK_KEY,
    )
