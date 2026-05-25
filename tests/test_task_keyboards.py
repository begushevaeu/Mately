from app.bot.keyboards.blocks import close_block_callback
from app.bot.keyboards.tasks import (
    MY_TASKS_CALLBACK,
    TASK_POOL_CALLBACK,
    build_completed_task_notification_keyboard,
    build_task_list_keyboard,
    build_tasks_menu,
    task_notification_delete_callback,
)
from app.models import Task
from app.services.chat_blocks import TASKS_BLOCK_KEY


def extract_button_labels(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def test_task_pool_menu_item_is_hidden_when_pool_is_empty() -> None:
    markup = build_tasks_menu(has_pool_tasks=False)

    assert "Ярмарка" not in extract_button_labels(markup)
    assert markup.inline_keyboard[-1][0].text == "Закрыть"
    assert markup.inline_keyboard[-1][0].callback_data == close_block_callback(TASKS_BLOCK_KEY)


def test_task_pool_menu_item_is_first_when_pool_has_tasks() -> None:
    markup = build_tasks_menu(has_pool_tasks=True)

    assert markup.inline_keyboard[0][0].text == "Ярмарка"
    assert markup.inline_keyboard[0][0].callback_data == TASK_POOL_CALLBACK


def test_task_list_keyboard_shows_delete_and_stop_repeat_actions() -> None:
    one_time_task = Task(
        id=1,
        title="Разобрать пакеты",
        created_by=1,
        assigned_to=1,
        status="ASSIGNED",
        is_recurring=False,
        recurrence_type=None,
    )
    recurring_task = Task(
        id=2,
        title="Полить цветы",
        created_by=1,
        assigned_to=1,
        status="ASSIGNED",
        is_recurring=True,
        recurrence_type="DAILY",
    )

    markup = build_task_list_keyboard(
        [one_time_task, recurring_task],
        view=MY_TASKS_CALLBACK,
        current_user_id=1,
    )

    assert extract_button_labels(markup) == [
        "Готово #1",
        "Удалить #1",
        "Готово #2",
        "Остановить повтор #2",
        "Назад к задачам",
        "Закрыть",
    ]
    assert markup.inline_keyboard[1][0].callback_data == "tasks:archive:1"
    assert markup.inline_keyboard[3][0].callback_data == "tasks:archive:2"


def test_completed_task_notification_keyboard_deletes_notification() -> None:
    markup = build_completed_task_notification_keyboard(task_id=42)

    button = markup.inline_keyboard[0][0]
    assert button.text == "Удалить уведомление"
    assert button.callback_data == task_notification_delete_callback(42)
