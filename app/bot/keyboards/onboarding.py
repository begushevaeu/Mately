from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

CREATE_COUPLE_BUTTON = "Создать пару"
ENTER_INVITE_CODE_BUTTON = "Ввести код"
REFRESH_STATUS_BUTTON = "Обновить статус"
CANCEL_BUTTON = "Отмена"


def build_onboarding_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CREATE_COUPLE_BUTTON)],
            [KeyboardButton(text=ENTER_INVITE_CODE_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Создайте пару или введите код",
    )


def build_waiting_for_partner_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=REFRESH_STATUS_BUTTON)],
            [KeyboardButton(text=ENTER_INVITE_CODE_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Партнер вводит ваш код у себя в боте",
    )


def build_cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON)]],
        resize_keyboard=True,
        input_field_placeholder="Введите код приглашения",
    )
