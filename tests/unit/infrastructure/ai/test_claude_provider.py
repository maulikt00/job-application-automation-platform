"""Tests for ClaudeProvider -- entirely mocked, no real Anthropic API
call anywhere. There is no API key or network access assumption this
project should rely on in its test suite, and even with a real key,
hitting a real, billed API in automated tests would be wrong (cost,
determinism, CI credentials). Every test here injects a hand-built fake
client via ClaudeProvider's constructor parameter, matching the real
`anthropic` SDK's actual response shape (Message/TextBlock/Usage) --
verified against the installed SDK directly during development, not
assumed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import anthropic
import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from jaap.infrastructure.ai.claude_provider import ClaudeProvider
from jaap.infrastructure.config.settings import Settings


def _make_message(*blocks: TextBlock | ToolUseBlock) -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-5",
        content=list(blocks),
        stop_reason="end_turn",
        stop_sequence=None,
        usage=Usage(input_tokens=10, output_tokens=5),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, anthropic_api_key="fake-key-for-tests")


@pytest.fixture
def fake_client():
    return MagicMock()


def test_generate_text_returns_the_response_text(settings: Settings, fake_client) -> None:
    fake_client.messages.create.return_value = _make_message(
        TextBlock(type="text", text="Generated cover letter text.")
    )
    provider = ClaudeProvider(settings, client=fake_client)

    result = provider.generate_text("Write a cover letter")

    assert result == "Generated cover letter text."


def test_generate_text_uses_model_and_max_tokens_from_settings(
    settings: Settings, fake_client
) -> None:
    fake_client.messages.create.return_value = _make_message(TextBlock(type="text", text="ok"))
    provider = ClaudeProvider(settings, client=fake_client)

    provider.generate_text("prompt")

    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == settings.anthropic_model
    assert call_kwargs["max_tokens"] == settings.anthropic_max_tokens


def test_generate_text_sends_the_prompt_as_a_user_message(
    settings: Settings, fake_client
) -> None:
    fake_client.messages.create.return_value = _make_message(TextBlock(type="text", text="ok"))
    provider = ClaudeProvider(settings, client=fake_client)

    provider.generate_text("Write a cover letter")

    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["messages"] == [{"role": "user", "content": "Write a cover letter"}]


def test_system_prompt_is_passed_through_when_given(settings: Settings, fake_client) -> None:
    fake_client.messages.create.return_value = _make_message(TextBlock(type="text", text="ok"))
    provider = ClaudeProvider(settings, client=fake_client)

    provider.generate_text("prompt", system_prompt="Be concise")

    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "Be concise"


def test_system_prompt_defaults_to_the_sdks_omit_sentinel_when_not_given(
    settings: Settings, fake_client
) -> None:
    # Regression test: an earlier version of this code passed
    # anthropic.NOT_GIVEN (the wrong sentinel type) here, which mypy
    # caught -- `system` specifically expects `anthropic.Omit`.
    fake_client.messages.create.return_value = _make_message(TextBlock(type="text", text="ok"))
    provider = ClaudeProvider(settings, client=fake_client)

    provider.generate_text("prompt")

    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] is anthropic.omit


def test_multiple_text_blocks_are_concatenated(settings: Settings, fake_client) -> None:
    fake_client.messages.create.return_value = _make_message(
        TextBlock(type="text", text="First part. "),
        TextBlock(type="text", text="Second part."),
    )
    provider = ClaudeProvider(settings, client=fake_client)

    result = provider.generate_text("prompt")

    assert result == "First part. Second part."


def test_non_text_blocks_are_ignored_when_a_text_block_is_also_present(
    settings: Settings, fake_client
) -> None:
    fake_client.messages.create.return_value = _make_message(
        ToolUseBlock(type="tool_use", id="t1", name="some_tool", input={}),
        TextBlock(type="text", text="The actual text response."),
    )
    provider = ClaudeProvider(settings, client=fake_client)

    result = provider.generate_text("prompt")

    assert result == "The actual text response."


def test_raises_a_clear_error_when_response_has_no_text_content(
    settings: Settings, fake_client
) -> None:
    fake_client.messages.create.return_value = _make_message(
        ToolUseBlock(type="tool_use", id="t1", name="some_tool", input={})
    )
    provider = ClaudeProvider(settings, client=fake_client)

    with pytest.raises(ValueError, match="no text content"):
        provider.generate_text("prompt")


def test_constructor_builds_a_real_client_when_none_is_injected(settings: Settings) -> None:
    # Confirms the "simple to use for real" half of the design: no client
    # argument needed for actual use, only for tests.
    provider = ClaudeProvider(settings)

    assert isinstance(provider._client, anthropic.Anthropic)
