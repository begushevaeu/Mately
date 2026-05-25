from app.bot.keyboards.blocks import close_block_callback
from app.bot.keyboards.places import (
    ADD_PLACE_CALLBACK,
    PLACES_NOT_ACQUAINTED_CALLBACK_PREFIX,
    PLACES_PLANNED_CALLBACK,
    PLACES_VISITED_CALLBACK,
    build_place_category_keyboard,
    build_place_list_keyboard,
    build_place_notification_keyboard,
    build_place_rating_keyboard,
    build_places_menu,
)
from app.models import PlaceItem
from app.services.chat_blocks import PLACES_BLOCK_KEY


def extract_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_places_menu_contains_core_actions_without_filters() -> None:
    buttons = extract_buttons(build_places_menu())

    assert buttons[0].text == "Добавить место"
    assert buttons[0].callback_data == ADD_PLACE_CALLBACK
    assert [button.callback_data for button in buttons[1:3]] == [
        PLACES_PLANNED_CALLBACK,
        PLACES_VISITED_CALLBACK,
    ]
    assert "Фильтры" not in [button.text for button in buttons]
    assert buttons[-1].callback_data == close_block_callback(PLACES_BLOCK_KEY)


def test_place_category_keyboard_contains_date_categories() -> None:
    buttons = extract_buttons(build_place_category_keyboard())
    texts_by_callback = {button.callback_data: button.text for button in buttons}
    texts = [button.text for button in buttons]

    assert texts_by_callback["places:create:category:restaurant"] == "Добавить 🍽️ Ресторан"
    assert texts_by_callback["places:create:category:cinema"] == "Добавить 🎬 Кино"
    assert texts_by_callback["places:create:category:cafe"] == "Добавить ☕ Кафе"
    assert texts_by_callback["places:create:category:theatre"] == "Добавить 🎭 Театр"
    assert texts_by_callback["places:create:category:park"] == "Добавить 🌳 Парк"
    assert texts_by_callback["places:create:category:show"] == "Добавить 🎟️ Шоу"
    assert "🚶 Прогулка" not in texts
    assert texts_by_callback["places:create:category:other"] == "Добавить ✨ Другое"


def test_place_list_keyboard_switches_action_by_status() -> None:
    planned = PlaceItem(id=1, title="Кафе", category="CAFE", added_by=1, status="NOT_VISITED")
    visited = PlaceItem(id=2, title="Парк", category="PARK", added_by=1, status="VISITED")

    buttons = extract_buttons(build_place_list_keyboard([planned, visited]))

    assert [button.text for button in buttons] == [
        "Посетили #1",
        "Оценить #2",
        "Комментарий #2",
        "Назад к местам",
        "Закрыть",
    ]
    assert buttons[0].callback_data == "places:visit:1"
    assert buttons[1].callback_data == "places:rate:2"
    assert buttons[2].callback_data == "places:comment:2"


def test_place_rating_keyboard_allows_not_acquainted_response() -> None:
    buttons = extract_buttons(build_place_rating_keyboard(place_id=42))

    assert f"{PLACES_NOT_ACQUAINTED_CALLBACK_PREFIX}:42" in [button.callback_data for button in buttons]


def test_place_notification_keyboard_allows_rating_and_not_visited_response() -> None:
    buttons = extract_buttons(build_place_notification_keyboard(place_id=42))

    assert [button.text for button in buttons] == ["Поставить оценку", "Не был(а)"]
    assert buttons[0].callback_data == "places:rate:42"
    assert buttons[1].callback_data == f"{PLACES_NOT_ACQUAINTED_CALLBACK_PREFIX}:42"
