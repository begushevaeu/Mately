from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PartnerAlias


class PartnerAliasRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, owner_user_id: int, partner_user_id: int) -> PartnerAlias | None:
        result = await self.session.execute(
            select(PartnerAlias).where(
                PartnerAlias.owner_user_id == owner_user_id,
                PartnerAlias.partner_user_id == partner_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        owner_user_id: int,
        partner_user_id: int,
        emoji: str,
        nominative: str,
        genitive: str,
        dative: str,
    ) -> PartnerAlias:
        alias = await self.get(owner_user_id, partner_user_id)
        if alias is None:
            alias = PartnerAlias(
                owner_user_id=owner_user_id,
                partner_user_id=partner_user_id,
                emoji=emoji,
                nominative=nominative,
                genitive=genitive,
                dative=dative,
            )
            self.session.add(alias)
        else:
            alias.emoji = emoji
            alias.nominative = nominative
            alias.genitive = genitive
            alias.dative = dative

        await self.session.flush()
        return alias
