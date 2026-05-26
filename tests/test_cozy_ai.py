from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.cozy import (
    CozyMessageGenerator,
    CozyMessageTheme,
    append_cozy_suffix,
    build_cozy_prompt,
    fallback_for_theme,
    sanitize_cozy_message,
)
from app.core.config import Settings


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.requests: list[dict] = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class FakeClient:
    def __init__(self, content: str) -> None:
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


class FailingCompletions:
    async def create(self, **_kwargs):
        raise RuntimeError("provider unavailable")


class FailingClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FailingCompletions())


@pytest.mark.asyncio
async def test_cozy_generator_uses_fallback_without_api_key() -> None:
    generator = CozyMessageGenerator(api_key="", settings=Settings())

    message = await generator.generate(CozyMessageTheme.TASK_COMPLETED, subject="Помыть пол")

    assert message == fallback_for_theme(CozyMessageTheme.TASK_COMPLETED)


@pytest.mark.asyncio
async def test_cozy_generator_uses_guardrails_and_sanitizes_response() -> None:
    client = FakeClient("  Первое предложение. Второе предложение! Третье уже лишнее.  ")
    generator = CozyMessageGenerator(client=client, settings=Settings())

    message = await generator.generate(CozyMessageTheme.TASK_COMPLETED, subject="Помыть пол")

    assert message == "Первое предложение. Второе предложение!"
    request = client.completions.requests[0]
    assert request["model"] == "gpt-4o-mini"
    assert "до 160 символов" in request["messages"][0]["content"]
    assert "Не используй HTML" in request["messages"][0]["content"]
    assert "Событие: завершена бытовая задача." in request["messages"][1]["content"]
    assert "Помыть пол" in request["messages"][1]["content"]


@pytest.mark.asyncio
async def test_cozy_generator_uses_configured_ai_runtime_settings() -> None:
    client = FakeClient("Тихая домашняя победа уже на месте.")
    settings = Settings.model_validate(
        {
            "OPENAI_MODEL": "gpt-test-cozy",
            "OPENAI_TIMEOUT_SECONDS": 8,
            "OPENAI_MAX_TOKENS": 120,
            "OPENAI_TEMPERATURE": 0.2,
        }
    )
    generator = CozyMessageGenerator(client=client, settings=settings)

    await generator.generate(CozyMessageTheme.CONTENT_COMPLETED, subject="Дюна")

    request = client.completions.requests[0]
    assert request["model"] == "gpt-test-cozy"
    assert request["max_tokens"] == 120
    assert request["temperature"] == 0.2


@pytest.mark.asyncio
async def test_cozy_generator_uses_fallback_when_provider_fails() -> None:
    generator = CozyMessageGenerator(client=FailingClient(), settings=Settings())

    message = await generator.generate(CozyMessageTheme.PLACE_VISITED, subject="Sage", fallback="Запасная фраза.")

    assert message == "Запасная фраза."


@pytest.mark.asyncio
async def test_append_cozy_suffix_keeps_plain_notifications_when_theme_is_absent() -> None:
    text = await append_cozy_suffix("Готово.", theme=None)

    assert text == "Готово."


@pytest.mark.asyncio
async def test_append_cozy_suffix_can_escape_html_for_markup_notifications() -> None:
    class FakeGenerator:
        async def generate(self, *_args, **_kwargs) -> str:
            return "Sage <3 & дом"

    text = await append_cozy_suffix(
        "<b>Готово.</b>",
        theme=CozyMessageTheme.TASK_COMPLETED,
        generator=FakeGenerator(),
        escape_suffix=True,
    )

    assert text == "<b>Готово.</b>\n\nSage &lt;3 &amp; дом"


def test_sanitize_cozy_message_limits_length() -> None:
    long_message = " ".join(["котик"] * 80)

    message = sanitize_cozy_message(long_message, "Запасная фраза.", max_chars=40)

    assert len(message) <= 41
    assert message.endswith(".")


def test_sanitize_cozy_message_removes_markup_boilerplate_and_placeholders() -> None:
    message = sanitize_cozy_message("Конечно, вот вариант: <b>Дом стал спокойнее.</b>", "Запасная фраза.")

    assert message == "Дом стал спокойнее."
    assert sanitize_cozy_message("placeholder text", "Запасная фраза.") == "Запасная фраза."


def test_cozy_prompt_uses_specific_context_for_evening_digest() -> None:
    prompt = build_cozy_prompt(CozyMessageTheme.EVENING_DIGEST, "Вечерняя сверка: активных задач 2.")

    assert "Событие: вечерняя сверка." in prompt
    assert "мягкого закрытия дня" in prompt
    assert "активных задач 2" in prompt
