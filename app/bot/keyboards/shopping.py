from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import ShoppingItem

SHOPPING_MENU_CALLBACK = "shopping:menu"
ADD_SHOPPING_ITEM_CALLBACK = "shopping:add"
SHOPPING_CANCEL_CALLBACK = "shopping:cancel"


def build_shopping_keyboard(items: list[ShoppingItem]) -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton(text="Добавить", callback_data=ADD_SHOPPING_ITEM_CALLBACK)]]
    active_index = 1
    for item in items:
        if item.status != "ACTIVE":
            continue

        keyboard.append(
            [InlineKeyboardButton(text=f"Куплено #{active_index}", callback_data=f"shopping:bought:{item.id}")]
        )
        active_index += 1

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_shopping_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data=SHOPPING_CANCEL_CALLBACK)],
        ]
    )
