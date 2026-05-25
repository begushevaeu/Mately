import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import build_main_menu
from app.bot.keyboards.onboarding import build_cancel_menu
from app.bot.keyboards.settings import SETUP_PARTNER_ALIAS_CALLBACK
from app.bot.states.partner_alias import PartnerAliasStates
from app.services.chat_blocks import ADDITIONAL_BLOCK_KEY, PARTNER_ALIAS_BLOCK_KEY, ChatBlockService
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile
from app.services.partner_aliases import PartnerAliasInput, PartnerAliasService, normalize_alias_value
from app.services.tasks import TaskService, TaskServiceError

router = Router()
logger = logging.getLogger(__name__)

INITIAL_ALIAS_PROMPT_TEXT = (
    "Давайте настроим, как партнер будет отображаться у тебя.\n\n"
    "Сначала отправь эмодзи для партнера. Например: 🥒"
)

CREATOR_ALIAS_PROMPT_TEXT = (
    "Партнер подключился к вашему пространству. Давайте настроим, как он будет отображаться у тебя.\n\n"
    "Сначала отправь эмодзи для партнера. Например: 🥒"
)


async def get_partner_for_alias(result: OnboardingResult, session: AsyncSession):
    context = await TaskService(session).get_context(result.user)
    return context.partner


async def result_from_message(message: Message, session: AsyncSession) -> OnboardingResult | None:
    if message.from_user is None:
        return None

    return await CoupleService(session).start_for_profile(
        TelegramUserProfile(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
    )


async def delete_user_alias_message(bot: Bot, message: Message) -> None:
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except TelegramAPIError:
        logger.debug("Failed to delete partner alias input message", exc_info=True)


async def add_alias_block_messages(
    session: AsyncSession,
    result: OnboardingResult,
    message: Message,
    messages: list[Message],
) -> None:
    await ChatBlockService(session).add_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=PARTNER_ALIAS_BLOCK_KEY,
        messages=messages,
    )


async def send_alias_prompt(
    message: Message,
    session: AsyncSession,
    result: OnboardingResult,
    text: str,
) -> Message:
    sent_message = await message.answer(text, reply_markup=build_cancel_menu())
    await add_alias_block_messages(session, result, message, [sent_message])
    return sent_message


async def reset_alias_block(bot: Bot, session: AsyncSession, result: OnboardingResult, chat_id: int) -> None:
    await ChatBlockService(session).reset_block(
        bot=bot,
        user=result.user,
        chat_id=chat_id,
        block_key=PARTNER_ALIAS_BLOCK_KEY,
    )


async def reset_additional_block(bot: Bot, session: AsyncSession, result: OnboardingResult, chat_id: int) -> None:
    await ChatBlockService(session).reset_block(
        bot=bot,
        user=result.user,
        chat_id=chat_id,
        block_key=ADDITIONAL_BLOCK_KEY,
    )


async def start_partner_alias_prompt(
    *,
    bot: Bot,
    session: AsyncSession,
    owner,
    partner,
    chat_id: int,
    state: FSMContext,
    text: str,
) -> bool:
    result = OnboardingResult(status=OnboardingStatus.IN_COUPLE, user=owner)
    await reset_alias_block(bot, session, result, chat_id)
    try:
        sent_message = await bot.send_message(chat_id, text, reply_markup=build_cancel_menu())
    except TelegramAPIError:
        logger.exception("Failed to send partner alias prompt")
        return False

    await state.set_state(PartnerAliasStates.waiting_for_emoji)
    await state.update_data(partner_user_id=partner.id)
    await add_alias_block_messages(session, result, sent_message, [sent_message])
    return True


async def maybe_prompt_partner_alias(
    message: Message,
    result: OnboardingResult,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    if result.status is not OnboardingStatus.IN_COUPLE:
        return

    try:
        partner = await get_partner_for_alias(result, session)
    except TaskServiceError:
        return

    if partner is None:
        return

    if await PartnerAliasService(session).has_alias_for(owner=result.user, partner=partner):
        return

    await start_partner_alias_prompt(
        bot=bot,
        session=session,
        owner=result.user,
        partner=partner,
        chat_id=message.chat.id,
        state=state,
        text=INITIAL_ALIAS_PROMPT_TEXT,
    )


async def maybe_prompt_couple_creator_for_joined_partner(
    *,
    bot: Bot,
    dispatcher: Dispatcher,
    session: AsyncSession,
    result: OnboardingResult,
) -> None:
    if result.status is not OnboardingStatus.IN_COUPLE:
        return

    try:
        context = await TaskService(session).get_context(result.user)
    except TaskServiceError:
        return

    creator = context.members[0] if context.members else None
    if creator is None or creator.id == result.user.id:
        return

    if await PartnerAliasService(session).has_alias_for(owner=creator, partner=result.user):
        return

    creator_state = dispatcher.fsm.get_context(
        bot=bot,
        chat_id=creator.telegram_id,
        user_id=creator.telegram_id,
    )
    await start_partner_alias_prompt(
        bot=bot,
        session=session,
        owner=creator,
        partner=result.user,
        chat_id=creator.telegram_id,
        state=creator_state,
        text=CREATOR_ALIAS_PROMPT_TEXT,
    )


@router.callback_query(F.data == SETUP_PARTNER_ALIAS_CALLBACK)
async def handle_setup_partner_alias(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    if callback.message is None:
        await callback.answer()
        return

    result = await CoupleService(session).start_for_profile(
        TelegramUserProfile(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
        )
    )
    if result.status is not OnboardingStatus.IN_COUPLE:
        await callback.answer("Сначала нужно быть в паре.", show_alert=True)
        return

    try:
        partner = await get_partner_for_alias(result, session)
    except TaskServiceError:
        await callback.answer("Партнер пока не найден.", show_alert=True)
        return

    if partner is None:
        await callback.answer("Партнер пока не найден.", show_alert=True)
        return

    await state.set_state(PartnerAliasStates.waiting_for_emoji)
    await state.update_data(partner_user_id=partner.id)
    await reset_alias_block(bot, session, result, callback.message.chat.id)
    await reset_additional_block(bot, session, result, callback.message.chat.id)
    await send_alias_prompt(callback.message, session, result, "Отправь эмодзи для партнера. Например: 🥒")
    await callback.answer()


@router.message(PartnerAliasStates.waiting_for_emoji)
async def handle_partner_alias_emoji(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await result_from_message(message, session)
    if result is None or result.status is not OnboardingStatus.IN_COUPLE:
        await state.clear()
        return

    await add_alias_block_messages(session, result, message, [message])
    await delete_user_alias_message(bot, message)
    try:
        emoji = normalize_alias_value(message.text or "", max_length=16)
    except ValueError:
        await send_alias_prompt(
            message,
            session,
            result,
            "Эмодзи не должно быть пустым. Отправь один короткий символ или сочетание.",
        )
        return

    await state.update_data(emoji=emoji)
    await state.set_state(PartnerAliasStates.waiting_for_nominative)
    await send_alias_prompt(
        message,
        session,
        result,
        "Теперь имя партнера в именительном падеже.\n"
        "Пример: Огурчик",
    )


@router.message(PartnerAliasStates.waiting_for_nominative)
async def handle_partner_alias_nominative(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await result_from_message(message, session)
    if result is None or result.status is not OnboardingStatus.IN_COUPLE:
        await state.clear()
        return

    await add_alias_block_messages(session, result, message, [message])
    await delete_user_alias_message(bot, message)
    try:
        nominative = normalize_alias_value(message.text or "")
    except ValueError:
        await send_alias_prompt(message, session, result, "Имя не должно быть пустым. Например: Огурчик")
        return

    await state.update_data(nominative=nominative)
    await state.set_state(PartnerAliasStates.waiting_for_genitive)
    await send_alias_prompt(
        message,
        session,
        result,
        "Теперь родительный падеж: задача от кого?\n"
        "Пример: Огурчика",
    )


@router.message(PartnerAliasStates.waiting_for_genitive)
async def handle_partner_alias_genitive(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await result_from_message(message, session)
    if result is None or result.status is not OnboardingStatus.IN_COUPLE:
        await state.clear()
        return

    await add_alias_block_messages(session, result, message, [message])
    await delete_user_alias_message(bot, message)
    try:
        genitive = normalize_alias_value(message.text or "")
    except ValueError:
        await send_alias_prompt(message, session, result, "Форма не должна быть пустой. Например: Огурчика")
        return

    await state.update_data(genitive=genitive)
    await state.set_state(PartnerAliasStates.waiting_for_dative)
    await send_alias_prompt(
        message,
        session,
        result,
        "И дательный падеж: отправить задачу кому?\n"
        "Пример: Огурчику",
    )


@router.message(PartnerAliasStates.waiting_for_dative)
async def handle_partner_alias_dative(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    if message.from_user is None:
        await state.clear()
        return

    result = await result_from_message(message, session)
    if result is None or result.status is not OnboardingStatus.IN_COUPLE:
        await state.clear()
        return

    await add_alias_block_messages(session, result, message, [message])
    await delete_user_alias_message(bot, message)
    data = await state.get_data()
    try:
        dative = normalize_alias_value(message.text or "")
        partner = await get_partner_for_alias(result, session)
    except (ValueError, TaskServiceError):
        await send_alias_prompt(message, session, result, "Форма не должна быть пустой. Например: Огурчику")
        return

    if partner is None or partner.id != data.get("partner_user_id"):
        await state.clear()
        await reset_alias_block(bot, session, result, message.chat.id)
        await message.answer("Не смогла сохранить имя партнера. Попробуй еще раз в настройках.", reply_markup=build_main_menu())
        return

    await PartnerAliasService(session).save_alias(
        owner=result.user,
        partner=partner,
        alias_input=PartnerAliasInput(
            emoji=data["emoji"],
            nominative=data["nominative"],
            genitive=data["genitive"],
            dative=dative,
        ),
    )
    await state.clear()
    await reset_alias_block(bot, session, result, message.chat.id)
    await message.answer(
        f"Готово. Теперь партнер будет отображаться как {data['emoji']}{data['nominative']}.",
        reply_markup=build_main_menu(),
    )
