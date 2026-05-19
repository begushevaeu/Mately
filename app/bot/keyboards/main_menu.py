from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def build_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Задачи"), KeyboardButton(text="🎬 Контент")],
            [KeyboardButton(text="🛒 Покупки"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел",
    )
