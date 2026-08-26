"""Tests for OllamaProvider -- entirely mocked, no real Ollama server
required. Every test injects a hand-built fake client via OllamaProvider's
constructor parameter, matching the real `ollama` package's actual
response shape (ChatResponse/Message) -- verified against the installed
package directly during development, not assumed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import ollama
import pytest
from ollama._types import ChatResponse, Message

from jaap.domain.exceptions import AIProviderError
from jaap.infrastructure.ai.ollama_provider import OllamaProvider
from jaap.infrastructure.config.settings import Settings


def _make_response(content: str | None) -> ChatResponse:
    return ChatResponse(
        model="llama3.1",
        created_at="2026-01-01T00:00:00Z",
        done=True,
        message=Message(role="assistant", content=content),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def fake_client():
    return MagicMock()


def test_generate_text_returns_the_response_content(settings: Settings, fake_client) -> None:
    fake_client.chat.return_value = _make_response("Generated cover letter text.")
    provider = OllamaProvider(settings, client=fake_client)

    result = provider.generate_text("Write a cover letter")

    assert result == "Generated cover letter text."


def test_generate_text_uses_model_from_settings(settings: Settings, fake_client) -> None:
    fake_client.chat.return_value = _make_response("ok")
    provider = OllamaProvider(settings, client=fake_client)

    provider.generate_text("prompt")

    assert fake_client.chat.call_args.kwargs["model"] == settings.ollama_model


def test_max_tokens_is_mapped_to_num_predict_in_options(settings: Settings, fake_client) -> None:
    fake_client.chat.return_value = _make_response("ok")
    provider = OllamaProvider(settings, client=fake_client)

    provider.generate_text("prompt")

    call_kwargs = fake_client.chat.call_args.kwargs
    assert call_kwargs["options"] == {"num_predict": settings.ollama_max_tokens}


def test_prompt_without_system_prompt_sends_only_a_user_message(
    settings: Settings, fake_client
) -> None:
    fake_client.chat.return_value = _make_response("ok")
    provider = OllamaProvider(settings, client=fake_client)

    provider.generate_text("Write a cover letter")

    call_kwargs = fake_client.chat.call_args.kwargs
    assert call_kwargs["messages"] == [{"role": "user", "content": "Write a cover letter"}]


def test_system_prompt_is_prepended_as_a_system_role_message(
    settings: Settings, fake_client
) -> None:
    # The key structural difference from ClaudeProvider: Ollama has no
    # separate `system` parameter, so system_prompt must become a
    # {"role": "system", ...} message prepended to the same messages
    # list -- this is the actual proof that AIProvider's interface
    # generalizes to a provider representing this differently.
    fake_client.chat.return_value = _make_response("ok")
    provider = OllamaProvider(settings, client=fake_client)

    provider.generate_text("Write a cover letter", system_prompt="Be concise")

    call_kwargs = fake_client.chat.call_args.kwargs
    assert call_kwargs["messages"] == [
        {"role": "system", "content": "Be concise"},
        {"role": "user", "content": "Write a cover letter"},
    ]


def test_raises_a_clear_error_when_response_content_is_none(
    settings: Settings, fake_client
) -> None:
    fake_client.chat.return_value = _make_response(None)
    provider = OllamaProvider(settings, client=fake_client)

    with pytest.raises(AIProviderError, match="no text content"):
        provider.generate_text("prompt")


def test_constructor_builds_a_real_client_when_none_is_injected(settings: Settings) -> None:
    provider = OllamaProvider(settings)

    assert isinstance(provider._client, ollama.Client)


def test_request_error_is_translated_to_ai_provider_error(settings: Settings, fake_client) -> None:
    fake_client.chat.side_effect = ollama.RequestError("bad request")
    provider = OllamaProvider(settings, client=fake_client)

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate_text("prompt")

    assert isinstance(exc_info.value.__cause__, ollama.RequestError)


def test_response_error_is_translated_to_ai_provider_error(settings: Settings, fake_client) -> None:
    # RequestError and ResponseError share no common base beyond bare
    # Exception (verified against the installed SDK) -- both are tested
    # explicitly here, not just one, since a single shared except clause
    # (as ClaudeProvider uses) would not have worked for Ollama.
    fake_client.chat.side_effect = ollama.ResponseError("server error")
    provider = OllamaProvider(settings, client=fake_client)

    with pytest.raises(AIProviderError) as exc_info:
        provider.generate_text("prompt")

    assert isinstance(exc_info.value.__cause__, ollama.ResponseError)
