# ADR-0014: `AIProvider` Interface

## Status

Accepted — 2026-07-09

## Context

Milestone 13 opens Phase 3 with just the abstract contract Milestones
14/15 (`ClaudeProvider`/`OllamaProvider`) will implement and Milestones
16-18 (AI-generated cover letters, AI-generated answers, resume
recommendation) will consume. This is the same interface-then-
implementation-then-consumer sequencing Phase 2 already used
successfully (`BrowserAutomationEngine` in Milestone 8, implemented and
consumed across Milestones 9-12) — not a new pattern, a continuation of
one already proven in this project.

## Decisions

### 1. `Protocol`, not `ABC`

Consistent with every interface in this project (ADR-0005/0008/0009/0010).

### 2. One generic primitive, `generate_text()`, not one method per feature

`AIProvider` does not define `generate_cover_letter()`,
`generate_answer()`, or `recommend_resume()`. This is the exact lesson
ADR-0009 already established for `BrowserAutomationEngine`: the
interface itself stays feature-agnostic; domain-specific logic (building
a cover-letter prompt, an answer prompt, a resume-ranking prompt, and
interpreting the returned text) belongs in the use cases that will
eventually consume this interface (Milestones 16-18), not baked into the
interface. Both Claude and Ollama are, underneath, "text in, text out"
chat/completion APIs — `generate_text(prompt, *, system_prompt=None) -> str`
reflects exactly that, nothing more.

### 3. `system_prompt` is included now, as an optional parameter

Both Claude (a dedicated `system` parameter, distinct from the user
message) and Ollama (a `system`-role message) support this distinction
natively. Since both of this interface's two already-planned concrete
implementations support it, it's included now rather than deferred --
unlike a feature-specific method (decision #2), this isn't inventing
speculative surface area; it's reflecting a capability both real,
already-scheduled implementations actually have.

### 4. Model selection is a constructor-level concern, not a `generate_text()` parameter

Matches how `PlaywrightBrowserEngine` doesn't take "which browser" as a
per-call argument. `ClaudeProvider`/`OllamaProvider` (Milestone 14/15)
will each be configured with a default model via `Settings` at
construction time.

### 5. No exception translation yet

Unlike `BrowserAutomationError` for `BrowserAutomationEngine`, no
`AIProviderError` is introduced in this milestone. There is no
use-case-level consumer yet to design a translation against (Milestone
16 will be) -- the same "don't build an abstraction without a concrete
consumer" discipline already applied to `BrowserAutomationEngine`'s
exception translation (ADR-0008/0009/0010) and to DTOs (ADR-0006).

### 6. No fake test double added yet

`FakeBrowserEngine` wasn't created until `AutofillApplicationUseCase`
(Milestone 10) actually needed one, two milestones after
`BrowserAutomationEngine` itself was defined. Same reasoning here: no
consumer exists yet, so no fake yet. This milestone's only test is a
throwaway, non-reusable stub class proving the `Protocol` itself is
well-formed and satisfiable -- the same verification method used for
every other interface in this project, just with no real implementation
to check yet (that arrives in Milestone 14/15).

## Alternatives Considered

- **Per-feature methods** (`generate_cover_letter()`, etc.). Rejected;
  see decision #2.
- **A `model` parameter on `generate_text()`.** Rejected; see decision #4.
- **Deferring `system_prompt`** until a consumer needs it, matching how
  `BrowserAutomationEngine`'s exception translation was deferred.
  Considered, and it's a reasonable alternative — but rejected because
  the two situations differ: exception translation requires knowing
  *how a use case wants to handle failure*, which genuinely isn't known
  yet; `system_prompt` is a capability both planned implementations
  already have, not something requiring a consumer's perspective to
  design correctly.
- **Building Milestone 13 and 14 together** (interface + first concrete
  implementation in one milestone). Rejected in favor of keeping the
  roadmap's own stated milestone boundaries, matching how
  `BrowserAutomationEngine`'s interface and `PlaywrightBrowserEngine`'s
  implementation were also kept as one milestone (8) rather than split
  further — the roadmap already treats "interface" as appropriately
  small on its own here, unlike AIProvider's implementations which get
  their own milestones (14/15) since there are two of them.

## Consequences

**Positive:**
- Milestone 16's `GenerateCoverLetterUseCase` (and 17/18's use cases)
  can depend on `AIProvider` as a pure interface, with `ClaudeProvider`/
  `OllamaProvider` swappable underneath with zero changes to the use case.
- Consistent with every architectural pattern already established in
  this project — no new abstraction style introduced.

**Trade-offs:**
- This milestone has almost no testable behavior of its own (a `Protocol`
  with no implementation has nothing to run) -- acceptable and expected,
  not a gap; real verification happens once Milestone 14/15 build
  concrete implementations that must satisfy it.

## References

- ADR-0008/0009 — `BrowserAutomationEngine`'s interface design and the
  exception-translation deferral this ADR mirrors.
- ADR-0006 — the "don't build an abstraction without a concrete
  consumer" discipline applied here to exception translation and the
  fake test double.
