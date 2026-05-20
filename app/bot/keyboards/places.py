from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.blocks import with_close_button
from app.models import PlaceItem
from app.services.chat_blocks import PLACES_BLOCK_KEY
from app.services.places import CATEGORY_LABELS, PlaceCategory

PLACES_MENU_CALLBACK = "places:menu"
ADD_PLACE_CALLBACK = "places:add"
PLACES_PLANNED_CALLBACK = "places:list:planned"
PLACES_VISITED_CALLBACK = "places:list:visited"
PLACES_CANCEL_CALLBACK = "places:cancel"


def build_places_keyboard() -> InlineKeyboardMarkup:
    return build_places_menu()


def build_places_menu() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Добавить место", callback_data=ADD_PLACE_CALLBACK)],
                [
                    InlineKeyboardButton(text="В планах", callback_data=PLACES_PLANNED_CALLBACK),
                    InlineKeyboardButton(text="Посещённые", callback_data=PLACES_VISITED_CALLBACK),
                ],
            ]
        ),
        PLACES_BLOCK_KEY,
    )


def build_place_category_keyboard() -> InlineKeyboardMarkup:
    rows = []
    categories = list(PlaceCategory)
    for index in range(0, len(categories), 2):
        rows.append(
            [
                InlineKeyboardButton(
                    text=CATEGORY_LABELS[category],
                    callback_data=f"places:create:category:{category.value.lower()}",
                )
                for category in categories[index : index + 2]
            ]
        )

    rows.append([InlineKeyboardButton(text="Назад", callback_data=PLACES_MENU_CALLBACK)])
    return with_close_button(InlineKeyboardMarkup(inline_keyboard=rows), PLACES_BLOCK_KEY)


def build_place_list_keyboard(items: list[PlaceItem]) -> InlineKeyboardMarkup:
    keyboard = []
    for index, item in enumerate(items, start=1):
        if item.status == "VISITED":
            keyboard.append(
                [
                    InlineKeyboardButton(text=f"Оценить #{index}", callback_data=f"places:rate:{item.id}"),
                    InlineKeyboardButton(text=f"Комментарий #{index}", callback_data=f"places:comment:{item.id}"),
                ]
            )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(text=f"Посетили #{index}", callback_data=f"places:visit:{item.id}"),
                ]
            )

    keyboard.append([InlineKeyboardButton(text="Назад к местам", callback_data=PLACES_MENU_CALLBACK)])
    return with_close_button(InlineKeyboardMarkup(inline_keyboard=keyboard), PLACES_BLOCK_KEY)


def build_place_cancel_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отмена", callback_data=PLACES_CANCEL_CALLBACK)],
            ]
        ),
        PLACES_BLOCK_KEY,
    )


def build_place_rating_keyboard(place_id: int | None = None) -> InlineKeyboardMarkup:
    rows = []
    for start in (1, 6):
        rows.append(
            [
                InlineKeyboardButton(text=str(score), callback_data=f"places:score:{score}")
                for score in range(start, start + 5)
            ]
        )
    if place_id is not None:
        rows.append([InlineKeyboardButton(text="Поставить позже", callback_data=PLACES_MENU_CALLBACK)])
    return with_close_button(InlineKeyboardMarkup(inline_keyboard=rows), PLACES_BLOCK_KEY)
