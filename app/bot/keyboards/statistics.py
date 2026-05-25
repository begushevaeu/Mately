from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.additional import build_back_to_additional_button
from app.bot.keyboards.blocks import with_close_button
from app.services.chat_blocks import ADDITIONAL_BLOCK_KEY

STATISTICS_WEEK_CALLBACK = "statistics:week"
STATISTICS_MONTH_CALLBACK = "statistics:month"


def build_statistics_keyboard(*, current_period: str = "week") -> InlineKeyboardMarkup:
    period_buttons = []
    if current_period != "week":
        period_buttons.append(InlineKeyboardButton(text="Неделя", callback_data=STATISTICS_WEEK_CALLBACK))
    if current_period != "month":
        period_buttons.append(InlineKeyboardButton(text="Месяц", callback_data=STATISTICS_MONTH_CALLBACK))

    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                period_buttons,
                [build_back_to_additional_button()],
            ]
        ),
        ADDITIONAL_BLOCK_KEY,
    )
