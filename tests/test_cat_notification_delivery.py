from __future__ import annotations

from pathlib import Path

import pytest

from app.bot.handlers import tasks as task_handlers
from app.bot.keyboards.tasks import task_notification_delete_callback
from app.models import Task, User
from app.notifications.cats import CatNotificationType
from app.services.tasks import TaskMutationResult


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeSentMessage:
    def __init__(self, message_id: int, chat_id: int) -> None:
        self.message_id = message_id
        self.chat = FakeChat(chat_id)


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.photos: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> FakeSentMessage:
        self.messages.append({"chat_id": chat_id, "text": text, **kwargs})
        return FakeSentMessage(message_id=1000 + len(self.messages), chat_id=chat_id)

    async def send_photo(self, chat_id: int, photo, **kwargs) -> FakeSentMessage:
        self.photos.append({"chat_id": chat_id, "photo": photo, **kwargs})
        return FakeSentMessage(message_id=2000 + len(self.photos), chat_id=chat_id)


def build_task_result() -> TaskMutationResult:
    return TaskMutationResult(
        task=Task(id=1, title="Помыть пол", created_by=1, assigned_to=2, status="COMPLETED"),
        notification_user=User(id=2, telegram_id=200, username="two", first_name="Two"),
        notification_text="Готово.",
        notification_message_kind="completed",
        cat_notification_type=CatNotificationType.COMPLETED,
    )


@pytest.mark.asyncio
async def test_task_notification_sends_cat_photo_when_asset_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cat_asset = tmp_path / "cat.png"
    cat_asset.write_bytes(b"png")
    bot = FakeBot()
    monkeypatch.setattr(task_handlers, "select_cat_asset", lambda _notification_type: cat_asset)

    await task_handlers.send_task_notification(bot, build_task_result())

    assert bot.messages == []
    assert bot.photos[0]["chat_id"] == 200
    assert Path(str(bot.photos[0]["photo"].path)) == cat_asset
    assert bot.photos[0]["caption"] == "Готово."
    assert bot.photos[0]["parse_mode"] == "HTML"
    button = bot.photos[0]["reply_markup"].inline_keyboard[0][0]
    assert button.text == "Удалить уведомление"
    assert button.callback_data == task_notification_delete_callback(1)


@pytest.mark.asyncio
async def test_task_notification_falls_back_to_text_when_asset_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = FakeBot()
    monkeypatch.setattr(task_handlers, "select_cat_asset", lambda _notification_type: None)

    await task_handlers.send_task_notification(bot, build_task_result())

    assert bot.photos == []
    assert bot.messages[0]["chat_id"] == 200
    assert bot.messages[0]["text"] == "Готово."
    assert bot.messages[0]["parse_mode"] == "HTML"
    assert bot.messages[0]["reply_markup"].inline_keyboard[0][0].callback_data == task_notification_delete_callback(1)


@pytest.mark.asyncio
async def test_task_notification_remembers_sent_message(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = FakeBot()
    events: list[tuple[int, int, str, list[int]]] = []

    class FakeChatBlockService:
        def __init__(self, session) -> None:
            assert session == "session"

        async def add_messages(self, *, user: User, chat_id: int, block_key: str, messages: list[FakeSentMessage]) -> None:
            events.append((user.id, chat_id, block_key, [message.message_id for message in messages]))

    monkeypatch.setattr(task_handlers, "select_cat_asset", lambda _notification_type: None)
    monkeypatch.setattr(task_handlers, "ChatBlockService", FakeChatBlockService)

    await task_handlers.send_task_notification(bot, build_task_result(), session="session")

    assert events == [(2, 200, "tasks:n:1:completed", [1001])]
