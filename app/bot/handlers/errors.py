from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)
router = Router()

GENERIC_ERROR_TEXT = (
    "Что-то пошло не так, но я уже сбросила текущий ввод. "
    "Нажми /menu, и мы спокойно продолжим."
)
GENERIC_CALLBACK_ERROR_TEXT = "Что-то сломалось. Я сбросила текущий ввод, открой /menu."


@router.error()
async def handle_unexpected_error(event: ErrorEvent, state: FSMContext | None = None) -> bool:
    log_unexpected_error(event.exception)
    await clear_state_safely(state)
    await notify_user_about_error(event)
    return True


def log_unexpected_error(exception: BaseException) -> None:
    logger.error(
        "Unhandled bot update error",
        exc_info=(type(exception), exception, exception.__traceback__),
    )


async def clear_state_safely(state: FSMContext | None) -> None:
    if state is None:
        return

    with suppress(Exception):
        await state.clear()


async def notify_user_about_error(event: ErrorEvent) -> None:
    update = event.update
    callback = getattr(update, "callback_query", None)
    if callback is not None:
        await notify_callback_about_error(callback)
        return

    message = getattr(update, "message", None) or getattr(update, "edited_message", None)
    if message is not None:
        with suppress(Exception):
            await message.answer(GENERIC_ERROR_TEXT)


async def notify_callback_about_error(callback: Any) -> None:
    with suppress(Exception):
        await callback.answer(GENERIC_CALLBACK_ERROR_TEXT, show_alert=True)

    message = getattr(callback, "message", None)
    if message is not None and hasattr(message, "answer"):
        with suppress(Exception):
            await message.answer(GENERIC_ERROR_TEXT)
