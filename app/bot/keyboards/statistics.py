from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.blocks import with_close_button
from app.services.chat_blocks import STATISTICS_BLOCK_KEY

STATISTICS_WEEK_CALLBACK = "statistics:week"
STATISTICS_MONTH_CALLBACK = "statistics:month"


def build_statistics_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Неделя", callback_data=STATISTICS_WEEK_CALLBACK),
                    InlineKeyboardButton(text="Месяц", callback_data=STATISTICS_MONTH_CALLBACK),
                ],
            ]
        ),
        STATISTICS_BLOCK_KEY,
    )
