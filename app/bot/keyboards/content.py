from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.keyboards.blocks import with_close_button
from app.models import ContentItem
from app.services.chat_blocks import CONTENT_BLOCK_KEY
from app.services.content import CATEGORY_LABELS, CONTENT_REACTIONS, ContentCategory

CONTENT_MENU_CALLBACK = "content:menu"
ADD_CONTENT_CALLBACK = "content:add"
CONTENT_PLANNED_CALLBACK = "content:list:planned"
CONTENT_COMPLETED_CALLBACK = "content:list:completed"
CONTENT_FILTERS_CALLBACK = "content:filters"
CONTENT_FILTER_CATEGORIES_CALLBACK = "content:filters:categories"
CONTENT_FILTER_RATING_HIGH_CALLBACK = "content:filters:rating:high"
CONTENT_FILTER_RATING_MID_CALLBACK = "content:filters:rating:mid"
CONTENT_FILTER_RATING_LOW_CALLBACK = "content:filters:rating:low"
CONTENT_FILTER_TODAY_CALLBACK = "content:filters:completed:today"
CONTENT_FILTER_WEEK_CALLBACK = "content:filters:completed:week"
CONTENT_FILTER_MONTH_CALLBACK = "content:filters:completed:month"
CONTENT_CANCEL_CALLBACK = "content:cancel"
CONTENT_EMOJI_SKIP_CALLBACK = "content:emoji:skip"


def build_content_menu() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Добавить контент", callback_data=ADD_CONTENT_CALLBACK)],
                [
                    InlineKeyboardButton(text="В планах", callback_data=CONTENT_PLANNED_CALLBACK),
                    InlineKeyboardButton(text="Завершённое", callback_data=CONTENT_COMPLETED_CALLBACK),
                ],
                [InlineKeyboardButton(text="Фильтры", callback_data=CONTENT_FILTERS_CALLBACK)],
            ]
        ),
        CONTENT_BLOCK_KEY,
    )


def build_content_category_keyboard(*, mode: str) -> InlineKeyboardMarkup:
    rows = []
    categories = list(ContentCategory)
    for index in range(0, len(categories), 2):
        row = []
        for category in categories[index : index + 2]:
            prefix = "content:create:category" if mode == "create" else "content:filter:category"
            text = CATEGORY_LABELS[category]
            if mode == "create":
                text = f"Добавить {text}"
            row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"{prefix}:{category.value.lower()}",
                )
            )
        rows.append(row)

    rows.append([InlineKeyboardButton(text="Назад", callback_data=CONTENT_MENU_CALLBACK)])
    return with_close_button(InlineKeyboardMarkup(inline_keyboard=rows), CONTENT_BLOCK_KEY)


def build_content_list_keyboard(items: list[ContentItem]) -> InlineKeyboardMarkup:
    keyboard = []
    for index, item in enumerate(items, start=1):
        if item.status == "COMPLETED":
            keyboard.append(
                [
                    InlineKeyboardButton(text=f"Оценить #{index}", callback_data=f"content:rate:{item.id}"),
                    InlineKeyboardButton(text=f"Комментарий #{index}", callback_data=f"content:comment:{item.id}"),
                ]
            )
        else:
            keyboard.append(
                [
                    InlineKeyboardButton(text=f"Готово #{index}", callback_data=f"content:complete:{item.id}"),
                    InlineKeyboardButton(text=f"Комментарий #{index}", callback_data=f"content:comment:{item.id}"),
                ]
            )

    keyboard.append([InlineKeyboardButton(text="Назад к контенту", callback_data=CONTENT_MENU_CALLBACK)])
    return with_close_button(InlineKeyboardMarkup(inline_keyboard=keyboard), CONTENT_BLOCK_KEY)


def build_content_cancel_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Отмена", callback_data=CONTENT_CANCEL_CALLBACK)],
            ]
        ),
        CONTENT_BLOCK_KEY,
    )


def build_content_filters_keyboard() -> InlineKeyboardMarkup:
    return with_close_button(
        InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="По категории", callback_data=CONTENT_FILTER_CATEGORIES_CALLBACK)],
                [
                    InlineKeyboardButton(text="Оценка 8-10", callback_data=CONTENT_FILTER_RATING_HIGH_CALLBACK),
                    InlineKeyboardButton(text="Оценка 5-7", callback_data=CONTENT_FILTER_RATING_MID_CALLBACK),
                ],
                [InlineKeyboardButton(text="Оценка 1-4", callback_data=CONTENT_FILTER_RATING_LOW_CALLBACK)],
                [
                    InlineKeyboardButton(text="Сегодня", callback_data=CONTENT_FILTER_TODAY_CALLBACK),
                    InlineKeyboardButton(text="7 дней", callback_data=CONTENT_FILTER_WEEK_CALLBACK),
                    InlineKeyboardButton(text="30 дней", callback_data=CONTENT_FILTER_MONTH_CALLBACK),
                ],
                [
                    InlineKeyboardButton(text="В планах", callback_data=CONTENT_PLANNED_CALLBACK),
                    InlineKeyboardButton(text="Завершённое", callback_data=CONTENT_COMPLETED_CALLBACK),
                ],
                [InlineKeyboardButton(text="Назад к контенту", callback_data=CONTENT_MENU_CALLBACK)],
            ]
        ),
        CONTENT_BLOCK_KEY,
    )


def build_content_rating_keyboard(content_id: int | None = None) -> InlineKeyboardMarkup:
    rows = []
    for start in (1, 6):
        rows.append(
            [
                InlineKeyboardButton(text=str(score), callback_data=f"content:score:{score}")
                for score in range(start, start + 5)
            ]
        )
    if content_id is not None:
        rows.append([InlineKeyboardButton(text="Поставить позже", callback_data=CONTENT_MENU_CALLBACK)])
    return with_close_button(InlineKeyboardMarkup(inline_keyboard=rows), CONTENT_BLOCK_KEY)


def build_content_reaction_keyboard() -> InlineKeyboardMarkup:
    reactions = list(CONTENT_REACTIONS.items())
    rows = []
    for index in range(0, len(reactions), 3):
        rows.append(
            [
                InlineKeyboardButton(text=emoji, callback_data=f"content:emoji:{key}")
                for key, emoji in reactions[index : index + 3]
            ]
        )

    rows.append([InlineKeyboardButton(text="Без реакции", callback_data=CONTENT_EMOJI_SKIP_CALLBACK)])
    return with_close_button(InlineKeyboardMarkup(inline_keyboard=rows), CONTENT_BLOCK_KEY)


def build_content_notification_keyboard(content_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поставить оценку", callback_data=f"content:rate:{content_id}")],
        ]
    )
