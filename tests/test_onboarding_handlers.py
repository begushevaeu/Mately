from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.bot.handlers import onboarding
from app.models import User
from app.services.couples import OnboardingResult, OnboardingStatus


@dataclass(slots=True)
class FakeChat:
    id: int = 100


class FakeMessage:
    def __init__(self, message_id: int = 1, text: str = "ABC12345") -> None:
        self.message_id = message_id
        self.text = text
        self.chat = FakeChat()
        self.sent_messages: list[FakeMessage] = []

    async def answer(self, *_args, **_kwargs) -> "FakeMessage":
        sent_message = FakeMessage(message_id=1000 + len(self.sent_messages), text="")
        self.sent_messages.append(sent_message)
        return sent_message


class FakeState:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def clear(self) -> None:
        self.events.append("clear_state")


class FakeCoupleService:
    def __init__(self, _session) -> None:
        pass

    async def join_couple(self, user: User, invite_code: str) -> OnboardingResult:
        assert invite_code == "ABC12345"
        return OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user)


class FakeChatBlockService:
    def __init__(self, _session) -> None:
        pass

    async def add_messages(self, *, messages, **_kwargs) -> None:
        self.__class__.events.append(f"remember:{','.join(str(message.message_id) for message in messages)}")

    async def reset_block(self, **_kwargs) -> None:
        self.__class__.events.append("reset_onboarding")


@pytest.mark.asyncio
async def test_successful_invite_code_cleans_onboarding_block_before_final_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(id=1, telegram_id=100, username=None, first_name="One")
    current_result = OnboardingResult(status=OnboardingStatus.NO_COUPLE, user=user)
    message = FakeMessage(message_id=42)
    events: list[str] = []
    FakeChatBlockService.events = events

    async def fake_get_current_onboarding_result(*_args, **_kwargs) -> OnboardingResult:
        return current_result

    async def fake_answer_for_onboarding_state(_message, result: OnboardingResult) -> None:
        events.append(f"answer:{result.status.value}")

    async def fake_maybe_prompt_partner_alias(*_args, **_kwargs) -> None:
        events.append("alias_prompt")

    monkeypatch.setattr(onboarding, "get_current_onboarding_result", fake_get_current_onboarding_result)
    monkeypatch.setattr(onboarding, "CoupleService", FakeCoupleService)
    monkeypatch.setattr(onboarding, "ChatBlockService", FakeChatBlockService)
    monkeypatch.setattr(onboarding, "answer_for_onboarding_state", fake_answer_for_onboarding_state)
    monkeypatch.setattr(onboarding, "maybe_prompt_partner_alias", fake_maybe_prompt_partner_alias)

    await onboarding.handle_invite_code(
        message,
        state=FakeState(events),
        session=None,
        bot=object(),
    )

    assert events == ["remember:42", "clear_state", "reset_onboarding", "answer:IN_COUPLE", "alias_prompt"]
