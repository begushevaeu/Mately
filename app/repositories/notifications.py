from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_dedupe_key(self, dedupe_key: str, couple_id: int) -> Notification | None:
        result = await self.session.execute(
            select(Notification).where(Notification.dedupe_key == dedupe_key, Notification.couple_id == couple_id)
        )
        return result.scalar_one_or_none()

    async def create_pending(
        self,
        *,
        couple_id: int,
        user_id: int,
        notification_type: str,
        scheduled_at: datetime,
        dedupe_key: str,
        payload: dict | None = None,
    ) -> Notification:
        notification = Notification(
            couple_id=couple_id,
            user_id=user_id,
            type=notification_type,
            payload=payload,
            scheduled_at=scheduled_at,
            dedupe_key=dedupe_key,
            status="PENDING",
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def mark_sent(self, notification: Notification, *, delivered_at: datetime) -> Notification:
        notification.status = "SENT"
        notification.delivered_at = delivered_at
        await self.session.flush()
        return notification

    async def mark_failed(self, notification: Notification) -> Notification:
        notification.status = "FAILED"
        await self.session.flush()
        return notification
