from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.additional import build_back_to_additional_button
from app.bot.keyboards.blocks import with_close_button
from app.models import CoupleReminderSettings
from app.services.chat_blocks import ADDITIONAL_BLOCK_KEY

SETUP_PARTNER_ALIAS_CALLBACK = "settings:partner_alias"
TOGGLE_MORNING_REMINDER_CALLBACK = "settings:reminders:morning:toggle"
SET_MORNING_REMINDER_TIME_CALLBACK = "settings:reminders:morning:time"
TOGGLE_EVENING_REMINDER_CALLBACK = "settings:reminders:evening:toggle"
SET_EVENING_REMINDER_TIME_CALLBACK = "settings:reminders:evening:time"
TOGGLE_REMINDERS_PAUSE_CALLBACK = "settings:reminders:pause:toggle"


def build_settings_keyboard(settings: CoupleReminderSettings | None = None) -> InlineKeyboardMarkup:
    morning_enabled = settings.morning_enabled if settings is not None else True
    evening_enabled = settings.evening_enabled if settings is not None else True
    reminders_paused = settings.reminders_paused if settings is not None else False
    morning_label = "Утро: включено" if morning_enabled else "Утро: выключено"
    evening_label = "Вечер: включено" if evening_enabled else "Вечер: выключено"
    pause_label = "Возобновить напоминания" if reminders_paused else "Пауза для напоминаний"
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=morning_label, callback_data=TOGGLE_MORNING_REMINDER_CALLBACK)],
                [InlineKeyboardButton(text="Время утреннего дайджеста", callback_data=SET_MORNING_REMINDER_TIME_CALLBACK)],
                [InlineKeyboardButton(text=evening_label, callback_data=TOGGLE_EVENING_REMINDER_CALLBACK)],
                [InlineKeyboardButton(text="Время вечерней сверки", callback_data=SET_EVENING_REMINDER_TIME_CALLBACK)],
                [InlineKeyboardButton(text=pause_label, callback_data=TOGGLE_REMINDERS_PAUSE_CALLBACK)],
                [InlineKeyboardButton(text="Настроить имя партнера", callback_data=SETUP_PARTNER_ALIAS_CALLBACK)],
                [build_back_to_additional_button()],
            ]
        ),
        ADDITIONAL_BLOCK_KEY,
    )
