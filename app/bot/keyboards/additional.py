from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.blocks import with_close_button
from app.services.chat_blocks import ADDITIONAL_BLOCK_KEY

ADDITIONAL_MENU_CALLBACK = "additional:menu"
ADDITIONAL_STATISTICS_CALLBACK = "additional:statistics"
ADDITIONAL_SETTINGS_CALLBACK = "additional:settings"
ADDITIONAL_EXPORT_CALLBACK = "additional:export"


def build_additional_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Статистика", callback_data=ADDITIONAL_STATISTICS_CALLBACK)],
                [InlineKeyboardButton(text="📤 Экспорт", callback_data=ADDITIONAL_EXPORT_CALLBACK)],
                [InlineKeyboardButton(text="⚙️ Настройки", callback_data=ADDITIONAL_SETTINGS_CALLBACK)],
            ]
        ),
        ADDITIONAL_BLOCK_KEY,
    )


def build_back_to_additional_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="Назад к дополнительному", callback_data=ADDITIONAL_MENU_CALLBACK)
