"""AIProvider interface (port).

Defined as a Protocol, not ABC -- same reasoning as every other interface
in this project (ADR-0005/0008/0009/0010): structural typing means a
test double satisfies this interface just by matching method shapes, no
inheritance required; mypy verifies conformance statically.

Exposes exactly one generic primitive, `generate_text()`, not one method
per feature (e.g. not `generate_cover_letter()`/`generate_answer()`/
`recommend_resume()`). This is the same lesson ADR-0009 already
established for `BrowserAutomationEngine`: keep the interface itself
feature-agnostic; domain-specific logic (building a cover-letter prompt,
an answer prompt, a resume-ranking prompt, and interpreting the result)
belongs in the use cases that will eventually consume this interface
(Milestones 16-18), not baked into the interface itself. Both Claude and
Ollama are fundamentally "text in, text out" chat/completion APIs, which
is exactly what this interface reflects.

Model selection (e.g. "claude-sonnet" vs "claude-opus", or which Ollama
model) is deliberately NOT a parameter here -- it's a constructor-level
concern for each concrete provider (Milestone 14/15), configured via
Settings, matching how PlaywrightBrowserEngine doesn't take "which
browser" as a per-call argument.

No dedicated exception translation yet, unlike BrowserAutomationError
(domain/exceptions.py) for BrowserAutomationEngine: there is no
use-case-level consumer of this interface yet to design a translation
against (Milestone 16 will be). Revisit then, following the same
"don't build an abstraction without a concrete consumer" discipline
already established for BrowserAutomationEngine's own exception
translation (ADR-0008/0009/0010) and for DTOs (ADR-0006).

This milestone (13) is intentionally minimal: an interface with zero
concrete implementations (Milestone 14/15) and zero consumers
(Milestone 16-18) has almost no testable behavior of its own -- its
correctness will be verified concretely once ClaudeProvider/OllamaProvider
exist and must satisfy it (mypy Protocol-conformance checks, matching
every other interface in this project). No fake test double is added
here either, for the same reason FakeBrowserEngine wasn't added until
Milestone 10 actually needed one, two milestones after
BrowserAutomationEngine itself was defined.
"""

from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        """Generate text from `prompt`, optionally guided by `system_prompt`.

        `system_prompt` is a separate, optional instruction distinct from
        `prompt` itself -- both Claude (a dedicated `system` parameter)
        and Ollama (a `system`-role message) support this distinction
        natively, so it's included now rather than added later once a
        consumer needs it.
        """
        ...
