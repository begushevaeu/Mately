from __future__ import annotations

import asyncio
import logging
import re
from enum import StrEnum
from html import escape as escape_html
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

MAX_COZY_CHARS = 180
AI_TIMEOUT_SECONDS = 6


class CozyMessageTheme(StrEnum):
    TASK_COMPLETED = "task_completed"
    TASK_ASSIGNED = "task_assigned"
    TASK_CLAIMED = "task_claimed"
    TASK_ARCHIVED = "task_archived"
    CONTENT_COMPLETED = "content_completed"
    PLACE_VISITED = "place_visited"
    MORNING_DIGEST = "morning_digest"
    EVENING_DIGEST = "evening_digest"
    RECAP = "recap"
    CAT_CAPTION = "cat_caption"


THEME_LABELS = {
    CozyMessageTheme.TASK_COMPLETED: "завершена бытовая задача",
    CozyMessageTheme.TASK_ASSIGNED: "назначена новая бытовая задача",
    CozyMessageTheme.TASK_CLAIMED: "партнёр взял задачу",
    CozyMessageTheme.TASK_ARCHIVED: "задача убрана из списка",
    CozyMessageTheme.CONTENT_COMPLETED: "завершён общий контент",
    CozyMessageTheme.PLACE_VISITED: "отмечено посещённое место",
    CozyMessageTheme.MORNING_DIGEST: "утренний дайджест",
    CozyMessageTheme.EVENING_DIGEST: "вечерняя сверка",
    CozyMessageTheme.RECAP: "короткая сводка пары",
    CozyMessageTheme.CAT_CAPTION: "подпись к котику",
}

THEME_INSTRUCTIONS = {
    CozyMessageTheme.TASK_COMPLETED: "Партнёр завершил бытовую задачу. Отметь маленькое домашнее облегчение.",
    CozyMessageTheme.TASK_ASSIGNED: "Появилась задача для партнёра. Поддержи спокойно, без давления и команд.",
    CozyMessageTheme.TASK_CLAIMED: "Партнёр взял задачу себе. Передай ощущение заботы и движения.",
    CozyMessageTheme.TASK_ARCHIVED: "Задачу убрали из списка. Сообщение должно звучать как мягкое наведение порядка.",
    CozyMessageTheme.CONTENT_COMPLETED: "Пара закончила смотреть, читать или проходить общий контент. Можно намекнуть на оценку.",
    CozyMessageTheme.PLACE_VISITED: "Пара отметила посещённое место. Сфокусируйся на общем воспоминании.",
    CozyMessageTheme.MORNING_DIGEST: "Это утренний список незавершённых задач. Поддержи спокойный старт дня.",
    CozyMessageTheme.EVENING_DIGEST: "Это вечерняя сверка активных задач. Дай ощущение мягкого закрытия дня.",
    CozyMessageTheme.RECAP: "Это короткая сводка периода для пары. Подчеркни спокойный общий прогресс.",
    CozyMessageTheme.CAT_CAPTION: "Нужна короткая подпись к кото-картинке в тёплом стиле приложения.",
}

FALLBACK_MESSAGES = {
    CozyMessageTheme.TASK_COMPLETED: "Готово: дома стало на одну заботу легче.",
    CozyMessageTheme.TASK_ASSIGNED: "Задача добавлена, без спешки: пусть спокойно дождётся своего момента.",
    CozyMessageTheme.TASK_CLAIMED: "Задача нашла руки, которые её заберут.",
    CozyMessageTheme.TASK_ARCHIVED: "Убрала это из домашнего списка, стало чуть просторнее.",
    CozyMessageTheme.CONTENT_COMPLETED: "Ещё одна общая история завершена, можно поставить ей место в памяти.",
    CozyMessageTheme.PLACE_VISITED: "На общей карте появилось новое место для воспоминаний.",
    CozyMessageTheme.MORNING_DIGEST: "Доброе утро. Держим день спокойным и берём задачи по одной.",
    CozyMessageTheme.EVENING_DIGEST: "Вечерняя сверка готова: можно закрыть день без лишнего шума.",
    CozyMessageTheme.RECAP: "День стал чуть собраннее; можно выдохнуть и идти дальше мягко.",
    CozyMessageTheme.CAT_CAPTION: "Смотрит так, будто всё понял и оставил при себе.",
}

SYSTEM_PROMPT = (
    "Ты пишешь короткую естественную фразу на русском для пары в Telegram. "
    "Одна фраза, максимум два коротких предложения и до 160 символов. "
    "Тон: тёплый, живой, спокойный, без сюсюканья и чрезмерного восторга. "
    "Лёгкая кошачья деталь допустима, но не обязательна. "
    "Не используй HTML, Markdown, списки, кавычки, эмодзи, хештеги, команды, советы, терапевтический тон, "
    "эмоциональное давление, слова «вариант», «сообщение», «тема» и упоминания ИИ."
)


def fallback_for_theme(theme: CozyMessageTheme) -> str:
    return FALLBACK_MESSAGES.get(theme, FALLBACK_MESSAGES[CozyMessageTheme.RECAP])


def normalize_cozy_subject(subject: str | None, *, max_chars: int = 160) -> str | None:
    normalized = re.sub(r"<[^>]+>", " ", subject or "")
    normalized = re.sub(r"\s+", " ", normalized).strip(" \"'«»`")
    if not normalized:
        return None
    if len(normalized) <= max_chars:
        return normalized
    truncated = normalized[: max_chars + 1].rsplit(" ", maxsplit=1)[0].rstrip(" ,;:")
    return f"{truncated}..."


def build_cozy_prompt(theme: CozyMessageTheme, subject: str | None = None) -> str:
    label = THEME_LABELS.get(theme, theme.value)
    instruction = THEME_INSTRUCTIONS.get(theme, THEME_INSTRUCTIONS[CozyMessageTheme.RECAP])
    context = normalize_cozy_subject(subject) or "нет дополнительной детали"
    return (
        f"Событие: {label}.\n"
        f"Смысл события: {instruction}\n"
        f"Деталь: {context}\n"
        "Верни только готовую фразу для отправки пользователю."
    )


def sanitize_cozy_message(value: str | None, fallback: str, *, max_chars: int = MAX_COZY_CHARS) -> str:
    normalized = re.sub(r"<[^>]+>", " ", value or "")
    normalized = re.sub(r"\s+", " ", normalized).strip(" \"'«»`*_")
    for _ in range(3):
        cleaned = re.sub(
            r"^(?:конечно|вот(?:\s+вариант)?|вариант|сообщение|фраза|ответ|тема)\s*[:—\-.,!]*\s*",
            "",
            normalized,
            flags=re.IGNORECASE,
        ).strip(" \"'«»`*_")
        if cleaned == normalized:
            break
        normalized = cleaned
    if not normalized:
        return fallback
    if re.search(r"\b(?:placeholder|заглушк|как\s+ии|я\s+ии)\b", normalized, flags=re.IGNORECASE):
        return fallback

    sentence_matches = list(re.finditer(r"[^.!?…]+[.!?…]?", normalized))
    if len(sentence_matches) > 2:
        normalized = "".join(match.group(0) for match in sentence_matches[:2]).strip()

    if len(normalized) > max_chars:
        truncated = normalized[: max_chars + 1].rsplit(" ", maxsplit=1)[0].rstrip(" ,;:")
        normalized = f"{truncated}."

    return normalized or fallback


class CozyMessageGenerator:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: Any | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        if api_key is None and client is None:
            if settings.openai_api_key is not None:
                configured_key = settings.openai_api_key.get_secret_value().strip()
                api_key = configured_key or None

        self.api_key = api_key
        self.client = client
        self.model = model or settings.openai_model
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.openai_timeout_seconds
        self.max_tokens = max_tokens if max_tokens is not None else settings.openai_max_tokens
        self.temperature = temperature if temperature is not None else settings.openai_temperature

    async def generate(self, theme: CozyMessageTheme, *, subject: str | None = None, fallback: str | None = None) -> str:
        safe_fallback = sanitize_cozy_message(fallback, fallback_for_theme(theme)) if fallback else fallback_for_theme(theme)
        if self.client is None and not self.api_key:
            return safe_fallback

        client = self.client or self._create_client()
        if client is None:
            return safe_fallback

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_cozy_prompt(theme, subject)},
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                ),
                timeout=self.timeout_seconds,
            )
            content = response.choices[0].message.content
        except Exception:
            logger.exception("Failed to generate cozy AI message")
            return safe_fallback

        return sanitize_cozy_message(content, safe_fallback)

    def _create_client(self) -> Any | None:
        if not self.api_key:
            return None

        try:
            from openai import AsyncOpenAI
        except ImportError:
            logger.exception("OpenAI package is not available")
            return None

        self.client = AsyncOpenAI(api_key=self.api_key)
        return self.client


async def append_cozy_suffix(
    base_text: str,
    *,
    theme: CozyMessageTheme | None,
    subject: str | None = None,
    generator: CozyMessageGenerator | None = None,
    escape_suffix: bool = False,
) -> str:
    if theme is None:
        return base_text

    cozy = await (generator or CozyMessageGenerator()).generate(theme, subject=subject)
    if not cozy:
        return base_text

    if escape_suffix:
        cozy = escape_html(cozy)

    return f"{base_text}\n\n{cozy}"
