from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Couple, CoupleMember, User


class CoupleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_membership(self, user_id: int) -> CoupleMember | None:
        result = await self.session.execute(
            select(CoupleMember)
            .where(CoupleMember.user_id == user_id)
            .options(selectinload(CoupleMember.couple))
        )
        return result.scalar_one_or_none()

    async def count_members(self, couple_id: int) -> int:
        result = await self.session.execute(
            select(func.count(CoupleMember.id)).where(CoupleMember.couple_id == couple_id)
        )
        return result.scalar_one()

    async def get_users_for_couple(self, couple_id: int) -> list[User]:
        result = await self.session.execute(
            select(User)
            .join(CoupleMember, CoupleMember.user_id == User.id)
            .where(CoupleMember.couple_id == couple_id)
            .order_by(CoupleMember.id)
        )
        return list(result.scalars().all())

    async def get_by_invite_code(self, invite_code: str) -> Couple | None:
        result = await self.session.execute(select(Couple).where(Couple.invite_code == invite_code))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Couple]:
        result = await self.session.execute(select(Couple).order_by(Couple.id))
        return list(result.scalars().all())

    async def create(self, invite_code: str, invite_expires_at, timezone: str) -> Couple:
        couple = Couple(
            invite_code=invite_code,
            invite_expires_at=invite_expires_at,
            timezone=timezone,
        )
        self.session.add(couple)
        await self.session.flush()
        return couple

    async def add_member(self, user_id: int, couple_id: int) -> CoupleMember:
        member = CoupleMember(user_id=user_id, couple_id=couple_id)
        self.session.add(member)
        await self.session.flush()
        return member
