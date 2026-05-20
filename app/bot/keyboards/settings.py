from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.additional import build_back_to_additional_button
from app.bot.keyboards.blocks import with_close_button
from app.services.chat_blocks import ADDITIONAL_BLOCK_KEY

SETUP_PARTNER_ALIAS_CALLBACK = "settings:partner_alias"


def build_settings_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Настроить имя партнера", callback_data=SETUP_PARTNER_ALIAS_CALLBACK)],
                [build_back_to_additional_button()],
            ]
        ),
        ADDITIONAL_BLOCK_KEY,
    )
