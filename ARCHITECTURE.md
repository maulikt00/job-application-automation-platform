# Architecture

This document describes JAAP's software architecture **as it actually
exists today** (through Milestone 18 / the pre-Phase-4 cleanup pass),
distinguishing built functionality from planned future work. For the
*reasoning* behind these choices, see [docs/adr/](docs/adr/).

## Guiding Principle: The Dependency Rule

> Source code dependencies always point inward. Inner layers know nothing
> about outer layers.

```
┌──────────────────────────────────────────────────────────┐
│  Presentation (CLI today; FastAPI/NiceGUI planned Phase 5) │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Infrastructure (SQLite + Playwright + Claude/Ollama    │ │
│  │  today; website connectors planned Phase 4)             │ │
│  │  ┌──────────────────────────────────────────────────┐ │ │
│  │  │  Application (Use Cases + Interfaces/Ports)       │ │ │
│  │  │  ┌──────────────────────────────────────────────┐│ │ │
│  │  │  │  Domain (Profile, Resume, JobPosting, ...)    ││ │ │
│  │  │  └──────────────────────────────────────────────┘│ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

Arrows of *dependency* point inward (outer rings depend on inner rings).
Arrows of *runtime data flow* can go either direction, which is why the
worked examples below distinguish them.

## Layers

### 1. Domain (`src/jaap/domain/`)

Pure business objects and rules, with zero dependency on SQLAlchemy,
Playwright, AI SDKs, or how they're persisted or displayed.

- **`models/`** — the six aggregate roots: `Profile`, `Resume`,
  `CoverLetterTemplate`, `Answer`, `JobPosting`, `Application`. All
  inherit from `Entity` (identity-based equality/hashing, see
  `entity.py`/ADR-0003). Value objects with no independent identity:
  `ApplicationStatus` (enum), `ApplicationStatusEvent`,
  `SubmittedContentSnapshot`, `SubmittedAnswer` (the last two added
  Milestone 13/ADR-0013 — durable, immutable evidence of what was
  actually submitted with an `Application`).
- **`exceptions.py`** — `DomainError` (base), `InvalidStatusTransitionError`,
  `ReferentialIntegrityError`, `BrowserAutomationError`, `AIProviderError`
  (the last added Milestone 16/ADR-0017). These represent violations of
  an aggregate's own internal consistency or a failed call to an
  external infrastructure dependency, distinct from
  `application/exceptions.py`'s business-rule violations (see ADR-0002's
  domain-invariant/business-rule split).

**Depends on:** nothing else in this project except `utils/` (a plain
function, `utils/slugify.py`, with zero side effects — see "Cross-cutting"
below for why this doesn't violate the dependency rule).

### 2. Application (`src/jaap/application/`)

Three things live here today:

- **`interfaces/`** — abstract contracts (`Protocol`, not `ABC` — see
  ADR-0005): `ProfileRepository`, `ResumeRepository`,
  `CoverLetterTemplateRepository`, `AnswerRepository`,
  `JobPostingRepository`, `ApplicationRepository` (`repositories.py`);
  `BrowserAutomationEngine` (`browser_engine.py`); `FormFieldDetector`
  and its `DetectedField` data type (`form_field_detector.py`);
  `FieldMatcher` and its `MatchedField`/`FieldMatchResult` types
  (`field_matcher.py`); `AIProvider` (`ai_provider.py`, Milestone 13 —
  one generic primitive, `generate_text(prompt, *, system_prompt=None) -> str`,
  deliberately not a method per AI feature; see ADR-0014).
  **Not yet defined:** `WebsiteConnector` — Phase 4's interface, planned
  but not built.
- **`use_cases/`** — one class per user-facing action, each constructor-
  injected with only the interfaces it needs: `CreateProfileUseCase`,
  `AddResumeUseCase`, `SaveCoverLetterTemplateUseCase`,
  `SaveAnswerUseCase`, `StartApplicationUseCase`,
  `AttachResumeToApplicationUseCase`, `SubmitApplicationUseCase`,
  `AutofillApplicationUseCase`, `ReviewApplicationUseCase`,
  `GenerateCoverLetterUseCase`, `GenerateAnswerUseCase`,
  `RecommendResumeUseCase` (the last three are Phase 3's real
  `AIProvider` consumers — Milestones 16/17/18). All three follow the
  same shape: compose repositories + the injected `AIProvider`, build a
  prompt internally (a private module-level function, not a class —
  see ADR-0013/0017/0018), and either return plain generated text
  (`str`, no DTO — cover letters/answers) or a small, genuinely
  multi-part result (`ResumeRecommendation`, since "which resume" +
  "why" are two related pieces of information a caller needs together
  — see ADR-0019). None of the three ever saves anything itself; the
  caller (currently the CLI) decides whether to persist the result,
  matching the human-review discipline established since ADR-0001/0012.
- **`services/`** (added Milestone 10/ADR-0010) — concrete implementations
  of application-layer interfaces that have **no external/infrastructure
  dependency** (pure logic only). Currently just `ExactFieldMatcher`, the
  default conservative `FieldMatcher` implementation. Contrast with
  `infrastructure/`: a `Protocol` implementation belongs here only if it
  depends on nothing external; if it needs a database, a browser, or a
  third-party SDK, it belongs in `infrastructure/` instead, even though
  both are "concrete implementations of an interface" in the abstract.
- **`exceptions.py`** — `UseCaseError` (base) and its subclasses
  (`ProfileNotFoundError`, `ResumeNotFoundError`, `AnswerNotFoundError`,
  `CoverLetterTemplateNotFoundError`, `JobPostingNotFoundError`,
  `ApplicationNotFoundError`, `ApplicationNotReadyForSubmissionError`,
  `NoResumesAvailableError`). Business-rule violations, not domain
  invariants (see ADR-0002/0006).
- **`dto/`** — still an empty scaffold. Deliberately not built yet
  (ADR-0006): no concrete consumer has needed one so far; use cases
  currently accept plain parameters and return domain objects (or a
  small justified result type like `ResumeRecommendation`) directly.

**Depends on:** domain only. Never imports anything from `infrastructure/`
or `presentation/` (enforced by an automated test — see "Architecture
Boundary Tests" below).

### 3. Infrastructure (`src/jaap/infrastructure/`)

Concrete implementations of application-layer interfaces that DO depend
on external systems:

- **`database/`** — `models.py` (SQLAlchemy ORM models for all six
  aggregates plus `ApplicationStatusEventORM`/`ApplicationAnswerORM`
  child tables), `types.py` (`UTCDateTime`, a custom type enforcing
  timezone-aware round-tripping), `base.py` (shared `DeclarativeBase`),
  `session.py` (engine/session-factory construction, SQLite foreign-key
  enforcement), `mappers/` (one module per aggregate translating
  domain ↔ ORM — see ADR-0005), `repositories/` (one
  `SqliteXRepository` per interface in `application/interfaces/repositories.py`).
- **`browser/`** — `playwright_engine.py` (`PlaywrightBrowserEngine`,
  the sole current `BrowserAutomationEngine` implementation: `launch`,
  `navigate`, `evaluate`, `fill`, `check`, `select_option`,
  `upload_file`, `screenshot`, `close` — every operational method
  translates Playwright's own exceptions into `BrowserAutomationError`,
  see ADR-0010) and `form_field_detector.py` (`PlaywrightFormFieldDetector`,
  the sole current `FormFieldDetector` implementation, using
  `BrowserAutomationEngine.evaluate()` to run JS against the live
  rendered DOM — never a static HTML parser, see ADR-0009).
- **`ai/`** (populated Milestones 14/15) — `claude_provider.py`
  (`ClaudeProvider`) and `ollama_provider.py` (`OllamaProvider`), the
  two current `AIProvider` implementations. Both translate their own
  SDK's exceptions into `AIProviderError` (resolved Milestone 16 —
  Anthropic's SDK shares one common exception base; Ollama's
  `RequestError`/`ResponseError` share none beyond bare `Exception`,
  so both are caught explicitly — see ADR-0017). Both accept an
  optional `client` constructor parameter (defaulting to a real one),
  so every test injects a hand-built fake matching the real SDK's
  response shape, never a real network call.
- **`config/`** — `settings.py` (a single Pydantic `Settings` object,
  loaded from environment variables/`.env`, injected everywhere rather
  than reached for as a global) and `logging_config.py`
  (`configure_logging()`, console text + rotating JSON file handlers).

**Not yet implemented** (empty `__init__.py` scaffold only):
`infrastructure/connectors/` (planned: `GreenhouseConnector`,
`LeverConnector`, `WorkdayConnector`, and a LinkedIn connector, Phase 4).

**Depends on:** application (to implement its interfaces) and domain.
Never depended upon by application or domain — infrastructure is the
outermost "plug-in" layer. `infrastructure/ai/` and `infrastructure/browser/`
additionally never import each other (see "AI / Browser Separation"
below) — now a genuinely exercised constraint, not a trivial pass
against an empty directory: `infrastructure/ai/` has real content
(two full provider implementations) and the boundary test has been
directly verified to catch a real violation (a deliberately introduced
one was confirmed to fail the test, then removed).

### 4. Presentation (`src/jaap/presentation/`)

Currently CLI-only (`presentation/cli/`):

- **`main.py`** — the composition root and entry point. `build_context()`
  constructs `Settings` → engine → session factory → all six
  repositories, bundling them (plus `Settings` itself) into a `Context`
  dataclass. `build_parser()` wires up `argparse` subcommands.
  `main(argv, settings)` parses arguments, dispatches to the matched
  command handler, and centrally translates any `UseCaseError`/
  `DomainError` into a clean one-line message + exit code 1 — no
  command handler contains its own `try`/`except` (see ADR-0007).
  This is the **only** file in the codebase allowed to import both a
  repository interface and its concrete `SqliteXRepository`
  implementation together.
- **`ai_provider_factory.py`** (added in the pre-Phase-4 cleanup) —
  `build_ai_provider(provider_name, settings) -> AIProvider`, constructing
  `ClaudeProvider` or `OllamaProvider` by name. Extracted specifically
  because three separate command modules (`cover_letter_commands.py`,
  `answer_commands.py`, `resume_commands.py`) each previously hardcoded
  `ClaudeProvider(context.settings)` directly, with no way for a user to
  actually choose `OllamaProvider` instead — despite Milestone 15 proving
  the interface genuinely supports it. All three now expose
  `--provider claude|ollama` (default `claude`), validated by argparse's
  own `choices=` before the handler ever runs.
- **`commands/`** — `profile_commands.py`, `resume_commands.py`,
  `application_commands.py`, `answer_commands.py`,
  `cover_letter_commands.py`. Each handler is a few lines of pure
  orchestration: call a use case, print the result, return an exit
  code. Three commands construct real infrastructure directly inside
  their own handler function (composition-root-style code, not eagerly
  built in `build_context()`, since each is comparatively slow/costly
  and no other command needs one): `application review`
  (`PlaywrightBrowserEngine`, ADR-0012), `cover-letter generate`/
  `answer generate`/`resume recommend` (an `AIProvider`, via
  `ai_provider_factory.build_ai_provider()`).

**Not yet built:** FastAPI, NiceGUI (Phase 5) — planned to be added
*alongside* the CLI, calling the same use cases, not replacing it.

**Depends on:** application (to call use cases) and, at the composition
root only, infrastructure (to construct concrete implementations to inject).

### Cross-cutting: `utils/`

Small, pure, dependency-free helper functions used across layers. If a
"utility" needs file/network/database I/O, it isn't a util — it belongs
in infrastructure. Currently one module: `slugify.py` — extracted from
`Answer.question_key`'s normalization (Milestone 2) so
`ExactFieldMatcher` (Milestone 10) could reuse the identical rule when
comparing a detected field's label against an existing `Answer`,
avoiding two independently-maintained regexes silently drifting apart.

## Composition Root

`presentation/cli/main.py` is currently the only composition root.
`build_context()` constructs every concrete repository implementation
and bundles them (plus `Settings`) into a `Context` dataclass; command
handlers receive `Context` and depend only on its `Protocol`-typed
fields, never on the concrete classes. `Context` grows by one field
each time a new repository or cross-cutting dependency (like `Settings`)
gets a real consumer — it does not eagerly construct anything a given
command doesn't need (e.g. no command pays a browser-launch cost or
constructs an `AIProvider` unless it actually uses one).

## Composition Over Inheritance

- `ExactFieldMatcher` implements `FieldMatcher` independently — no base
  class with shared behavior. It's a `Protocol` specifically because a
  second, AI-assisted implementation remains a real future possibility
  (not yet scheduled on the roadmap); until then, it's the only one.
- `ClaudeProvider` and `OllamaProvider` implement `AIProvider`
  independently, each accepting an optional constructor-injected client
  (defaulting to a real one) rather than sharing a base class — this is
  what makes every test able to substitute a fake matching each SDK's
  real response shape, with zero network access anywhere in the suite.
  Milestone 15 confirmed this genuinely generalizes, not just in theory:
  Ollama's chat API has no `system` parameter at all (unlike Anthropic's),
  representing it instead as a `role="system"` message in the same list
  — `OllamaProvider` translates this internally with zero change to
  `AIProvider`'s external contract.
- `PlaywrightBrowserEngine` and `PlaywrightFormFieldDetector` are
  similarly the sole current implementations of their respective
  `Protocol`s, composed together via constructor injection (the
  detector takes an engine, not the other way around, and never
  imports Playwright directly — see ADR-0009).
- Repositories are injected into use case constructors, not provided
  via a shared base class. `SubmitApplicationUseCase`, for example,
  takes four repositories directly (`ApplicationRepository`,
  `ResumeRepository`, `AnswerRepository`, `CoverLetterTemplateRepository`)
  rather than through any aggregating abstraction — evaluated explicitly
  against introducing one and rejected, since multiple repositories
  injected directly into a use case is already this project's
  established pattern, not a new one (see ADR-0013).

This is what makes the system testable: every unit test hands a use case
a fake implementation of whatever interface it depends on
(`tests/unit/application/use_cases/fakes.py`), so tests never need a
real database, browser, or AI provider *unless the test is specifically
verifying that real implementation* (see "Testing Strategy" below).

## AI / Browser Separation

A structural rule: **AI code and browser automation code must never
import each other.** `infrastructure/ai/` now has real content (two full
provider implementations, Milestones 14/15) and `infrastructure/browser/`
has had real content since Phase 2 — this is a genuinely exercised
constraint, verified by an automated test
(`tests/unit/architecture/test_dependency_boundaries.py`), not a
trivial pass against an empty directory the way it necessarily was
before Phase 3.

Design intent, now concretely realized rather than merely planned:
browser automation collects structured page/form information
(`DetectedField`, form values); `AIProvider` implementations assist with
text generation and decision support (`GenerateCoverLetterUseCase`,
`GenerateAnswerUseCase`, `RecommendResumeUseCase`); a use case
orchestrates the two but neither infrastructure package ever imports
the other directly.

## Architecture Boundary Tests

`tests/unit/architecture/test_dependency_boundaries.py` (added as part
of the pre-Phase-3 cleanup, alongside an earlier version of this
document) statically inspects every module's imports (via Python's
`ast` module — no third-party architecture-linting dependency) and
asserts:

- `domain/` never imports from `application/`, `infrastructure/`, or
  `presentation/`.
- `application/` never imports from `infrastructure/` or `presentation/`.
- `infrastructure/ai/` never imports from `infrastructure/browser/`.
- `infrastructure/browser/` never imports from `infrastructure/ai/`.

This makes the dependency rule and the AI/browser separation
continuously verified facts, not just documented intentions — a
violation fails the test suite immediately, the same day it's
introduced, rather than being caught (or missed) in review. Verified
directly (not just assumed) to actually catch a violation: a real
cross-layer import was deliberately introduced once, confirmed to fail
this test with a clear message, then removed.

## Data Flow — Worked Example 1 (Current, Real): Autofill and Review

**Scenario:** review an autofilled application before manual submission
— `jaap application review`, the actual current CLI flow.

1. **Presentation (CLI)**'s `_handle_review` looks up the `JobPosting`
   via `context.job_posting_repository` to get its URL, then constructs
   a `PlaywrightBrowserEngine(context.settings)` directly (the one
   sanctioned exception to "only depend on interfaces," since this is
   composition-root-style code).
2. It navigates the engine to the posting's URL, then constructs
   `PlaywrightFormFieldDetector(engine)`, `ExactFieldMatcher()`, and
   `AutofillApplicationUseCase` (injected with the engine, detector,
   matcher, and three repositories), and `ReviewApplicationUseCase`
   (composing the autofill use case with the same engine).
3. **`AutofillApplicationUseCase`** loads the `Profile` and its
   `Answer`s (and `Resume`, if a `resume_id` was given) via injected
   repositories — it has no idea these are backed by SQLite. It asks
   the injected `FormFieldDetector` to detect fields on the live page,
   asks the injected `FieldMatcher` to match them, then dispatches each
   matched field to `fill()`/`check()`/`select_option()`/`upload_file()`
   on the injected `BrowserAutomationEngine` — it has no idea that's
   Playwright underneath.
4. **`ReviewApplicationUseCase`** takes the resulting match report and
   calls `engine.screenshot()`, returning both as an `ApplicationReview`.
5. The CLI prints matched fields (with values and source), unmatched
   fields needing manual attention, the screenshot path, and an explicit
   statement that nothing has been submitted — there is no code path
   anywhere in this codebase that could click a submit button (see
   ADR-0012).

Separately, when `SubmitApplicationUseCase.execute()` is called: it
loads the `Application`, resolves its referenced `Resume`/`Answer`s/
`CoverLetterTemplate` (or accepts an ad-hoc `cover_letter_text_override`
for content that was never saved as a template) into a
`SubmittedContentSnapshot`, and passes that snapshot into
`Application.transition_to(SUBMITTED, content_snapshot=...)` — the one
lifecycle transition that requires it (see ADR-0013).

## Data Flow — Worked Example 2 (Current, Real): AI-Generated Content

**Scenario:** draft a cover letter with Claude, then optionally save it
— `jaap cover-letter generate --save-as "..."`.

1. **Presentation (CLI)**'s `_handle_generate` calls
   `ai_provider_factory.build_ai_provider(args.provider, context.settings)`
   — `ClaudeProvider` by default, `OllamaProvider` if `--provider ollama`
   was passed — then constructs `GenerateCoverLetterUseCase`, injected
   with that provider plus `ProfileRepository`/`JobPostingRepository`/
   `CoverLetterTemplateRepository`.
2. **`GenerateCoverLetterUseCase`** loads the `Profile` and `JobPosting`
   (and an existing `CoverLetterTemplate`, if a `template_id` was given)
   via injected repositories, builds a prompt and system prompt
   internally (private module-level functions — no class, no `Protocol`,
   since there's exactly one caller and no anticipated second
   implementation — see ADR-0013/0017), and calls
   `ai_provider.generate_text(prompt, system_prompt=...)` — it has no
   idea whether that's Claude or Ollama underneath, or what SDK-specific
   translation either concrete provider does internally
   (`ClaudeProvider` builds an Anthropic `messages.create()` call;
   `OllamaProvider` builds an Ollama `chat()` call with the system
   prompt folded into the same `messages` list — two structurally
   different translations behind one identical interface call).
3. If either provider's underlying SDK call fails, it's caught and
   re-raised as `AIProviderError` (`domain/exceptions.py`) — the use
   case never needs to catch `anthropic.AnthropicError` or
   `ollama.RequestError`/`ResponseError` specifically.
4. The CLI prints the generated text for review. If `--save-as <name>`
   was given, it's saved as a new `CoverLetterTemplate` in the same
   invocation (text still shown first); otherwise, the CLI prints the
   exact command needed to use it as one-off text via
   `jaap application submit --cover-letter-text-override`. Either way,
   `GenerateCoverLetterUseCase` itself never persists anything — the
   human-review discipline from ADR-0001/0012, applied here to
   AI-generated content specifically.

`GenerateAnswerUseCase` and `RecommendResumeUseCase` follow the same
shape with two real, deliberate differences, both documented as design
decisions rather than oversights: `GenerateAnswerUseCase` takes no
`job_posting_id` at all, so what it generates stays genuinely safe to
save and reuse across different companies (ADR-0018); `RecommendResumeUseCase`
returns a small `ResumeRecommendation` (resume + reasoning) rather than
plain text, since `AIProvider` has no structured-output primitive and a
specific choice had to be parsed reliably out of free text (ADR-0019).

## Testing Strategy

- **All tests currently live under `tests/unit/`.** `tests/integration/`
  exists as an empty scaffold (from Milestone 1's original planned
  layout) but is not actually used — in practice, tests that exercise
  real infrastructure (a real SQLite file, a real headless Chromium
  instance) live alongside fake-based tests under `tests/unit/`, with
  the module docstring stating clearly which kind each file is.
- **Fake-based tests** (most of the suite) use hand-written fakes in
  `tests/unit/application/use_cases/fakes.py` (one per `Protocol`
  interface) — fast, deterministic, no real database, browser, or
  network call. This is the direct payoff of every interface being a
  `Protocol`: a fake satisfies it purely by matching method shapes, no
  inheritance required.
- **Real-infrastructure tests** exercise the actual concrete
  implementation against something real: `tests/unit/infrastructure/database/`
  uses real (in-memory) SQLite; `tests/unit/infrastructure/browser/`
  uses a real headless Chromium instance (verified to be genuinely
  necessary — see ADR-0009's reasoning that a fake `BrowserAutomationEngine`
  would only prove the code calls an API in the expected shape, not that
  the actual JavaScript detection/matching logic is correct).
- **AI providers are mocked in every test, never called for real.**
  `tests/unit/infrastructure/ai/` injects a hand-built fake `client`
  into `ClaudeProvider`/`OllamaProvider`'s constructor, built to match
  each real SDK's actual response shape (`anthropic.types.Message`/
  `TextBlock`; `ollama._types.ChatResponse`/`Message`) — verified
  against the actually-installed SDKs during development, not assumed
  from documentation. No real API call, no network access, no cost
  anywhere in the test suite (cost, determinism, and CI credential
  concerns, exactly as originally anticipated before Phase 3 began).

## Where This Document Gets Updated

Whenever a new layer, interface, or cross-cutting concern is introduced,
this file is updated in the same commit/PR — including, per a real gap
found and fixed before Phase 4 began, when a phase's own milestones
complete (this document went stale relative to all of Phase 3 until
this pass, having last been updated just *before* Phase 3 started).
Individual *decisions* (why a choice was made, what alternatives were
considered) belong in [docs/adr/](docs/adr/) rather than here — this
document describes the current, real shape of the system,
distinguishing it explicitly from planned future work; ADRs preserve
the reasoning behind each decision.
