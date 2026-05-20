from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, InlineKeyboardMarkup

from app.models import User
from app.notifications.cats import CatNotificationType, select_cat_asset

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NotificationDeliveryResult:
    delivered: bool
    used_photo: bool = False


async def send_user_notification(
    bot: Bot,
    user: User,
    text: str,
    *,
    cat_notification_type: CatNotificationType | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> NotificationDeliveryResult:
    cat_asset = select_cat_asset(cat_notification_type)
    if cat_asset is not None:
        try:
            await bot.send_photo(
                user.telegram_id,
                FSInputFile(cat_asset),
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return NotificationDeliveryResult(delivered=True, used_photo=True)
        except TelegramAPIError:
            logger.exception("Failed to send notification photo")

    try:
        await bot.send_message(
            user.telegram_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return NotificationDeliveryResult(delivered=True)
    except TelegramAPIError:
        logger.exception("Failed to send notification message")
        return NotificationDeliveryResult(delivered=False)
