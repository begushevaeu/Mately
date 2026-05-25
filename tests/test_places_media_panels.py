from __future__ import annotations

import pytest

from app.bot.handlers.places import edit_places_panel, edit_places_panel_from_state, remember_places_panel_in_state


class FakeChat:
    id = 100


class FakePhotoMessage:
    chat = FakeChat()
    message_id = 42
    photo = [object()]

    def __init__(self) -> None:
        self.edited_text: dict | None = None
        self.edited_caption: dict | None = None

    async def edit_text(self, **kwargs) -> None:
        self.edited_text = kwargs

    async def edit_caption(self, **kwargs) -> None:
        self.edited_caption = kwargs


class FakeState:
    def __init__(self) -> None:
        self.data: dict = {}

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return self.data


class FakeBot:
    def __init__(self) -> None:
        self.edited_text: dict | None = None
        self.edited_caption: dict | None = None

    async def edit_message_text(self, **kwargs) -> None:
        self.edited_text = kwargs

    async def edit_message_caption(self, **kwargs) -> None:
        self.edited_caption = kwargs


@pytest.mark.asyncio
async def test_places_panel_edits_caption_for_photo_notifications() -> None:
    message = FakePhotoMessage()

    await edit_places_panel(message, "Оценка", reply_markup="keyboard")

    assert message.edited_text is None
    assert message.edited_caption == {
        "caption": "Оценка",
        "reply_markup": "keyboard",
        "parse_mode": "HTML",
    }


@pytest.mark.asyncio
async def test_places_panel_from_state_edits_caption_for_remembered_photo_notifications() -> None:
    message = FakePhotoMessage()
    state = FakeState()
    bot = FakeBot()

    await remember_places_panel_in_state(state, message)
    await edit_places_panel_from_state(bot, state, "Выбери оценку", reply_markup="keyboard")

    assert bot.edited_text is None
    assert bot.edited_caption == {
        "chat_id": 100,
        "message_id": 42,
        "caption": "Выбери оценку",
        "reply_markup": "keyboard",
        "parse_mode": "HTML",
    }
