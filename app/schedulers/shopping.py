from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.couples import CoupleRepository
from app.services.shopping import ShoppingContext, ShoppingService

logger = logging.getLogger(__name__)


async def archive_expired_shopping_items(session_maker: async_sessionmaker[AsyncSession]) -> None:
    async with session_maker() as session:
        try:
            couples = await CoupleRepository(session).list_all()
            now = datetime.now(timezone.utc)
            archived_count = 0
            for couple in couples:
                members = await CoupleRepository(session).get_users_for_couple(couple.id)
                if not members:
                    continue

                context = ShoppingContext(couple=couple, current_user=members[0], members=members)
                archived_count += await ShoppingService(session).archive_expired_bought_items_for_context(
                    context,
                    now=now,
                )

            await session.commit()
            if archived_count:
                logger.info("Archived %s expired shopping items", archived_count)
        except Exception:
            await session.rollback()
            logger.exception("Failed to archive expired shopping items")


def setup_shopping_cleanup_scheduler(session_maker: async_sessionmaker[AsyncSession]) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        archive_expired_shopping_items,
        "interval",
        minutes=1,
        args=[session_maker],
        id="shopping_midnight_cleanup",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
