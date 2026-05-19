from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SETUP_PARTNER_ALIAS_CALLBACK = "settings:partner_alias"


def build_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Настроить имя партнера", callback_data=SETUP_PARTNER_ALIAS_CALLBACK)]
        ]
    )
