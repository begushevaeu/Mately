from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.bot.handlers import tasks
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


class FakeChatBlockService:
    remembered_message_ids: list[int] = []

    def __init__(self, _session) -> None:
        pass

    async def reset_block(self, **_kwargs) -> None:
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
