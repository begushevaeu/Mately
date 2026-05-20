from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CLOSE_BLOCK_CALLBACK_PREFIX = "blocks:close:"
CLOSE_BLOCK_BUTTON_TEXT = "Закрыть"


def close_block_callback(block_key: str) -> str:
    return f"{CLOSE_BLOCK_CALLBACK_PREFIX}{block_key}"


def parse_close_block_callback(data: str) -> str | None:
    if not data.startswith(CLOSE_BLOCK_CALLBACK_PREFIX):
        return None
    return data.removeprefix(CLOSE_BLOCK_CALLBACK_PREFIX)


def build_close_block_button(block_key: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=CLOSE_BLOCK_BUTTON_TEXT, callback_data=close_block_callback(block_key))


def with_close_button(markup: InlineKeyboardMarkup, block_key: str) -> InlineKeyboardMarkup:
    keyboard = [list(row) for row in markup.inline_keyboard]
    keyboard.append([build_close_block_button(block_key)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_close_block_keyboard(block_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[build_close_block_button(block_key)]])
