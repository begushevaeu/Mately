from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.bot.handlers import partner_aliases
from app.bot.states.partner_alias import PartnerAliasStates
from app.models import Couple, User
from app.services.couples import OnboardingResult, OnboardingStatus


class FakeChat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class FakeMessage:
    def __init__(self, chat_id: int, message_id: int = 1000) -> None:
        self.chat = FakeChat(chat_id)
        self.message_id = message_id


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> FakeMessage:
        self.sent_messages.append({"chat_id": chat_id, "text": text, **kwargs})
        return FakeMessage(chat_id)


class FakeState:
    def __init__(self) -> None:
        self.state = None
        self.data: dict = {}

    async def set_state(self, state) -> None:
        self.state = state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)


class FakeFsm:
    def __init__(self, state: FakeState) -> None:
        self.state = state
        self.context_args: dict | None = None

    def get_context(self, **kwargs) -> FakeState:
        self.context_args = kwargs
        return self.state


class FakeDispatcher:
    def __init__(self, state: FakeState) -> None:
        self.fsm = FakeFsm(state)


class FakeTaskService:
    members: list[User] = []

    def __init__(self, _session) -> None:
        pass

    async def get_context(self, current_user: User):
        return SimpleNamespace(members=self.__class__.members, current_user=current_user)


class FakePartnerAliasService:
    has_alias = False
    checks: list[tuple[int, int]] = []

    def __init__(self, _session) -> None:
        pass

    async def has_alias_for(self, *, owner: User, partner: User) -> bool:
        self.__class__.checks.append((owner.id, partner.id))
        return self.__class__.has_alias


class FakeChatBlockService:
    events: list[str] = []

    def __init__(self, _session) -> None:
        pass

    async def reset_block(self, *, user: User, chat_id: int, block_key: str, **_kwargs) -> None:
        self.__class__.events.append(f"reset:{user.id}:{chat_id}:{block_key}")

    async def add_messages(self, *, user: User, chat_id: int, block_key: str, messages, **_kwargs) -> None:
        message_ids = ",".join(str(message.message_id) for message in messages)
        self.__class__.events.append(f"remember:{user.id}:{chat_id}:{block_key}:{message_ids}")


@pytest.mark.asyncio
async def test_creator_is_prompted_to_name_joined_partner(monkeypatch: pytest.MonkeyPatch) -> None:
    creator = User(id=1, telegram_id=100, username="one", first_name="One")
    joined = User(id=2, telegram_id=200, username="two", first_name="Two")
    result = OnboardingResult(
        status=OnboardingStatus.IN_COUPLE,
        user=joined,
        couple=Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow"),
    )
    state = FakeState()
    bot = FakeBot()
    dispatcher = FakeDispatcher(state)
    FakeTaskService.members = [creator, joined]
    FakePartnerAliasService.has_alias = False
    FakePartnerAliasService.checks = []
    FakeChatBlockService.events = []

    monkeypatch.setattr(partner_aliases, "TaskService", FakeTaskService)
    monkeypatch.setattr(partner_aliases, "PartnerAliasService", FakePartnerAliasService)
    monkeypatch.setattr(partner_aliases, "ChatBlockService", FakeChatBlockService)

    await partner_aliases.maybe_prompt_couple_creator_for_joined_partner(
        bot=bot,
        dispatcher=dispatcher,
        session=None,
        result=result,
    )

    assert FakePartnerAliasService.checks == [(creator.id, joined.id)]
    assert dispatcher.fsm.context_args == {"bot": bot, "chat_id": creator.telegram_id, "user_id": creator.telegram_id}
    assert state.state == PartnerAliasStates.waiting_for_emoji
    assert state.data == {"partner_user_id": joined.id}
    assert bot.sent_messages[0]["chat_id"] == creator.telegram_id
    assert "Партнер подключился" in bot.sent_messages[0]["text"]
    assert FakeChatBlockService.events == [
        "reset:1:100:partner_alias",
        "remember:1:100:partner_alias:1000",
    ]


@pytest.mark.asyncio
async def test_creator_prompt_is_skipped_when_alias_already_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    creator = User(id=1, telegram_id=100, username="one", first_name="One")
    joined = User(id=2, telegram_id=200, username="two", first_name="Two")
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=joined)
    state = FakeState()
    bot = FakeBot()
    dispatcher = FakeDispatcher(state)
    FakeTaskService.members = [creator, joined]
    FakePartnerAliasService.has_alias = True
    FakePartnerAliasService.checks = []
    FakeChatBlockService.events = []

    monkeypatch.setattr(partner_aliases, "TaskService", FakeTaskService)
    monkeypatch.setattr(partner_aliases, "PartnerAliasService", FakePartnerAliasService)
    monkeypatch.setattr(partner_aliases, "ChatBlockService", FakeChatBlockService)

    await partner_aliases.maybe_prompt_couple_creator_for_joined_partner(
        bot=bot,
        dispatcher=dispatcher,
        session=None,
        result=result,
    )

    assert FakePartnerAliasService.checks == [(creator.id, joined.id)]
    assert bot.sent_messages == []
    assert state.state is None
    assert FakeChatBlockService.events == []
