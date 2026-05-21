from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from secrets import choice

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models import Couple, User
from app.repositories.couples import CoupleRepository
from app.repositories.users import UserRepository

INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITE_CODE_LENGTH = 8
MAX_TELEGRAM_ID = 2**63 - 1
MAX_PROFILE_TEXT_LENGTH = 255


class OnboardingStatus(StrEnum):
    NO_COUPLE = "NO_COUPLE"
    WAITING_FOR_PARTNER = "WAITING_FOR_PARTNER"
    IN_COUPLE = "IN_COUPLE"
    INVALID_OR_EXPIRED_INVITE = "INVALID_OR_EXPIRED_INVITE"
    COUPLE_FULL = "COUPLE_FULL"


@dataclass(slots=True)
class TelegramUserProfile:
    telegram_id: int
    username: str | None
    first_name: str | None


@dataclass(slots=True)
class OnboardingResult:
    status: OnboardingStatus
    user: User
    couple: Couple | None = None
    invite_code: str | None = None
    invite_expires_at: datetime | None = None


def generate_invite_code(length: int = INVITE_CODE_LENGTH) -> str:
    return "".join(choice(INVITE_CODE_ALPHABET) for _ in range(length))


def normalize_invite_code(invite_code: str) -> str:
    return "".join(
        character
        for character in invite_code.upper()
        if not character.isspace() and character != "-"
    )


def is_valid_invite_code(invite_code: str) -> bool:
    return len(invite_code) == INVITE_CODE_LENGTH and all(character in INVITE_CODE_ALPHABET for character in invite_code)


def validate_telegram_id(telegram_id: int) -> int:
    if not isinstance(telegram_id, int) or telegram_id <= 0 or telegram_id > MAX_TELEGRAM_ID:
        raise ValueError("invalid Telegram user id")
    return telegram_id


def normalize_profile_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    return normalized[:MAX_PROFILE_TEXT_LENGTH]


def normalize_telegram_profile(profile: TelegramUserProfile) -> TelegramUserProfile:
    return TelegramUserProfile(
        telegram_id=validate_telegram_id(profile.telegram_id),
        username=normalize_profile_text(profile.username),
        first_name=normalize_profile_text(profile.first_name),
    )


class CoupleService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        settings: Settings | None = None,
        users: UserRepository | None = None,
        couples: CoupleRepository | None = None,
    ) -> None:
        if session is None and (users is None or couples is None):
            raise ValueError("session is required when repositories are not provided")

        self.settings = settings or get_settings()
        self.users = users or UserRepository(session)  # type: ignore[arg-type]
        self.couples = couples or CoupleRepository(session)  # type: ignore[arg-type]

    async def get_or_register_user(self, profile: TelegramUserProfile) -> User:
        profile = normalize_telegram_profile(profile)
        user = await self.users.get_by_telegram_id(profile.telegram_id)
        if user is None:
            return await self.users.create(
                telegram_id=profile.telegram_id,
                username=profile.username,
                first_name=profile.first_name,
            )

        return await self.users.update_profile(
            user=user,
            username=profile.username,
            first_name=profile.first_name,
        )

    async def get_current_state(self, user: User) -> OnboardingResult:
        membership = await self.couples.get_membership(user.id)
        if membership is None:
            return OnboardingResult(status=OnboardingStatus.NO_COUPLE, user=user)

        member_count = await self.couples.count_members(membership.couple_id)
        if member_count < 2:
            return OnboardingResult(
                status=OnboardingStatus.WAITING_FOR_PARTNER,
                user=user,
                couple=membership.couple,
                invite_code=membership.couple.invite_code,
                invite_expires_at=membership.couple.invite_expires_at,
            )

        return OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user, couple=membership.couple)

    async def start_for_profile(self, profile: TelegramUserProfile) -> OnboardingResult:
        user = await self.get_or_register_user(profile)
        return await self.get_current_state(user)

    async def create_couple(self, user: User) -> OnboardingResult:
        current_state = await self.get_current_state(user)
        if current_state.status is not OnboardingStatus.NO_COUPLE:
            return current_state

        invite_code = await self._generate_unique_invite_code()
        invite_expires_at = datetime.now(timezone.utc) + timedelta(hours=self.settings.invite_code_ttl_hours)
        couple = await self.couples.create(
            invite_code=invite_code,
            invite_expires_at=invite_expires_at,
            timezone=self.settings.default_timezone,
        )
        await self.couples.add_member(user_id=user.id, couple_id=couple.id)

        return OnboardingResult(
            status=OnboardingStatus.WAITING_FOR_PARTNER,
            user=user,
            couple=couple,
            invite_code=couple.invite_code,
            invite_expires_at=couple.invite_expires_at,
        )

    async def join_couple(self, user: User, invite_code: str) -> OnboardingResult:
        current_state = await self.get_current_state(user)
        if current_state.status is OnboardingStatus.IN_COUPLE:
            return current_state

        normalized_code = normalize_invite_code(invite_code)
        if not is_valid_invite_code(normalized_code):
            return OnboardingResult(status=OnboardingStatus.INVALID_OR_EXPIRED_INVITE, user=user)

        couple = await self.couples.get_by_invite_code(normalized_code)
        if couple is None or self._is_invite_expired(couple):
            return OnboardingResult(status=OnboardingStatus.INVALID_OR_EXPIRED_INVITE, user=user)

        current_waiting_couple = None
        if current_state.status is OnboardingStatus.WAITING_FOR_PARTNER:
            current_waiting_couple = current_state.couple
            if current_waiting_couple is None:
                return current_state
            if couple.id == current_waiting_couple.id:
                return current_state

        await self.couples.lock_by_id(couple.id)
        member_count = await self.couples.count_members(couple.id)
        if member_count >= 2:
            return OnboardingResult(status=OnboardingStatus.COUPLE_FULL, user=user, couple=couple)

        if current_waiting_couple is not None:
            await self.couples.lock_by_id(current_waiting_couple.id)
            current_member_count = await self.couples.count_members(current_waiting_couple.id)
            if current_member_count >= 2:
                return await self.get_current_state(user)
            await self.couples.remove_member_and_empty_couple(
                user_id=user.id,
                couple_id=current_waiting_couple.id,
            )

        await self.couples.add_member(user_id=user.id, couple_id=couple.id)
        return OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=user, couple=couple)

    async def _generate_unique_invite_code(self) -> str:
        for _ in range(20):
            invite_code = generate_invite_code()
            if await self.couples.get_by_invite_code(invite_code) is None:
                return invite_code

        raise RuntimeError("Unable to generate unique invite code")

    @staticmethod
    def _is_invite_expired(couple: Couple) -> bool:
        return couple.invite_expires_at is not None and couple.invite_expires_at <= datetime.now(timezone.utc)
