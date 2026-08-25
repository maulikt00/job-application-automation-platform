# Architecture

This document describes JAAP's software architecture **as it actually
exists today** (through Milestone 13 / the pre-Phase-3 cleanup pass),
distinguishing built functionality from planned future work. For the
*reasoning* behind these choices, see [docs/adr/](docs/adr/).

## Guiding Principle: The Dependency Rule

> Source code dependencies always point inward. Inner layers know nothing
> about outer layers.

```
┌──────────────────────────────────────────────────────────┐
│  Presentation (CLI today; FastAPI/NiceGUI planned Phase 5) │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Infrastructure (SQLite + Playwright today;            │ │
│  │  Claude/Ollama/connectors planned Phase 3-4)           │ │
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
worked example below distinguishes them.

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
  `ReferentialIntegrityError`, `BrowserAutomationError`. These represent
  violations of an aggregate's own internal consistency, distinct from
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
  (`field_matcher.py`). **Not yet defined:** `AIProvider`,
  `WebsiteConnector` — these are Phase 3/4 interfaces, planned but not
  built.
- **`use_cases/`** — one class per user-facing action, each constructor-
  injected with only the interfaces it needs: `CreateProfileUseCase`,
  `AddResumeUseCase`, `SaveCoverLetterTemplateUseCase`,
  `SaveAnswerUseCase`, `StartApplicationUseCase`,
  `AttachResumeToApplicationUseCase`, `SubmitApplicationUseCase`,
  `AutofillApplicationUseCase`, `ReviewApplicationUseCase`. **Not yet
  built:** any AI-content-generation use case (`GenerateCoverLetterUseCase`
  and similar are Phase 3/Milestone 16-18 work).
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
  `ApplicationNotFoundError`, `ApplicationNotReadyForSubmissionError`).
  Business-rule violations, not domain invariants (see ADR-0002/0006).
- **`dto/`** — still an empty scaffold. Deliberately not built yet
  (ADR-0006): no concrete consumer has needed one so far; use cases
  currently accept plain parameters and return domain objects directly.

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
- **`config/`** — `settings.py` (a single Pydantic `Settings` object,
  loaded from environment variables/`.env`, injected everywhere rather
  than reached for as a global) and `logging_config.py`
  (`configure_logging()`, console text + rotating JSON file handlers).

**Not yet implemented** (empty `__init__.py` scaffolds only):
`infrastructure/ai/` (planned: `ClaudeProvider`, `OllamaProvider`,
Phase 3) and `infrastructure/connectors/` (planned:
`GreenhouseConnector`, `LeverConnector`, `WorkdayConnector`, and a
LinkedIn connector, Phase 4).

**Depends on:** application (to implement its interfaces) and domain.
Never depended upon by application or domain — infrastructure is the
outermost "plug-in" layer. `infrastructure/ai/` and `infrastructure/browser/`
additionally never import each other (see "AI / Browser Separation"
below) — currently trivially true since `ai/` is empty, but enforced by
an automated test so it stays true once Phase 3 populates it.

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
- **`commands/`** — `profile_commands.py`, `resume_commands.py`,
  `application_commands.py`. Each handler is a few lines of pure
  orchestration: call a use case, print the result, return an exit
  code. `application_commands.py`'s `review` command is the one
  handler that constructs a real `PlaywrightBrowserEngine` directly
  (inside its own function, not eagerly in `build_context()`, since
  launching a browser is comparatively slow and no other command needs
  one — see ADR-0012).

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
command doesn't need (e.g. no command pays a browser-launch cost unless
it actually uses one).

## Composition Over Inheritance

- `ExactFieldMatcher` implements `FieldMatcher` independently — no base
  class with shared behavior. It's a `Protocol` specifically because a
  second, AI-assisted implementation is anticipated for Phase 3 (see
  ADR-0010); until then, it's the only one.
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
real database or browser *unless the test is specifically verifying
that real implementation* (see "Testing Strategy" below).

## AI / Browser Separation

A structural rule: **AI code and browser automation code must never
import each other.** Currently trivially satisfied, since
`infrastructure/ai/` is empty — there is nothing yet for
`infrastructure/browser/` to accidentally import, or vice versa. This
becomes a real, checkable constraint once Phase 3 populates `ai/`,
which is why an automated architecture-boundary test now enforces it
(see below) rather than relying solely on manual discipline going
forward.

Design intent for when this becomes concrete: browser automation
collects structured page/form information (`DetectedField`, form
values); AI (once built) will assist with text generation and decision
support; a use case orchestrates the two but never lets one control the
other directly — neither infrastructure package will ever import the
other.

## Architecture Boundary Tests

`tests/unit/architecture/test_dependency_boundaries.py` (added as part
of the pre-Phase-3 cleanup, alongside this document) statically inspects
every module's imports (via Python's `ast` module — no third-party
architecture-linting dependency) and asserts:

- `domain/` never imports from `application/`, `infrastructure/`, or
  `presentation/`.
- `application/` never imports from `infrastructure/` or `presentation/`.
- `infrastructure/ai/` never imports from `infrastructure/browser/`.
- `infrastructure/browser/` never imports from `infrastructure/ai/`.

This makes the dependency rule and the AI/browser separation
continuously verified facts, not just documented intentions — a
violation fails the test suite immediately, the same day it's
introduced, rather than being caught (or missed) in review.

## Data Flow — Worked Example (Current, Real)

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

## Data Flow — Future Example (Not Yet Built, Phase 3)

Once `AIProvider`, `ClaudeProvider`/`OllamaProvider`, and an AI-content
use case exist: a future `GenerateCoverLetterUseCase` would ask its
injected `ProfileRepository`/`JobPostingRepository` for domain objects,
build a prompt, and call its injected `AIProvider.generate_text(prompt)`
— not knowing or caring whether that's Claude or Ollama underneath. The
resulting text would flow to the CLI for human review/editing, then
either be saved as a `CoverLetterTemplate` or passed directly as
`SubmitApplicationUseCase`'s `cover_letter_text_override` if kept as
one-off content (exactly the case ADR-0013 designed for). None of this
exists yet; described here only so the shape of the interfaces already
built (`AutofillApplicationUseCase`'s pattern, `SubmitApplicationUseCase`'s
override parameter) is visibly consistent with what Phase 3 will need.

## Testing Strategy

- **All tests currently live under `tests/unit/`.** `tests/integration/`
  exists as an empty scaffold (from Milestone 1's original planned
  layout) but is not actually used — in practice, tests that exercise
  real infrastructure (a real SQLite file, a real headless Chromium
  instance) live alongside fake-based tests under `tests/unit/`, with
  the module docstring stating clearly which kind each file is. This
  document is corrected to reflect that actual practice rather than the
  originally planned (but unused) split.
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
- **AI providers, once built, will be mocked in unit tests** — no
  real Claude/Ollama API call should ever run in the test suite (cost,
  determinism, and CI credential concerns). This is a stated intention
  for Phase 3, not yet a built or tested fact.

## Where This Document Gets Updated

Whenever a new layer, interface, or cross-cutting concern is introduced,
this file is updated in the same commit/PR. Individual *decisions* (why
a choice was made, what alternatives were considered) belong in
[docs/adr/](docs/adr/) rather than here — this document describes the
current, real shape of the system, distinguishing it explicitly from
planned future work; ADRs preserve the reasoning behind each decision.
