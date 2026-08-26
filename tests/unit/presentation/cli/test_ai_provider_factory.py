"""Tests for the AI provider factory: constructs a concrete AIProvider by
name, so CLI commands can let the user choose --provider claude|ollama
instead of hardcoding ClaudeProvider (a real gap found and fixed before
Phase 4 began -- see CHANGELOG.md)."""

from __future__ import annotations

import pytest

from jaap.infrastructure.ai.claude_provider import ClaudeProvider
from jaap.infrastructure.ai.ollama_provider import OllamaProvider
from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.ai_provider_factory import build_ai_provider


def test_claude_builds_a_claude_provider() -> None:
    settings = Settings(_env_file=None)

    provider = build_ai_provider("claude", settings)

    assert isinstance(provider, ClaudeProvider)


def test_ollama_builds_an_ollama_provider() -> None:
    settings = Settings(_env_file=None)

    provider = build_ai_provider("ollama", settings)

    assert isinstance(provider, OllamaProvider)


def test_unknown_provider_raises_value_error() -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValueError, match="Unknown AI provider"):
        build_ai_provider("gpt5", settings)
