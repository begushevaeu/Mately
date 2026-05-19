from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.main_menu import (
    CONTENT_BUTTON,
    SETTINGS_BUTTON,
    SHOPPING_BUTTON,
    STATISTICS_BUTTON,
    build_main_menu,
)
from app.bot.keyboards.settings import build_settings_keyboard
from app.services.couples import OnboardingResult, OnboardingStatus

router = Router()


async def ensure_main_menu_access(message: Message, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return None

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return None

    return result


@router.message(F.text == CONTENT_BUTTON)
async def handle_content_menu(message: Message, session: AsyncSession) -> None:
    if await ensure_main_menu_access(message, session) is None:
        return

    await message.answer(
        "Контент будет жить здесь: фильмы, книги, сериалы и оценки. Раздел подключим после задач и покупок.",
        reply_markup=build_main_menu(),
    )


@router.message(F.text == SHOPPING_BUTTON)
async def handle_shopping_menu(message: Message, session: AsyncSession) -> None:
    if await ensure_main_menu_access(message, session) is None:
        return

    await message.answer(
        "Список покупок будет здесь. В ближайшем шаге добавлю добавление пунктов и отметку «куплено».",
        reply_markup=build_main_menu(),
    )


@router.message(F.text == STATISTICS_BUTTON)
async def handle_statistics_menu(message: Message, session: AsyncSession) -> None:
    if await ensure_main_menu_access(message, session) is None:
        return

    await message.answer(
        "Статистика появится после первых задач и отметок контента. Пока тут будет тихий уголок ожидания.",
        reply_markup=build_main_menu(),
    )


@router.message(F.text == SETTINGS_BUTTON)
async def handle_settings_menu(message: Message, session: AsyncSession) -> None:
    result = await ensure_main_menu_access(message, session)
    if result is None:
        return

    timezone = result.couple.timezone if result.couple is not None else "Europe/Moscow"
    await message.answer(
        "Настройки Mately\n\n"
        f"Часовой пояс пары: {timezone}\n"
        "Доступные команды: /menu, /cancel, /help",
        reply_markup=build_settings_keyboard(),
    )


@router.message(F.text)
async def handle_unknown_menu_text(message: Message, session: AsyncSession) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return

    await message.answer(
        "Я пока не знаю такую команду. Выберите раздел из меню.",
        reply_markup=build_main_menu(),
    )
