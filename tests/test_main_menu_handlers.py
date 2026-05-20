from datetime import datetime, timezone

import pytest

from app.bot.handlers import main_menu
from app.bot.keyboards.blocks import close_block_callback
from app.models import Couple, User
from app.services.chat_blocks import CONTENT_BLOCK_KEY, MENU_HINT_BLOCK_KEY, TASKS_BLOCK_KEY
from app.services.couples import OnboardingResult, OnboardingStatus


class FakeChat:
    id = 100


class FakeMessage:
    def __init__(self, message_id: int = 1) -> None:
        self.message_id = message_id
        self.chat = FakeChat()
        self.answers: list[str] = []
        self.answer_kwargs: list[dict] = []
        self.sent_messages: list[FakeMessage] = []

    async def answer(self, text: str, **kwargs) -> "FakeMessage":
        self.answers.append(text)
        self.answer_kwargs.append(kwargs)
        sent_message = FakeMessage(message_id=1000 + len(self.sent_messages))
        self.sent_messages.append(sent_message)
        return sent_message


class FakeCallbackUser:
    id = 100
    username = None
    first_name = None


class FakeCallback:
    def __init__(self, data: str, message: FakeMessage | None = None) -> None:
        self.data = data
        self.message = message
        self.from_user = FakeCallbackUser()
        self.answer_called = False

    async def answer(self, *_, **__) -> None:
        self.answer_called = True


class FakeState:
    def __init__(self) -> None:
        self.clear_called = False

    async def clear(self) -> None:
        self.clear_called = True


class FakeBot:
    def __init__(self) -> None:
        self.deleted_messages: list[tuple[int, int]] = []

    async def delete_message(self, *, chat_id: int, message_id: int) -> None:
        self.deleted_messages.append((chat_id, message_id))


class FakeChatBlockService:
    reset_other_block_key: str | None = None
    reset_block_key: str | None = None
    remembered_message_ids: list[int] = []

    def __init__(self, _session) -> None:
        pass

    async def reset_other_blocks(self, *, current_block_key: str, **_) -> None:
        self.__class__.reset_other_block_key = current_block_key

    async def reset_block(self, *, block_key: str, **_) -> None:
        self.__class__.reset_block_key = block_key

    async def remember_messages(self, *, messages, **_) -> None:
        self.__class__.remembered_message_ids = [message.message_id for message in messages]


@pytest.mark.asyncio
async def test_main_menu_guard_blocks_users_without_couple(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name=None)
    result = OnboardingResult(status=OnboardingStatus.NO_COUPLE, user=user)
    message = FakeMessage()
    onboarding_answers: list[OnboardingStatus] = []

    async def fake_get_current_onboarding_result(*_, **__) -> OnboardingResult:
        return result

    async def fake_answer_for_onboarding_state(_, onboarding_result: OnboardingResult) -> None:
        onboarding_answers.append(onboarding_result.status)

    monkeypatch.setattr(main_menu, "get_current_onboarding_result", fake_get_current_onboarding_result)
    monkeypatch.setattr(main_menu, "answer_for_onboarding_state", fake_answer_for_onboarding_state)

    access_result = await main_menu.ensure_main_menu_access(message, session=None)

    assert access_result is None
    assert onboarding_answers == [OnboardingStatus.NO_COUPLE]


@pytest.mark.asyncio
async def test_main_menu_guard_allows_users_in_couple(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name=None)
    couple = Couple(
        id=1,
        invite_code="ABC12345",
        invite_expires_at=datetime.now(timezone.utc),
        timezone="Europe/Moscow",
    )
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user, couple=couple)
    message = FakeMessage()

    async def fake_get_current_onboarding_result(*_, **__) -> OnboardingResult:
        return result

    monkeypatch.setattr(main_menu, "get_current_onboarding_result", fake_get_current_onboarding_result)

    access_result = await main_menu.ensure_main_menu_access(message, session=None)

    assert access_result is result
    assert message.answers == []


@pytest.mark.asyncio
async def test_main_menu_block_resets_previous_blocks_and_remembers_current(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name=None)
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user)
    message = FakeMessage(message_id=42)

    monkeypatch.setattr(main_menu, "ChatBlockService", FakeChatBlockService)

    await main_menu.show_main_menu_block(
        message=message,
        session=None,
        bot=object(),
        result=result,
        block_key=CONTENT_BLOCK_KEY,
        text="Контент",
        reply_markup=None,
    )

    assert FakeChatBlockService.reset_other_block_key == CONTENT_BLOCK_KEY
    assert FakeChatBlockService.reset_block_key == CONTENT_BLOCK_KEY
    assert FakeChatBlockService.remembered_message_ids == [42, 1000]


@pytest.mark.asyncio
async def test_close_block_callback_resets_current_block_and_clears_state(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name=None)
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user)
    callback = FakeCallback(data=close_block_callback(TASKS_BLOCK_KEY), message=FakeMessage(message_id=77))
    state = FakeState()
    bot = FakeBot()
    FakeChatBlockService.reset_block_key = None

    async def fake_get_current_result_for_callback(*_, **__) -> OnboardingResult:
        return result

    monkeypatch.setattr(main_menu, "get_current_result_for_callback", fake_get_current_result_for_callback)
    monkeypatch.setattr(main_menu, "ChatBlockService", FakeChatBlockService)

    await main_menu.handle_close_block(callback, state, session=None, bot=bot)

    assert callback.answer_called is True
    assert state.clear_called is True
    assert FakeChatBlockService.reset_block_key == TASKS_BLOCK_KEY
    assert bot.deleted_messages == [(100, 77)]


@pytest.mark.asyncio
async def test_unknown_message_is_deleted_and_restores_reply_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name=None)
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user)
    message = FakeMessage(message_id=88)
    bot = FakeBot()
    FakeChatBlockService.reset_block_key = None
    FakeChatBlockService.remembered_message_ids = []

    async def fake_get_current_onboarding_result(*_, **__) -> OnboardingResult:
        return result

    monkeypatch.setattr(main_menu, "get_current_onboarding_result", fake_get_current_onboarding_result)
    monkeypatch.setattr(main_menu, "ChatBlockService", FakeChatBlockService)

    await main_menu.handle_unknown_menu_text(message, session=None, bot=bot)

    assert bot.deleted_messages == [(100, 88)]
    assert FakeChatBlockService.reset_block_key == MENU_HINT_BLOCK_KEY
    assert FakeChatBlockService.remembered_message_ids == [1000]
    assert message.answers == ["Я убрала лишнее сообщение и обновила меню. Выбери раздел кнопкой ниже или нажми /menu."]
    assert "reply_markup" in message.answer_kwargs[0]
