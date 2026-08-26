"""Ollama-backed AIProvider implementation.

The second concrete AIProvider implementation (see ADR-0016) -- its real
purpose is proving the interface actually generalizes to a structurally
different provider, not just a second copy of ClaudeProvider's shape.
Ollama's chat API differs from Claude's in several concrete ways
(verified by inspecting the actually-installed `ollama` package, not
assumed):

  - No separate `system` parameter. Ollama represents a system prompt as
    a `{"role": "system", "content": ...}` message prepended to the same
    `messages` list the user prompt goes in -- there is no top-level
    `system` argument the way Anthropic's API has one. generate_text()
    translates AIProvider's `system_prompt` parameter into this shape
    internally; the external contract (`generate_text(prompt, *,
    system_prompt=None) -> str`) stays identical to ClaudeProvider's.
  - No `max_tokens` parameter at all. The equivalent is `num_predict`,
    nested inside an `options` mapping.
  - No API key -- Ollama runs locally (or against a configured host) with
    no authentication by default, matching `Settings.ollama_host` already
    having no accompanying API key field.
  - A simpler response shape: `response.message.content: str | None` (not
    a list of typed content blocks the way Claude's response is) -- but
    still `| None`, so generate_text() must still handle a missing-text
    case explicitly to satisfy its own `-> str` contract.

Requires the `ollama` package (pinned tightly -- see requirements.txt's
note, following ADR-0008/0015's lesson).
"""

from __future__ import annotations

import ollama

from jaap.domain.exceptions import AIProviderError
from jaap.infrastructure.config.settings import Settings


class OllamaProvider:
    """Satisfies application.interfaces.ai_provider.AIProvider.

    Constructor accepts an optional `client`, defaulting to a real
    `ollama.Client` if not given -- the same testability pattern as
    ClaudeProvider (see ADR-0015's decision #2): dependency injection,
    not global monkeypatching, keeps every test able to substitute a fake
    matching Ollama's real response shape, with zero network access.

    `model` and `max_tokens` come from Settings, not generate_text()
    parameters -- consistent with ADR-0014's decision that model
    selection is a constructor/config-level concern.

    Exception translation (added Milestone 16, resolving the deferral
    stated in ADR-0014/0015/0016): unlike Anthropic's SDK,
    `ollama.RequestError` and `ollama.ResponseError` share NO common base
    beyond bare `Exception` (verified directly against the installed
    SDK) -- both are caught explicitly as a tuple, not a single shared
    base class the way ClaudeProvider's translation works. Re-raised as
    `AIProviderError` (domain/exceptions.py) via exception chaining,
    mirroring the same precedent set by PlaywrightBrowserEngine/
    BrowserAutomationError (Milestone 8->10) and ClaudeProvider here.
    """

    def __init__(self, settings: Settings, client: ollama.Client | None = None) -> None:
        self._model = settings.ollama_model
        self._max_tokens = settings.ollama_max_tokens
        self._client = client or ollama.Client(host=settings.ollama_host)

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat(
                model=self._model,
                messages=messages,
                options={"num_predict": self._max_tokens},
            )
        except (ollama.RequestError, ollama.ResponseError) as exc:
            raise AIProviderError(f"Ollama request failed: {exc}") from exc

        content = response.message.content
        if content is None:
            raise AIProviderError(
                f"Ollama's response contained no text content (model: {self._model!r})"
            )
        return content
