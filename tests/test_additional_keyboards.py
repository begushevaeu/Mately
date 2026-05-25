from app.bot.keyboards.additional import (
    ADDITIONAL_SETTINGS_CALLBACK,
    ADDITIONAL_STATISTICS_CALLBACK,
    build_additional_keyboard,
)
from app.bot.keyboards.blocks import close_block_callback
from app.bot.keyboards.settings import (
    SET_EVENING_REMINDER_TIME_CALLBACK,
    SET_MORNING_REMINDER_TIME_CALLBACK,
    TOGGLE_EVENING_REMINDER_CALLBACK,
    TOGGLE_MORNING_REMINDER_CALLBACK,
    TOGGLE_REMINDERS_PAUSE_CALLBACK,
    build_settings_keyboard,
)
from app.bot.keyboards.statistics import build_statistics_keyboard
from app.services.chat_blocks import ADDITIONAL_BLOCK_KEY


def extract_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_additional_menu_contains_statistics_settings_and_close() -> None:
    buttons = extract_buttons(build_additional_keyboard())

    assert [button.text for button in buttons] == ["📊 Статистика", "⚙️ Настройки", "Закрыть"]
    assert buttons[0].callback_data == ADDITIONAL_STATISTICS_CALLBACK
    assert buttons[1].callback_data == ADDITIONAL_SETTINGS_CALLBACK
    assert buttons[2].callback_data == close_block_callback(ADDITIONAL_BLOCK_KEY)


def test_nested_additional_keyboards_close_the_additional_block() -> None:
    settings_buttons = extract_buttons(build_settings_keyboard())
    statistics_buttons = extract_buttons(build_statistics_keyboard())

    assert settings_buttons[-1].callback_data == close_block_callback(ADDITIONAL_BLOCK_KEY)
    assert statistics_buttons[-1].callback_data == close_block_callback(ADDITIONAL_BLOCK_KEY)


def test_settings_keyboard_contains_reminder_controls() -> None:
    buttons = extract_buttons(build_settings_keyboard())
    callback_data = [button.callback_data for button in buttons]

    assert TOGGLE_MORNING_REMINDER_CALLBACK in callback_data
    assert SET_MORNING_REMINDER_TIME_CALLBACK in callback_data
    assert TOGGLE_EVENING_REMINDER_CALLBACK in callback_data
    assert SET_EVENING_REMINDER_TIME_CALLBACK in callback_data
    assert TOGGLE_REMINDERS_PAUSE_CALLBACK in callback_data
