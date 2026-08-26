"""Claude-backed AIProvider implementation.

Requires the `anthropic` package (pinned tightly -- see requirements.txt's
note, following ADR-0008's lesson that a wide version range already bit
this project once for a different dependency).

Constructor accepts an optional `client` parameter, defaulting to a real
`anthropic.Anthropic` instance if not given. This is a deliberately
different pattern from PlaywrightBrowserEngine (which constructs its own
browser internally, no injection): there, real behavior under test was
exactly what was wanted (verified against actual Chromium). Here, the
opposite is true -- there is no API key or network access assumption
this project should rely on in its test suite, and even with a real key,
hitting a real, billed API in automated tests would be wrong (cost,
determinism, CI credentials). Optional client injection, defaulting to
real, is the standard way to make this both simple to use for real and
trivial to substitute a fake for in tests.
"""

from __future__ import annotations

import anthropic
from anthropic.types import TextBlock

from jaap.infrastructure.config.settings import Settings


class ClaudeProvider:
    """Satisfies application.interfaces.ai_provider.AIProvider.

    `model` and `max_tokens` come from Settings (see settings.py), not
    generate_text() parameters -- consistent with ADR-0014's decision
    that model selection is a constructor/config-level concern, not a
    per-call one.

    No exception translation yet: Anthropic's own exceptions (`APIError`,
    `RateLimitError`, `AuthenticationError`, etc.) propagate untranslated
    from generate_text(). This mirrors the exact precedent set by
    PlaywrightBrowserEngine, which also had no exception translation when
    it was first built (Milestone 8) -- BrowserAutomationError wasn't
    added until Milestone 10, the first real use-case consumer. The same
    discipline applies here: deferred to Milestone 16 (see ADR-0014/0015).
    """
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None) -> None:
        self._model = settings.anthropic_model
        self._max_tokens = settings.anthropic_max_tokens
        self._client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        # anthropic.omit, not NOT_GIVEN: verified against the installed
        # SDK that `system` specifically expects the `Omit` sentinel, a
        # distinct type from the older `NotGiven`/`NOT_GIVEN` -- an
        # earlier version of this code used the wrong one and mypy caught
        # it (a real, useful type error, not a false positive).
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
            system=system_prompt if system_prompt is not None else anthropic.omit,
        )

        # response.content is a union of many possible block types
        # (TextBlock, ThinkingBlock, ToolUseBlock, ...) -- verified
        # against the installed SDK, not assumed to always be plain text.
        # A simple text-only prompt (no tools, no extended thinking)
        # returns a single TextBlock in practice, but filtering explicitly
        # rather than blindly indexing content[0] is what actually
        # satisfies the AIProvider contract (always return str) correctly.
        text_blocks = [block.text for block in response.content if isinstance(block, TextBlock)]
        if not text_blocks:
            raise ValueError(
                "Claude's response contained no text content "
                f"(got block types: {[type(b).__name__ for b in response.content]})"
            )
        return "".join(text_blocks)
