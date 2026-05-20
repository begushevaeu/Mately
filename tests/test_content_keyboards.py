from app.bot.keyboards.content import (
    ADD_CONTENT_CALLBACK,
    CONTENT_COMPLETED_CALLBACK,
    CONTENT_EMOJI_SKIP_CALLBACK,
    CONTENT_PLANNED_CALLBACK,
    build_content_list_keyboard,
    build_content_menu,
    build_content_reaction_keyboard,
)
from app.models import ContentItem


def extract_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_content_menu_contains_core_actions() -> None:
    buttons = extract_buttons(build_content_menu())

    assert buttons[0].text == "Добавить контент"
    assert buttons[0].callback_data == ADD_CONTENT_CALLBACK
    assert [button.callback_data for button in buttons[1:3]] == [
        CONTENT_PLANNED_CALLBACK,
        CONTENT_COMPLETED_CALLBACK,
    ]


def test_content_list_keyboard_switches_action_by_status() -> None:
    planned = ContentItem(id=1, title="Фильм", category="MOVIE", added_by=1, status="NOT_COMPLETED")
    completed = ContentItem(id=2, title="Книга", category="BOOK", added_by=1, status="COMPLETED")

    buttons = extract_buttons(build_content_list_keyboard([planned, completed]))

    assert [button.text for button in buttons] == [
        "Готово #1",
        "Комментарий #1",
        "Оценить #2",
        "Комментарий #2",
        "Назад к контенту",
    ]
    assert buttons[0].callback_data == "content:complete:1"
    assert buttons[1].callback_data == "content:comment:1"
    assert buttons[2].callback_data == "content:rate:2"
    assert buttons[3].callback_data == "content:comment:2"


def test_content_reaction_keyboard_uses_updated_reaction_set() -> None:
    markup = build_content_reaction_keyboard()
    reaction_rows = markup.inline_keyboard[:-1]
    buttons = extract_buttons(markup)

    assert [button.text for button in buttons[:-1]] == ["❤️", "🤩", "🤡", "💩", "🔥", "😭", "🥴", "👍🏻", "👎🏻"]
    assert [len(row) for row in reaction_rows] == [3, 3, 3]
    assert buttons[-1].callback_data == CONTENT_EMOJI_SKIP_CALLBACK
