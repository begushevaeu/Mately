from __future__ import annotations

from pathlib import Path

import pytest

from app.bot.handlers import tasks as task_handlers
from app.models import Task, User
from app.notifications.cats import CatNotificationType
from app.services.tasks import TaskMutationResult


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.photos: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.messages.append({"chat_id": chat_id, "text": text, **kwargs})

    async def send_photo(self, chat_id: int, photo, **kwargs) -> None:
        self.photos.append({"chat_id": chat_id, "photo": photo, **kwargs})


def build_task_result() -> TaskMutationResult:
    return TaskMutationResult(
        task=Task(id=1, title="Помыть пол", created_by=1, assigned_to=2, status="COMPLETED"),
        notification_user=User(id=2, telegram_id=200, username="two", first_name="Two"),
        notification_text="Готово.",
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


@pytest.mark.asyncio
async def test_task_notification_falls_back_to_text_when_asset_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = FakeBot()
    monkeypatch.setattr(task_handlers, "select_cat_asset", lambda _notification_type: None)

    await task_handlers.send_task_notification(bot, build_task_result())

    assert bot.photos == []
    assert bot.messages == [{"chat_id": 200, "text": "Готово.", "parse_mode": "HTML"}]
