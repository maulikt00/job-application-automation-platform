"""Tests for AIProvider.

Deliberately minimal: this milestone (13) is just the interface, with no
concrete implementations (Milestone 14/15) and no consumers (Milestone
16-18) yet. There is almost nothing to test beyond "is this Protocol
well-formed" -- its real correctness will be verified once
ClaudeProvider/OllamaProvider exist and must structurally satisfy it,
the same way every other interface in this project has been verified.
"""

from __future__ import annotations

from jaap.application.interfaces.ai_provider import AIProvider


class _StubProvider:
    """Throwaway, not a reusable fake for other tests to import -- exists
    only to prove AIProvider is a well-formed, satisfiable Protocol. A
    real fake (for Milestone 16+'s use case tests) gets added once there's
    an actual consumer to test against, matching how FakeBrowserEngine
    wasn't added until Milestone 10 needed one.
    """

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return f"stub response to: {prompt!r} (system={system_prompt!r})"


def test_a_conforming_class_satisfies_the_protocol() -> None:
    provider: AIProvider = _StubProvider()

    assert provider.generate_text("hello") == "stub response to: 'hello' (system=None)"


def test_system_prompt_is_optional() -> None:
    provider: AIProvider = _StubProvider()

    result = provider.generate_text("hello", system_prompt="be concise")

    assert "system='be concise'" in result
