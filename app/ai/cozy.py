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
    RECAP = "recap"
    CAT_CAPTION = "cat_caption"


THEME_LABELS = {
    CozyMessageTheme.TASK_COMPLETED: "completed household task",
    CozyMessageTheme.TASK_ASSIGNED: "new household task",
    CozyMessageTheme.TASK_CLAIMED: "claimed household task",
    CozyMessageTheme.TASK_ARCHIVED: "stopped or removed household task",
    CozyMessageTheme.CONTENT_COMPLETED: "completed shared content",
    CozyMessageTheme.PLACE_VISITED: "visited shared place",
    CozyMessageTheme.RECAP: "short couple recap",
    CozyMessageTheme.CAT_CAPTION: "cat caption",
}

FALLBACK_MESSAGES = {
    CozyMessageTheme.TASK_COMPLETED: "Маленькая бытовая победа засчитана. Котики одобрительно щурятся.",
    CozyMessageTheme.TASK_ASSIGNED: "Появилась маленькая домашняя миссия. Котики держат хвост трубой.",
    CozyMessageTheme.TASK_CLAIMED: "Задача нашла своего героя. Где-то рядом довольно мурчит невидимый кот.",
    CozyMessageTheme.TASK_ARCHIVED: "Домашний список стал чуточку легче. Котики спокойно кивают.",
    CozyMessageTheme.CONTENT_COMPLETED: "Общее культурное досье пополнилось. Плед и котик мысленно уже рядом.",
    CozyMessageTheme.PLACE_VISITED: "Общая карта воспоминаний получила новую отметку. Котики одобрительно сверились с маршрутом.",
    CozyMessageTheme.RECAP: "День стал немного собраннее и теплее. Котики записали это в хорошие новости.",
    CozyMessageTheme.CAT_CAPTION: "Котик смотрит так, будто все понял и никому не расскажет.",
}

SYSTEM_PROMPT = (
    "Generate a short cozy Russian message for a couple. "
    "Tone: warm, playful, soft. Maximum 1-2 sentences. "
    "Include subtle cat energy. Avoid cringe, excessive enthusiasm, therapy language, "
    "emotional manipulation, advice, and long responses."
)


def fallback_for_theme(theme: CozyMessageTheme) -> str:
    return FALLBACK_MESSAGES.get(theme, FALLBACK_MESSAGES[CozyMessageTheme.RECAP])


def build_cozy_prompt(theme: CozyMessageTheme, subject: str | None = None) -> str:
    prompt = f"Theme: {THEME_LABELS.get(theme, theme.value)}."
    if subject:
        prompt = f"{prompt} Context: {subject.strip()[:120]}."
    return prompt


def sanitize_cozy_message(value: str | None, fallback: str, *, max_chars: int = MAX_COZY_CHARS) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip()).strip(" \"'«»")
    if not normalized:
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
        model: str = "gpt-4o-mini",
        settings: Settings | None = None,
    ) -> None:
        if api_key is None and client is None:
            settings = settings or get_settings()
            if settings.openai_api_key is not None:
                configured_key = settings.openai_api_key.get_secret_value().strip()
                api_key = configured_key or None

        self.api_key = api_key
        self.client = client
        self.model = model

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
                    max_tokens=80,
                    temperature=0.7,
                ),
                timeout=AI_TIMEOUT_SECONDS,
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
