"""Constructs a concrete AIProvider by name, for CLI commands that let
the user choose which provider to use via `--provider`.

Extracted here specifically to avoid duplicating this small piece of
composition-root-style logic across three separate command modules
(cover_letter_commands.py, answer_commands.py, resume_commands.py) --
each previously hardcoded `ClaudeProvider(context.settings)` directly,
with no way to choose OllamaProvider instead, despite Milestone 15
proving the interface genuinely supports it. Not a new architectural
layer: this is the same kind of composition-root code `main.py`/
`_handle_review` already contains, just shared across the three places
that now need it instead of copy-pasted.
"""

from __future__ import annotations

from jaap.application.interfaces.ai_provider import AIProvider
from jaap.infrastructure.ai.claude_provider import ClaudeProvider
from jaap.infrastructure.ai.ollama_provider import OllamaProvider
from jaap.infrastructure.config.settings import Settings

_PROVIDERS = {
    "claude": ClaudeProvider,
    "ollama": OllamaProvider,
}


def build_ai_provider(provider_name: str, settings: Settings) -> AIProvider:
    """`provider_name` is validated by argparse's own `choices=` before
    this is ever called (see each command's `--provider` argument), so
    the ValueError here is a defensive backstop, not the primary
    validation path.
    """
    try:
        provider_class = _PROVIDERS[provider_name]
    except KeyError:
        raise ValueError(
            f"Unknown AI provider {provider_name!r}; expected one of {sorted(_PROVIDERS)}"
        ) from None
    return provider_class(settings)
