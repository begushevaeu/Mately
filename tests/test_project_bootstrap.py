from app.bot.keyboards.main_menu import build_main_menu
from app.core.config import get_settings


def test_default_timezone_is_configured() -> None:
    settings = get_settings()

    assert settings.default_timezone == "Europe/Moscow"


def test_main_menu_contains_core_sections() -> None:
    markup = build_main_menu()
    button_texts = [button.text for row in markup.keyboard for button in row]

    assert "📋 Задачи" in button_texts
    assert "🎬 Контент" in button_texts
    assert "🛒 Покупки" in button_texts
    assert "📊 Статистика" in button_texts
    assert "⚙️ Настройки" in button_texts
