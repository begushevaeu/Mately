from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.bot.handlers import tasks
from app.bot.keyboards.tasks import task_notification_delete_callback
from app.models import Couple, User
from app.services.couples import OnboardingResult, OnboardingStatus


@dataclass(slots=True)
class FakeChat:
    id: int


class FakeMessage:
    def __init__(self, message_id: int, chat_id: int = 100) -> None:
        self.message_id = message_id
        self.chat = FakeChat(id=chat_id)
        self.answers: list[FakeMessage] = []

    async def answer(self, *_args, **_kwargs) -> "FakeMessage":
        sent_message = FakeMessage(message_id=1000 + len(self.answers), chat_id=self.chat.id)
        self.answers.append(sent_message)
        return sent_message


class FakeCallbackUser:
    id = 100
    username = None
    first_name = None


class FakeCallback:
    def __init__(self, *, data: str, message: FakeMessage | None = None) -> None:
        self.data = data
        self.message = message
        self.from_user = FakeCallbackUser()
        self.answer_text: str | None = None
        self.answer_kwargs: dict | None = None

    async def answer(self, text: str | None = None, **kwargs) -> None:
        self.answer_text = text
        self.answer_kwargs = kwargs


class FakeBot:
    def __init__(self) -> None:
        self.deleted_messages: list[tuple[int, int]] = []

    async def delete_message(self, *, chat_id: int, message_id: int) -> None:
        self.deleted_messages.append((chat_id, message_id))


class FakeChatBlockService:
    remembered_message_ids: list[int] = []

    def __init__(self, _session) -> None:
        pass

    async def reset_block(self, **_kwargs) -> None:
        return None

    async def reset_other_blocks(self, **_kwargs) -> None:
        return None

    async def remember_messages(self, *, messages, **_kwargs) -> None:
        self.__class__.remembered_message_ids = [message.message_id for message in messages]


@pytest.mark.asyncio
async def test_tasks_block_remembers_user_trigger_message(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=1, telegram_id=100, username="one", first_name="One")
    result = OnboardingResult(
        status=OnboardingStatus.IN_COUPLE,
        user=user,
        couple=Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow"),
    )
    trigger_message = FakeMessage(message_id=42)

    async def fake_build_tasks_menu_for_user(*_args, **_kwargs):
        return None

    async def fake_build_tasks_panel_text(*_args, **_kwargs):
        return "Задачи"

    monkeypatch.setattr(tasks, "ChatBlockService", FakeChatBlockService)
    monkeypatch.setattr(tasks, "build_tasks_menu_for_user", fake_build_tasks_menu_for_user)
    monkeypatch.setattr(tasks, "build_tasks_panel_text", fake_build_tasks_panel_text)

    await tasks.reset_and_show_tasks_menu(
        trigger_message,
        session=None,
        bot=object(),
        result=result,
        trigger_message=trigger_message,
    )

    assert FakeChatBlockService.remembered_message_ids == [42, 1000]


@pytest.mark.asyncio
async def test_task_list_panel_renders_index_inside_quote() -> None:
    class FakeTaskService:
        async def build_task_card(self, _context, _task, *, show_ownership: bool, list_index: int | None = None) -> str:
            assert show_ownership is True
            return f"<blockquote>{list_index}. 🐻 Купить молоко</blockquote>\nСтатус: назначена"

    panel = await tasks.render_task_list_panel(
        FakeTaskService(),
        context=object(),
        tasks=[object()],
        title="Все активные",
        empty_text="Пусто.",
        show_ownership=True,
    )

    assert panel == (
        "📋 <b>Все активные</b>\n\n"
        "<blockquote>1. 🐻 Купить молоко</blockquote>\n"
        "Статус: назначена"
    )


@pytest.mark.asyncio
async def test_completed_task_notification_delete_resets_related_notification_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(id=1, telegram_id=100, username="one", first_name="One")
    result = OnboardingResult(
        status=OnboardingStatus.IN_COUPLE,
        user=user,
        couple=Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow"),
    )
    reset_block_keys: list[str] = []

    async def fake_access(*_, **__) -> OnboardingResult:
        return result

    class FakeTaskService:
        def __init__(self, _session) -> None:
            pass

        async def get_task_for_user(self, current_user: User, task_id: int) -> object:
            assert current_user is user
            assert task_id == 42
            return object()

    class DeletingChatBlockService:
        def __init__(self, _session) -> None:
            pass

        async def reset_block(self, *, block_key: str, **_kwargs) -> None:
            reset_block_keys.append(block_key)

    monkeypatch.setattr(tasks, "ensure_task_access_for_callback", fake_access)
    monkeypatch.setattr(tasks, "TaskService", FakeTaskService)
    monkeypatch.setattr(tasks, "ChatBlockService", DeletingChatBlockService)

    callback = FakeCallback(data=task_notification_delete_callback(42), message=FakeMessage(message_id=777))
    bot = FakeBot()

    await tasks.handle_delete_completed_task_notification(callback, session=None, bot=bot)

    assert bot.deleted_messages == [(100, 777)]
    assert reset_block_keys == ["tasks:n:42:assignment", "tasks:n:42:completed"]
    assert callback.answer_text == "Убрала"
