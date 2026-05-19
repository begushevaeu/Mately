from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.bot.keyboards.onboarding import CANCEL_BUTTON

TASKS_MENU_CALLBACK = "tasks:menu"
ADD_TASK_CALLBACK = "tasks:add"
MY_TASKS_CALLBACK = "tasks:mine"
TASK_POOL_CALLBACK = "tasks:pool"
ALL_TASKS_CALLBACK = "tasks:all"

ONE_TIME_TASK_BUTTON = "Разовая"
RECURRING_TASK_BUTTON = "Регулярная"
DAILY_RECURRENCE_BUTTON = "Каждый день"
WEEKLY_RECURRENCE_BUTTON = "Каждую неделю"
MONTHLY_RECURRENCE_BUTTON = "Каждый месяц"
CUSTOM_RECURRENCE_BUTTON = "Другой интервал"
ASSIGN_SELF_BUTTON = "Себе"
ASSIGN_PARTNER_BUTTON = "Партнеру"
ASSIGN_POOL_BUTTON = "В общий пул"
TODAY_DEADLINE_BUTTON = "Сегодня"
TOMORROW_DEADLINE_BUTTON = "Завтра"
NO_DEADLINE_BUTTON = "Без срока"


def build_tasks_menu(*, has_pool_tasks: bool = False) -> InlineKeyboardMarkup:
    keyboard = []
    if has_pool_tasks:
        keyboard.append([InlineKeyboardButton(text="Ярмарка задач", callback_data=TASK_POOL_CALLBACK)])

    keyboard.extend(
        [
            [InlineKeyboardButton(text="Добавить задачу", callback_data=ADD_TASK_CALLBACK)],
            [InlineKeyboardButton(text="Мои задачи", callback_data=MY_TASKS_CALLBACK)],
            [InlineKeyboardButton(text="Все активные", callback_data=ALL_TASKS_CALLBACK)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_task_actions(task_id: int, *, can_claim: bool) -> InlineKeyboardMarkup:
    row = []
    if can_claim:
        row.append(InlineKeyboardButton(text="Взять задачу", callback_data=f"tasks:claim:{task_id}"))

    row.append(InlineKeyboardButton(text="Выполнено", callback_data=f"tasks:done:{task_id}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])


def build_recurring_choice_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ONE_TIME_TASK_BUTTON), KeyboardButton(text=RECURRING_TASK_BUTTON)],
            [KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Разовая или регулярная?",
    )


def build_recurrence_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=DAILY_RECURRENCE_BUTTON), KeyboardButton(text=WEEKLY_RECURRENCE_BUTTON)],
            [KeyboardButton(text=MONTHLY_RECURRENCE_BUTTON), KeyboardButton(text=CUSTOM_RECURRENCE_BUTTON)],
            [KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Как часто повторять?",
    )


def build_assignment_keyboard(partner_button_text: str | None = None) -> ReplyKeyboardMarkup:
    partner_button_text = partner_button_text or ASSIGN_PARTNER_BUTTON
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ASSIGN_SELF_BUTTON), KeyboardButton(text=partner_button_text)],
            [KeyboardButton(text=ASSIGN_POOL_BUTTON)],
            [KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Кому назначить?",
    )


def build_deadline_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TODAY_DEADLINE_BUTTON), KeyboardButton(text=TOMORROW_DEADLINE_BUTTON)],
            [KeyboardButton(text=NO_DEADLINE_BUTTON)],
            [KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Когда выполнить?",
    )
