from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.cozy import (
    CozyMessageGenerator,
    CozyMessageTheme,
    append_cozy_suffix,
    fallback_for_theme,
    sanitize_cozy_message,
)


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


@pytest.mark.asyncio
async def test_cozy_generator_uses_fallback_without_api_key() -> None:
    generator = CozyMessageGenerator(api_key="")

    message = await generator.generate(CozyMessageTheme.TASK_COMPLETED, subject="Помыть пол")

    assert message == fallback_for_theme(CozyMessageTheme.TASK_COMPLETED)


@pytest.mark.asyncio
async def test_cozy_generator_uses_guardrails_and_sanitizes_response() -> None:
    client = FakeClient("  Первое предложение. Второе предложение! Третье уже лишнее.  ")
    generator = CozyMessageGenerator(client=client)

    message = await generator.generate(CozyMessageTheme.TASK_COMPLETED, subject="Помыть пол")

    assert message == "Первое предложение. Второе предложение!"
    request = client.completions.requests[0]
    assert request["model"] == "gpt-4o-mini"
    assert "Maximum 1-2 sentences" in request["messages"][0]["content"]
    assert "Theme: completed household task." in request["messages"][1]["content"]
    assert "Помыть пол" in request["messages"][1]["content"]


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
