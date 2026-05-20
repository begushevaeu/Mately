from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.blocks import with_close_button
from app.models import ShoppingItem
from app.services.chat_blocks import SHOPPING_BLOCK_KEY

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

    return with_close_button(InlineKeyboardMarkup(inline_keyboard=keyboard), SHOPPING_BLOCK_KEY)


def build_shopping_cancel_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отмена", callback_data=SHOPPING_CANCEL_CALLBACK)],
            ]
        ),
        SHOPPING_BLOCK_KEY,
    )
