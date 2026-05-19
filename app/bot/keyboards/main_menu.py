from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

TASKS_BUTTON = "📋 Задачи"
CONTENT_BUTTON = "🎬 Контент"
SHOPPING_BUTTON = "🛒 Покупки"
STATISTICS_BUTTON = "📊 Статистика"
SETTINGS_BUTTON = "⚙️ Настройки"


def build_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TASKS_BUTTON), KeyboardButton(text=CONTENT_BUTTON)],
            [KeyboardButton(text=SHOPPING_BUTTON), KeyboardButton(text=STATISTICS_BUTTON)],
            [KeyboardButton(text=SETTINGS_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел",
    )
