# ADR-0015: `ClaudeProvider` — First Concrete `AIProvider` Implementation

## Status

Accepted — 2026-07-09

## Context

Milestone 14 builds `ClaudeProvider`, the first concrete implementation
of `AIProvider` (ADR-0014). Before designing anything, the actual
`anthropic` Python SDK was installed and inspected directly (constructor
signature, `messages.create()`'s real parameters, the `Message`/`TextBlock`
response shape, and the SDK's exception types) rather than relying on
possibly-stale training knowledge — several real, non-obvious findings
came directly from this inspection and shaped the implementation.

## Decisions

### 1. Version pin: `anthropic==1.0.0`, not a range

Following ADR-0008's lesson directly: a wide version range
(`playwright>=1.45,<2.0`) already caused a real, reproduced regression
in this project once. Pinned tightly from the start this time rather
than waiting to discover a similar problem later; verified with a
clean-venv install.

### 2. Constructor accepts an optional `client`, defaulting to a real one

`ClaudeProvider.__init__(self, settings: Settings, client: anthropic.Anthropic | None = None)`.
Deliberately different from `PlaywrightBrowserEngine`'s pattern (which
constructs its own browser internally, no injection point) — there,
real behavior under test was exactly what was wanted, verified against
actual Chromium. Here, the opposite holds: there is no API key or
network access this project's test suite should assume, and even with a
real key, hitting a real, billed API automatically would be wrong (cost,
non-determinism, CI credential requirements). Optional client injection,
defaulting to real, is the standard way to keep normal use simple
(`ClaudeProvider(settings)`) while making every test trivially able to
substitute a hand-built fake matching the SDK's real response shape.

### 3. `model` and `max_tokens` are new `Settings` fields, not `generate_text()` parameters

Consistent with ADR-0014's decision that model selection is a
constructor/config-level concern. `max_tokens` is genuinely required by
Anthropic's API (confirmed by inspecting `messages.create()`'s real
signature — unlike some other providers' APIs, it has no default), so it
needed a decision regardless; treating it the same way as `model` (a
`Settings` field, not a call-site parameter) keeps both configuration
knobs in one consistent place.

`anthropic_model` defaults to `"claude-sonnet-5"`. This was initially
chosen by cross-referencing the installed SDK's own `Model` type literal
against this assistant's system prompt — a reasonable first pass, but
not yet verification against Anthropic's own published documentation.
That verification was performed afterward (2026-08-25) directly against
`platform.claude.com/docs`: the "Model IDs and versioning" page confirms
that starting with the 4.6 generation, a bare, dateless ID like
`claude-sonnet-5` is the canonical, pinned model identifier (not a
rolling alias) — and Anthropic's own AWS Bedrock documentation shows
`model="claude-sonnet-5"` directly in sample code. Both the SDK's type
stub and the official documentation agree; `anthropic_max_tokens`
defaults to `1024`, reasonable for cover-letter/answer-length text
(Milestone 16/17's actual anticipated use).

**A concrete finding worth recording:** one third-party blog covering
this same model confidently reported its API identifier as
`claude-sonnet-4-5` — which is wrong. This is a real example, not a
hypothetical caution: aggregator/blog content about model identifiers
can be stale or simply incorrect, even when confidently written.
Anthropic's own documentation and the installed SDK's type stubs are
the two sources trusted here; third-party summaries are not.

**Upgrade procedure**, documented so this default is revalidated
deliberately, not silently left stale: before changing
`anthropic_model`, check both
[Model IDs and versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)
and
[Model deprecations](https://platform.claude.com/docs/en/about-claude/models/model-deprecations)
on Anthropic's own docs site, and confirm the new identifier appears in
the currently installed `anthropic` package's
`anthropic.types.model.Model` Literal type. Re-run
`tests/unit/infrastructure/ai/test_claude_provider.py` after changing --
those tests assert the configured model string is passed through
correctly, not any specific value, so they remain valid regardless of
which model is configured. This same procedure is also documented
directly in `Settings.anthropic_model`'s own docstring, so it's visible
at the point of use, not only here.

### 4. `system_prompt` uses `anthropic.omit`, not `anthropic.NOT_GIVEN` — a real bug caught by mypy, not a style choice

The SDK exposes two different "not given" sentinel families:
`NotGiven`/`NOT_GIVEN` and `Omit`/`omit`. An initial implementation used
`NOT_GIVEN` for the optional `system` parameter; mypy correctly rejected
it (`incompatible type "str | NotGiven"; expected "str | Iterable[TextBlockParam] | Omit"`).
Verified directly against the installed SDK's type stubs and fixed to
use `anthropic.omit` specifically. This is recorded here because it's a
real, non-obvious API detail this project got wrong on the first attempt
and mypy caught immediately — exactly the kind of thing worth writing
down rather than treating as a one-off fix.

### 5. `response.content` is filtered for `TextBlock` instances, not indexed at `[0]`

Also caught by mypy, not assumed correct from the start: `Message.content`
is a list of a union type covering many possible content block kinds
(`TextBlock`, `ThinkingBlock`, `ToolUseBlock`, and others) — confirmed by
inspecting the SDK's actual type definitions. A simple text-only prompt
(no tools, no extended thinking) returns a single `TextBlock` in
practice, but `generate_text()` must satisfy its `-> str` contract
correctly regardless, so the implementation filters `response.content`
for `TextBlock` instances specifically, concatenates their text (in case
of multiple), and raises a clear `ValueError` (naming the actual block
types received) if no text block is present at all -- rather than
risking an `AttributeError` on a non-text block, or silently returning
something wrong.

### 6. No exception translation yet

Anthropic's own exceptions (`APIError`, `RateLimitError`,
`AuthenticationError`, `APIConnectionError`, and others — enumerated by
inspecting the installed SDK) propagate untranslated from
`generate_text()`. This directly mirrors a precedent already set, not
just repeats ADR-0014's stated plan: `BrowserAutomationError` was not
added when `PlaywrightBrowserEngine` was first built (Milestone 8, a
concrete implementation calling a concrete SDK, exactly analogous to
`ClaudeProvider` here) -- it waited until Milestone 10, the first real
*use-case* consumer, per ADR-0008/0010. The same discipline applies:
deferred to Milestone 16.

## Alternatives Considered

- **Constructing the `anthropic.Anthropic` client unconditionally inside
  `__init__`, with tests monkeypatching the class globally.** Rejected
  in favor of constructor injection; see decision #2 — dependency
  injection over global monkeypatching is more consistent with this
  project's established testing style (fakes injected via constructors
  throughout, e.g. `tests/unit/application/use_cases/fakes.py`).
- **A wide version range for `anthropic`**, matching the original
  commented-out placeholder in `requirements.txt`. Rejected; see
  decision #1.
- **Indexing `response.content[0].text` directly.** This was the
  original implementation; rejected once mypy's union-type error made
  clear it wasn't actually safe for every possible response shape. See
  decision #5.

## Consequences

**Positive:**
- Every test in `test_claude_provider.py` runs with zero network access
  and zero API cost, using a fake client built to match the SDK's real,
  verified response shape -- not a shape guessed from documentation or
  memory.
- Two real bugs (the wrong sentinel type, the unsafe content indexing)
  were caught by mypy during development, before either could reach a
  real API call and fail confusingly (or silently produce wrong output)
  in actual use.
- `infrastructure/ai/` now has real content for the first time, and the
  architecture boundary test (added in the pre-Phase-3 cleanup) was
  confirmed to still pass -- the first genuinely meaningful run of that
  test, not just a trivial pass against an empty directory.

**Trade-offs:**
- `anthropic_model`'s default will need re-verification against the
  installed SDK if it's ever bumped -- documented explicitly in
  `settings.py`'s docstring so this isn't forgotten, but it is a
  manual step, not automated.

## References

- ADR-0008 — the version-pinning lesson applied here, and the original
  precedent for deferring exception translation on a concrete
  implementation until a real use-case consumer exists.
- ADR-0014 — `AIProvider`'s interface design, which this implementation
  satisfies without needing any change to the interface itself.
- ADR-0010 — the earlier, exact precedent (`BrowserAutomationError`
  deferred from Milestone 8 to Milestone 10) this ADR's decision #6
  directly mirrors.
