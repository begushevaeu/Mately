from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import Task

TASKS_MENU_CALLBACK = "tasks:menu"
ADD_TASK_CALLBACK = "tasks:add"
MY_TASKS_CALLBACK = "tasks:mine"
TASK_POOL_CALLBACK = "tasks:pool"
ALL_TASKS_CALLBACK = "tasks:all"
TASK_CREATE_CANCEL_CALLBACK = "tasks:create:cancel"
TASK_CREATE_ONE_TIME_CALLBACK = "tasks:create:recurring:once"
TASK_CREATE_RECURRING_CALLBACK = "tasks:create:recurring:regular"
TASK_CREATE_DAILY_CALLBACK = "tasks:create:recurrence:daily"
TASK_CREATE_WEEKLY_CALLBACK = "tasks:create:recurrence:weekly"
TASK_CREATE_MONTHLY_CALLBACK = "tasks:create:recurrence:monthly"
TASK_CREATE_CUSTOM_CALLBACK = "tasks:create:recurrence:custom"
TASK_CREATE_ASSIGN_SELF_CALLBACK = "tasks:create:assign:self"
TASK_CREATE_ASSIGN_PARTNER_CALLBACK = "tasks:create:assign:partner"
TASK_CREATE_ASSIGN_POOL_CALLBACK = "tasks:create:assign:pool"
TASK_CREATE_DEADLINE_TODAY_CALLBACK = "tasks:create:deadline:today"
TASK_CREATE_DEADLINE_TOMORROW_CALLBACK = "tasks:create:deadline:tomorrow"
TASK_CREATE_DEADLINE_NONE_CALLBACK = "tasks:create:deadline:none"

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
        keyboard.append([InlineKeyboardButton(text="Ярмарка", callback_data=TASK_POOL_CALLBACK)])

    keyboard.extend(
        [
            [InlineKeyboardButton(text="Добавить задачу", callback_data=ADD_TASK_CALLBACK)],
            [InlineKeyboardButton(text="Мои задачи", callback_data=MY_TASKS_CALLBACK)],
            [InlineKeyboardButton(text="Все активные", callback_data=ALL_TASKS_CALLBACK)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_task_list_keyboard(
    tasks: list[Task],
    *,
    view: str,
    current_user_id: int,
) -> InlineKeyboardMarkup:
    keyboard = []
    for index, task in enumerate(tasks, start=1):
        if view == TASK_POOL_CALLBACK:
            keyboard.append([InlineKeyboardButton(text=f"Взять #{index}", callback_data=f"tasks:claim:{task.id}")])
            continue

        if task.assigned_to is None:
            keyboard.append([InlineKeyboardButton(text=f"Взять #{index}", callback_data=f"tasks:claim:{task.id}")])
        elif view == MY_TASKS_CALLBACK or task.assigned_to == current_user_id:
            keyboard.append([InlineKeyboardButton(text=f"Готово #{index}", callback_data=f"tasks:done:{task.id}")])

    keyboard.append([InlineKeyboardButton(text="Назад к задачам", callback_data=TASKS_MENU_CALLBACK)])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_task_creation_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data=TASK_CREATE_CANCEL_CALLBACK)],
        ]
    )


def build_recurring_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=ONE_TIME_TASK_BUTTON, callback_data=TASK_CREATE_ONE_TIME_CALLBACK),
                InlineKeyboardButton(text=RECURRING_TASK_BUTTON, callback_data=TASK_CREATE_RECURRING_CALLBACK),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data=TASK_CREATE_CANCEL_CALLBACK)],
        ]
    )


def build_recurrence_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=DAILY_RECURRENCE_BUTTON, callback_data=TASK_CREATE_DAILY_CALLBACK),
                InlineKeyboardButton(text=WEEKLY_RECURRENCE_BUTTON, callback_data=TASK_CREATE_WEEKLY_CALLBACK),
            ],
            [
                InlineKeyboardButton(text=MONTHLY_RECURRENCE_BUTTON, callback_data=TASK_CREATE_MONTHLY_CALLBACK),
                InlineKeyboardButton(text=CUSTOM_RECURRENCE_BUTTON, callback_data=TASK_CREATE_CUSTOM_CALLBACK),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data=TASK_CREATE_CANCEL_CALLBACK)],
        ]
    )


def build_assignment_keyboard(partner_button_text: str | None = None) -> InlineKeyboardMarkup:
    partner_button_text = partner_button_text or ASSIGN_PARTNER_BUTTON
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=ASSIGN_SELF_BUTTON, callback_data=TASK_CREATE_ASSIGN_SELF_CALLBACK),
                InlineKeyboardButton(text=partner_button_text, callback_data=TASK_CREATE_ASSIGN_PARTNER_CALLBACK),
            ],
            [InlineKeyboardButton(text=ASSIGN_POOL_BUTTON, callback_data=TASK_CREATE_ASSIGN_POOL_CALLBACK)],
            [InlineKeyboardButton(text="Отмена", callback_data=TASK_CREATE_CANCEL_CALLBACK)],
        ]
    )


def build_deadline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=TODAY_DEADLINE_BUTTON, callback_data=TASK_CREATE_DEADLINE_TODAY_CALLBACK),
                InlineKeyboardButton(text=TOMORROW_DEADLINE_BUTTON, callback_data=TASK_CREATE_DEADLINE_TOMORROW_CALLBACK),
            ],
            [InlineKeyboardButton(text=NO_DEADLINE_BUTTON, callback_data=TASK_CREATE_DEADLINE_NONE_CALLBACK)],
            [InlineKeyboardButton(text="Отмена", callback_data=TASK_CREATE_CANCEL_CALLBACK)],
        ]
    )
