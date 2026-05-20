from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import Settings
from app.models import Couple, CoupleMember, User
from app.services.couples import (
    CoupleService,
    MAX_PROFILE_TEXT_LENGTH,
    OnboardingStatus,
    TelegramUserProfile,
    generate_invite_code,
    is_valid_invite_code,
    normalize_invite_code,
)


@dataclass(slots=True)
class FakeRepositories:
    users: FakeUserRepository
    couples: FakeCoupleRepository


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self.next_id = 1

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return next((user for user in self.users.values() if user.telegram_id == telegram_id), None)

    async def create(self, telegram_id: int, username: str | None, first_name: str | None) -> User:
        user = User(id=self.next_id, telegram_id=telegram_id, username=username, first_name=first_name)
        self.next_id += 1
        self.users[user.id] = user
        return user

    async def update_profile(self, user: User, username: str | None, first_name: str | None) -> User:
        user.username = username
        user.first_name = first_name
        return user


class FakeCoupleRepository:
    def __init__(self) -> None:
        self.couples: dict[int, Couple] = {}
        self.memberships: list[CoupleMember] = []
        self.next_id = 1
        self.next_member_id = 1

    async def get_membership(self, user_id: int) -> CoupleMember | None:
        for membership in self.memberships:
            if membership.user_id == user_id:
                membership.couple = self.couples[membership.couple_id]
                return membership
        return None

    async def count_members(self, couple_id: int) -> int:
        return len([membership for membership in self.memberships if membership.couple_id == couple_id])

    async def get_by_invite_code(self, invite_code: str) -> Couple | None:
        return next((couple for couple in self.couples.values() if couple.invite_code == invite_code), None)

    async def lock_by_id(self, couple_id: int) -> Couple | None:
        return self.couples.get(couple_id)

    async def create(self, invite_code: str, invite_expires_at, timezone: str) -> Couple:
        couple = Couple(
            id=self.next_id,
            invite_code=invite_code,
            invite_expires_at=invite_expires_at,
            timezone=timezone,
        )
        self.next_id += 1
        self.couples[couple.id] = couple
        return couple

    async def add_member(self, user_id: int, couple_id: int) -> CoupleMember:
        membership = CoupleMember(id=self.next_member_id, user_id=user_id, couple_id=couple_id)
        membership.couple = self.couples[couple_id]
        self.next_member_id += 1
        self.memberships.append(membership)
        return membership


def build_service() -> CoupleService:
    users = FakeUserRepository()
    couples = FakeCoupleRepository()
    settings = Settings.model_validate(
        {
            "BOT_TOKEN": "",
            "DATABASE_URL": "postgresql+asyncpg://mately:mately@127.0.0.1:5432/mately",
            "DEFAULT_TIMEZONE": "Europe/Moscow",
            "INVITE_CODE_TTL_HOURS": "168",
        }
    )
    service = CoupleService(settings=settings, users=users, couples=couples)
    service.fake_repositories = FakeRepositories(users=users, couples=couples)  # type: ignore[attr-defined]
    return service


def test_invite_code_helpers_keep_codes_readable() -> None:
    code = generate_invite_code()

    assert len(code) == 8
    assert normalize_invite_code(" abcd-1234 ") == "ABCD1234"
    assert is_valid_invite_code(code) is True
    assert is_valid_invite_code("BAD!") is False


@pytest.mark.asyncio
async def test_user_can_create_couple_and_partner_can_join() -> None:
    service = build_service()
    creator = await service.get_or_register_user(TelegramUserProfile(telegram_id=1, username="one", first_name="One"))
    partner = await service.get_or_register_user(TelegramUserProfile(telegram_id=2, username="two", first_name="Two"))

    created_result = await service.create_couple(creator)
    joined_result = await service.join_couple(partner, created_result.invite_code or "")

    assert created_result.status is OnboardingStatus.WAITING_FOR_PARTNER
    assert joined_result.status is OnboardingStatus.IN_COUPLE
    assert (await service.get_current_state(creator)).status is OnboardingStatus.IN_COUPLE


@pytest.mark.asyncio
async def test_expired_invite_code_is_rejected() -> None:
    service = build_service()
    repositories = service.fake_repositories  # type: ignore[attr-defined]
    user = await service.get_or_register_user(TelegramUserProfile(telegram_id=1, username=None, first_name=None))
    expired_couple = Couple(
        id=1,
        invite_code="OLD12345",
        invite_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        timezone="Europe/Moscow",
    )
    repositories.couples.couples[expired_couple.id] = expired_couple

    result = await service.join_couple(user, "OLD12345")

    assert result.status is OnboardingStatus.INVALID_OR_EXPIRED_INVITE


@pytest.mark.asyncio
async def test_invalid_invite_code_shape_is_rejected_before_lookup() -> None:
    service = build_service()
    user = await service.get_or_register_user(TelegramUserProfile(telegram_id=1, username=None, first_name=None))

    result = await service.join_couple(user, "not a valid invite code")

    assert result.status is OnboardingStatus.INVALID_OR_EXPIRED_INVITE


@pytest.mark.asyncio
async def test_telegram_profile_is_validated_and_trimmed() -> None:
    service = build_service()

    user = await service.get_or_register_user(
        TelegramUserProfile(
            telegram_id=1,
            username="  one   user  ",
            first_name="x" * (MAX_PROFILE_TEXT_LENGTH + 10),
        )
    )

    assert user.username == "one user"
    assert user.first_name == "x" * MAX_PROFILE_TEXT_LENGTH


@pytest.mark.asyncio
async def test_invalid_telegram_id_is_rejected() -> None:
    service = build_service()

    with pytest.raises(ValueError, match="invalid Telegram user id"):
        await service.get_or_register_user(TelegramUserProfile(telegram_id=0, username=None, first_name=None))


@pytest.mark.asyncio
async def test_full_couple_is_rejected() -> None:
    service = build_service()
    repositories = service.fake_repositories  # type: ignore[attr-defined]
    couple = Couple(
        id=1,
        invite_code="FULL2234",
        invite_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        timezone="Europe/Moscow",
    )
    repositories.couples.couples[couple.id] = couple
    await repositories.couples.add_member(user_id=10, couple_id=couple.id)
    await repositories.couples.add_member(user_id=11, couple_id=couple.id)
    user = await service.get_or_register_user(TelegramUserProfile(telegram_id=3, username=None, first_name=None))

    result = await service.join_couple(user, "FULL2234")

    assert result.status is OnboardingStatus.COUPLE_FULL
