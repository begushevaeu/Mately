from datetime import datetime, timezone

import pytest

from app.bot.handlers import main_menu
from app.models import Couple, User
from app.services.couples import OnboardingResult, OnboardingStatus


class FakeMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []

    async def answer(self, text: str, **_) -> None:
        self.answers.append(text)


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
