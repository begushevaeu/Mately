from types import SimpleNamespace

import pytest

from app.bot.handlers import errors


class FakeState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


class FakeMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, **_kwargs) -> None:
        self.answers.append(text)


class FakeCallback:
    def __init__(self) -> None:
        self.message = FakeMessage()
        self.answers: list[tuple[str, bool | None]] = []

    async def answer(self, text: str, *, show_alert: bool | None = None, **_kwargs) -> None:
        self.answers.append((text, show_alert))


@pytest.mark.asyncio
async def test_unexpected_message_error_clears_state_and_notifies_user() -> None:
    state = FakeState()
    message = FakeMessage()
    event = SimpleNamespace(update=SimpleNamespace(message=message), exception=RuntimeError("boom"))

    handled = await errors.handle_unexpected_error(event, state)

    assert handled is True
    assert state.cleared is True
    assert message.answers == [errors.GENERIC_ERROR_TEXT]


@pytest.mark.asyncio
async def test_unexpected_callback_error_answers_alert_and_chat_message() -> None:
    state = FakeState()
    callback = FakeCallback()
    event = SimpleNamespace(update=SimpleNamespace(callback_query=callback), exception=RuntimeError("boom"))

    handled = await errors.handle_unexpected_error(event, state)

    assert handled is True
    assert state.cleared is True
    assert callback.answers == [(errors.GENERIC_CALLBACK_ERROR_TEXT, True)]
    assert callback.message.answers == [errors.GENERIC_ERROR_TEXT]
