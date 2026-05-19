from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PartnerAlias, User
from app.repositories.partner_aliases import PartnerAliasRepository


@dataclass(slots=True)
class PartnerAliasInput:
    emoji: str
    nominative: str
    genitive: str
    dative: str


@dataclass(slots=True)
class DisplayName:
    emoji: str
    nominative: str
    genitive: str
    dative: str

    @property
    def nominative_with_emoji(self) -> str:
        return f"{self.emoji} {self.nominative}".strip()

    @property
    def genitive_with_emoji(self) -> str:
        return f"{self.emoji} {self.genitive}".strip()

    @property
    def dative_with_emoji(self) -> str:
        return f"{self.emoji} {self.dative}".strip()


def normalize_alias_value(value: str, *, max_length: int = 64) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("empty alias value")
    if len(normalized) > max_length:
        raise ValueError("alias value is too long")
    return normalized


def display_from_alias(alias: PartnerAlias) -> DisplayName:
    return DisplayName(
        emoji=alias.emoji,
        nominative=alias.nominative,
        genitive=alias.genitive,
        dative=alias.dative,
    )


def fallback_display_for_user(user: User) -> DisplayName:
    name = user.first_name or user.username or "партнер"
    return DisplayName(emoji="", nominative=name, genitive=name, dative=name)


class PartnerAliasService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        aliases: PartnerAliasRepository | None = None,
    ) -> None:
        if session is None and aliases is None:
            raise ValueError("session is required when repository is not provided")
        self.aliases = aliases or PartnerAliasRepository(session)  # type: ignore[arg-type]

    async def get_display_for(self, *, owner: User, partner: User) -> DisplayName:
        alias = await self.aliases.get(owner_user_id=owner.id, partner_user_id=partner.id)
        if alias is None:
            return fallback_display_for_user(partner)
        return display_from_alias(alias)

    async def has_alias_for(self, *, owner: User, partner: User) -> bool:
        return await self.aliases.get(owner_user_id=owner.id, partner_user_id=partner.id) is not None

    async def save_alias(self, *, owner: User, partner: User, alias_input: PartnerAliasInput) -> PartnerAlias:
        return await self.aliases.upsert(
            owner_user_id=owner.id,
            partner_user_id=partner.id,
            emoji=normalize_alias_value(alias_input.emoji, max_length=16),
            nominative=normalize_alias_value(alias_input.nominative),
            genitive=normalize_alias_value(alias_input.genitive),
            dative=normalize_alias_value(alias_input.dative),
        )
