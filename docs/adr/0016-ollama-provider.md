# ADR-0016: `OllamaProvider` — Proving `AIProvider` Generalizes

## Status

Accepted — 2026-07-09

## Context

Milestone 15 builds the second concrete `AIProvider` implementation.
Its purpose is different from Milestone 14's: with only one
implementation (`ClaudeProvider`), there was no way to confirm
`AIProvider`'s interface (ADR-0014) was genuinely provider-agnostic
rather than accidentally Claude-shaped. Before designing anything, the
actual `ollama` Python package (`0.6.2`) was installed and inspected
directly — the same discipline as Milestone 14 — and it surfaced real,
structural differences from Anthropic's API worth confirming the
interface survives.

## Decisions

### 1. Version pin: `ollama==0.6.2`, not a range

Same reasoning as `anthropic==1.0.0` and `playwright==1.56.0`: pin
tightly from the start, verified with a clean-venv install, rather than
risk a repeat of the regression a wide range already caused once
(ADR-0008).

### 2. `system_prompt` is translated into a `{"role": "system", ...}` message, not a separate API parameter — the real generalization test

Inspecting `ollama.Client.chat()`'s actual signature confirmed it has no
`system` parameter at all, unlike Anthropic's API. Ollama represents a
system prompt as a message with `role="system"`, prepended to the same
`messages` list the user prompt goes in. `OllamaProvider.generate_text()`
builds this list internally — `AIProvider`'s external contract
(`generate_text(prompt, *, system_prompt=None) -> str`) is completely
unaffected and identical to `ClaudeProvider`'s. This is the concrete
proof the interface (decision #2/#3 of ADR-0014: one generic primitive,
system prompt included since both planned implementations support it)
was designed at the right level of abstraction — it accommodates two
providers representing the same concept in structurally different ways
without any change to the interface itself.

### 3. `max_tokens` maps to `options.num_predict`, not a top-level parameter

Also confirmed by inspecting the real signature: `chat()` has no
`max_tokens` argument; the equivalent, `num_predict`, lives nested inside
an `options` mapping. `Settings.ollama_max_tokens` exists as its own
field (mirroring `anthropic_max_tokens`), mapped to this shape inside
`OllamaProvider` — the `Settings`-level configuration story stays
consistent across both providers even though the underlying API shapes
differ.

### 4. No API key -- matches `Settings.ollama_host`'s existing shape

Ollama runs locally (or against a configured host) with no
authentication by default. This required no new secret-handling code;
`Settings.ollama_host` already existed with no accompanying API key
field, and that was already correct.

### 5. `ollama_model` defaults to `"llama3.1"` — verified differently than `anthropic_model`, and documented as such

Unlike Claude, Ollama has no hosted API with an official, checkable
model list — models are local, and a user must `ollama pull <model>`
before any model works at all. There is no equivalent of "check
Anthropic's official docs" to perform here. Instead, `"llama3.1"` was
chosen by cross-referencing multiple independent sources on Ollama's
library popularity (checked 2026-08-25), including one that cites
Ollama's own pull-count data directly from `ollama.com/library` (Llama
3.1: 118.6M total pulls, the most of any model family at the time) — the
consistently-recommended "start here" default across sources, not an
official canonical choice the way `claude-sonnet-5` is.
`Settings.ollama_model`'s docstring states this distinction explicitly,
so a future maintainer doesn't mistake this default for having the same
verification basis as `anthropic_model`.

### 6. `response.message.content: str | None` is checked explicitly, not assumed present

Inspecting `ollama._types.Message` confirmed `content` is optional —
simpler than Claude's list-of-typed-content-blocks response shape, but
still not guaranteed to be text. `generate_text()` raises a clear
`ValueError` (naming the configured model) if `content` is `None`,
satisfying its own `-> str` contract the same way `ClaudeProvider` does
for its own different failure shape (no `TextBlock` present).

### 7. Constructor accepts an optional `client`, defaulting to a real `ollama.Client`

Identical pattern to `ClaudeProvider` (ADR-0015 decision #2), for the
same reason: no test in this project's suite should require a real,
running Ollama server, matching the "AI providers are mocked in tests"
principle from the pre-Phase-3 review.

### 8. No exception translation yet

`ollama.RequestError`/`ollama.ResponseError` propagate untranslated,
mirroring the same precedent now established three times
(`PlaywrightBrowserEngine` Milestone 8→10, `ClaudeProvider` Milestone
14→16, and now `OllamaProvider` here) — deferred to Milestone 16.

## Alternatives Considered

- **Adding a `system` field to `AIProvider` conditionally supported by
  implementations.** Rejected — the whole point of decision #2 is that
  the interface needed no change at all; a provider translates the
  concept into whatever shape its own API needs internally.
- **A wide version range for `ollama`.** Rejected; see decision #1.
- **Treating `ollama_model`'s default with the same "verified against
  official docs" framing as `anthropic_model`.** Rejected; see decision
  #5 — the verification basis is genuinely different (community/library
  popularity vs. an official hosted-API model list), and documenting
  that difference honestly matters more than making the two defaults
  sound equivalently authoritative.

## Consequences

**Positive:**
- `AIProvider` is now confirmed, not just designed, to generalize across
  two structurally different provider APIs — the system-prompt
  translation is the concrete evidence, not an assumption.
- Every test in `test_ollama_provider.py` runs with zero network access
  and no dependency on a running Ollama server.
- A future third provider (if one is ever added, per the "yes, this is
  exactly what the interface is for" answer already given) has two
  working, structurally-different examples to follow, not just one.

**Trade-offs:**
- `ollama_model`'s default carries a real, ongoing maintenance
  difference from `anthropic_model`: since Ollama has no official
  model-list API to check periodically, keeping this default current
  relies on community-sourced popularity data, which is a weaker
  verification basis than `anthropic_model`'s official documentation
  check — acceptable, but explicitly not equivalent, and documented as such.

## References

- ADR-0014 — `AIProvider`'s interface design, confirmed here to actually
  generalize as intended.
- ADR-0015 — `ClaudeProvider`'s constructor-injection testability
  pattern, reused identically here.
- ADR-0008 — the version-pinning lesson applied a third time.
