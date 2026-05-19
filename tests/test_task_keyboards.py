from app.bot.keyboards.tasks import TASK_POOL_CALLBACK, build_tasks_menu


def extract_button_labels(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def test_task_pool_menu_item_is_hidden_when_pool_is_empty() -> None:
    markup = build_tasks_menu(has_pool_tasks=False)

    assert "Ярмарка задач" not in extract_button_labels(markup)


def test_task_pool_menu_item_is_first_when_pool_has_tasks() -> None:
    markup = build_tasks_menu(has_pool_tasks=True)

    assert markup.inline_keyboard[0][0].text == "Ярмарка задач"
    assert markup.inline_keyboard[0][0].callback_data == TASK_POOL_CALLBACK
