from __future__ import annotations

import pytest

from app.bot.handlers import content as content_handlers
from app.bot.handlers import places as place_handlers
from app.bot.keyboards.content import CONTENT_NOT_ACQUAINTED_CALLBACK_PREFIX
from app.bot.keyboards.places import PLACES_NOT_ACQUAINTED_CALLBACK_PREFIX
from app.ai.cozy import CozyMessageTheme
from app.models import ContentItem, PlaceItem, User
from app.notifications.cats import CatNotificationType
from app.services.couples import OnboardingResult, OnboardingStatus
from app.services.content import ContentMutationResult
from app.services.places import PlaceMutationResult


class FakeCallbackUser:
    id = 100
    username = None
    first_name = None


class FakeMessage:
    pass


class FakeCallback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = FakeMessage()
        self.from_user = FakeCallbackUser()
        self.answer_text: str | None = None
        self.answer_kwargs: dict | None = None

    async def answer(self, text: str | None = None, **kwargs) -> None:
        self.answer_text = text
        self.answer_kwargs = kwargs


class FakeState:
    def __init__(self, data: dict | None = None) -> None:
        self.data = data or {}
        self.clear_called = False

    async def get_data(self) -> dict:
        return self.data

    async def clear(self) -> None:
        self.clear_called = True


@pytest.mark.asyncio
async def test_content_not_acquainted_handler_saves_without_score(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name=None)
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user)
    saved_content_ids: list[int] = []
    edited_panels: list[tuple[str, object]] = []

    async def fake_access(*_, **__) -> OnboardingResult:
        return result

    class FakeContentService:
        def __init__(self, _session) -> None:
            pass

        async def save_not_acquainted(self, current_user: User, *, content_id: int) -> None:
            assert current_user is user
            saved_content_ids.append(content_id)

    async def fake_root_panel(*_, **__) -> tuple[str, object]:
        return "root", "keyboard"

    async def fake_edit_panel(_message, text: str, reply_markup=None) -> None:
        edited_panels.append((text, reply_markup))

    monkeypatch.setattr(content_handlers, "ensure_content_access_for_callback", fake_access)
    monkeypatch.setattr(content_handlers, "ContentService", FakeContentService)
    monkeypatch.setattr(content_handlers, "build_content_root_panel", fake_root_panel)
    monkeypatch.setattr(content_handlers, "edit_content_panel", fake_edit_panel)

    callback = FakeCallback(f"{CONTENT_NOT_ACQUAINTED_CALLBACK_PREFIX}:42")
    state = FakeState()

    await content_handlers.handle_content_not_acquainted(callback, state, session=None)

    assert saved_content_ids == [42]
    assert state.clear_called is True
    assert callback.answer_text == "Сохранила"
    assert edited_panels == [("✅ <b>Ответ сохранён:</b> не знаком(а)\n\nroot", "keyboard")]


@pytest.mark.asyncio
async def test_place_not_acquainted_handler_saves_without_score(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name=None)
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user)
    saved_place_ids: list[int] = []
    edited_panels: list[tuple[str, object]] = []

    async def fake_access(*_, **__) -> OnboardingResult:
        return result

    class FakePlaceService:
        def __init__(self, _session) -> None:
            pass

        async def save_not_acquainted(self, current_user: User, *, place_id: int) -> None:
            assert current_user is user
            saved_place_ids.append(place_id)

    async def fake_root_panel(*_, **__) -> tuple[str, object]:
        return "root", "keyboard"

    async def fake_edit_panel(_message, text: str, reply_markup=None) -> None:
        edited_panels.append((text, reply_markup))

    monkeypatch.setattr(place_handlers, "ensure_places_access_for_callback", fake_access)
    monkeypatch.setattr(place_handlers, "PlaceService", FakePlaceService)
    monkeypatch.setattr(place_handlers, "build_places_root_panel", fake_root_panel)
    monkeypatch.setattr(place_handlers, "edit_places_panel", fake_edit_panel)

    callback = FakeCallback(f"{PLACES_NOT_ACQUAINTED_CALLBACK_PREFIX}:42")
    state = FakeState()

    await place_handlers.handle_place_not_acquainted(callback, state, session=None)

    assert saved_place_ids == [42]
    assert state.clear_called is True
    assert callback.answer_text == "Сохранила"
    assert edited_panels == [("✅ <b>Ответ сохранён:</b> не был(а)\n\nroot", "keyboard")]


@pytest.mark.asyncio
async def test_content_completion_notification_uses_quote_markup_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=2, telegram_id=200, username=None, first_name="Two")
    result = ContentMutationResult(
        item=ContentItem(id=42, title="Movie", category="MOVIE", added_by=1, status="COMPLETED"),
        notification_user=user,
        notification_text="Базовый текст.",
        cozy_theme=CozyMessageTheme.CONTENT_COMPLETED,
        cozy_subject="Movie",
        cat_notification_type=CatNotificationType.COMPLETED,
    )
    delivered: list[dict] = []

    class FakeBot:
        async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
            delivered.append({"chat_id": chat_id, "text": text, **kwargs})

    async def fake_append_cozy_suffix(text: str, **kwargs) -> str:
        assert kwargs == {
            "theme": CozyMessageTheme.CONTENT_COMPLETED,
            "subject": "Movie",
            "escape_suffix": True,
        }
        return f"{text}\n\nТёплая строка."

    monkeypatch.setattr(content_handlers, "append_cozy_suffix", fake_append_cozy_suffix)
    monkeypatch.setattr(content_handlers, "select_cat_asset", lambda _notification_type: None)

    await content_handlers.send_content_notification(bot=FakeBot(), result=result)

    buttons = [button for row in delivered[0]["reply_markup"].inline_keyboard for button in row]
    assert delivered[0]["chat_id"] == 200
    assert delivered[0]["text"] == "Базовый текст.\n\nТёплая строка."
    assert delivered[0]["parse_mode"] == "HTML"
    assert [button.callback_data for button in buttons] == [
        "content:rate:42",
        f"{CONTENT_NOT_ACQUAINTED_CALLBACK_PREFIX}:42",
    ]


@pytest.mark.asyncio
async def test_place_visit_notification_uses_rating_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=2, telegram_id=200, username=None, first_name="Two")
    result = PlaceMutationResult(
        item=PlaceItem(id=42, title="Sage", category="RESTAURANT", added_by=1, status="VISITED"),
        notification_user=user,
        notification_text="Базовый текст.",
        cozy_theme=CozyMessageTheme.PLACE_VISITED,
        cozy_subject="Sage",
        cat_notification_type=CatNotificationType.COMPLETED,
    )
    delivered: list[dict] = []

    async def fake_append_cozy_suffix(text: str, **kwargs) -> str:
        assert kwargs == {"theme": CozyMessageTheme.PLACE_VISITED, "subject": "Sage", "escape_suffix": True}
        return f"{text}\n\nТёплая строка."

    async def fake_send_user_notification(_bot, notification_user: User, text: str, **kwargs) -> None:
        delivered.append({"user": notification_user, "text": text, **kwargs})

    monkeypatch.setattr(place_handlers, "append_cozy_suffix", fake_append_cozy_suffix)
    monkeypatch.setattr(place_handlers, "send_user_notification", fake_send_user_notification)

    await place_handlers.send_place_notification(bot=object(), result=result)

    buttons = [button for row in delivered[0]["reply_markup"].inline_keyboard for button in row]
    assert delivered[0]["user"] is user
    assert delivered[0]["text"] == "Базовый текст.\n\nТёплая строка."
    assert delivered[0]["cat_notification_type"] is CatNotificationType.COMPLETED
    assert delivered[0]["parse_mode"] == "HTML"
    assert [button.callback_data for button in buttons] == [
        "places:rate:42",
        f"{PLACES_NOT_ACQUAINTED_CALLBACK_PREFIX}:42",
    ]
