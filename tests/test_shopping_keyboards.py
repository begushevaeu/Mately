from app.bot.keyboards.shopping import ADD_SHOPPING_ITEM_CALLBACK, build_shopping_keyboard
from app.models import ShoppingItem


def extract_buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def test_shopping_keyboard_shows_add_and_active_item_actions() -> None:
    active = ShoppingItem(id=1, title="Молоко", added_by=1, status="ACTIVE")
    bought = ShoppingItem(id=2, title="Хлеб", added_by=1, status="BOUGHT")

    buttons = extract_buttons(build_shopping_keyboard([active, bought]))

    assert buttons[0].text == "Добавить"
    assert buttons[0].callback_data == ADD_SHOPPING_ITEM_CALLBACK
    assert [button.text for button in buttons] == ["Добавить", "Куплено #1"]
    assert buttons[1].callback_data == "shopping:bought:1"
