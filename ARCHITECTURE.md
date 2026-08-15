# Architecture

This document describes JAAP's software architecture: the layers, the
dependency rules between them, the key interfaces, and how a request flows
through the system. For the *reasoning* behind these choices (not just the
current state), see [docs/adr/](docs/adr/).

## Guiding Principle: The Dependency Rule

> Source code dependencies always point inward. Inner layers know nothing
> about outer layers.

```
┌──────────────────────────────────────────────────────────┐
│  Presentation (CLI, later FastAPI / NiceGUI)              │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Infrastructure (SQLite, Playwright, Claude, Ollama,   │ │
│  │  Greenhouse/Lever/Workday connectors, Config)          │ │
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
diagram below distinguishes them.

## Layers

### 1. Domain (`src/jaap/domain/`)

Pure business objects and rules: `Profile`, `Resume`, `CoverLetterTemplate`,
`Answer`, `JobPosting`, `Application`, `ApplicationStatus`. Implemented as
Pydantic models / dataclasses. No SQLAlchemy, no Playwright, no AI SDKs, no
knowledge of how they're persisted or displayed.

**Depends on:** nothing else in this project.

### 2. Application (`src/jaap/application/`)

Two things live here:

- **Use cases** (`use_cases/`) — one class per user-facing action
  (`GenerateCoverLetterUseCase`, `AutofillApplicationUseCase`,
  `RecordApplicationUseCase`, ...). Each use case receives its dependencies
  through its constructor (dependency injection) — it is handed a
  repository, an AI provider, a browser engine, etc., and never constructs
  them itself.
- **Interfaces / ports** (`interfaces/`) — abstract contracts
  (`ProfileRepository`, `AIProvider`, `BrowserAutomationEngine`,
  `WebsiteConnector`) that use cases depend on. These are Python `Protocol`
  or `ABC` definitions with no implementation.

**Depends on:** domain only. Never imports anything from `infrastructure/`
or `presentation/`.

This is the layer that makes "add a new AI provider" or "add a new job site"
purely additive: a use case is written once against `AIProvider`, and works
unmodified with any class that implements that interface.

### 3. Infrastructure (`src/jaap/infrastructure/`)

Concrete implementations of the interfaces defined in `application/interfaces/`:

- `database/` — SQLAlchemy ORM models, session management, and repository
  implementations (`SqliteProfileRepository`, etc.) backed by SQLite.
- `ai/` — `ClaudeProvider`, `OllamaProvider`, each implementing `AIProvider`.
- `browser/` — Playwright-based `BrowserAutomationEngine`, form field
  detector, and autofill engine.
- `connectors/` — `GreenhouseConnector`, `LeverConnector`,
  `WorkdayConnector`, each implementing `WebsiteConnector`.
- `config/` — a single Pydantic `Settings` object that loads environment
  variables / `.env` files.

**Depends on:** application (to implement its interfaces) and domain.
Never depended upon by application or domain — infrastructure is the
outermost "plug-in" layer.

### 4. Presentation (`src/jaap/presentation/`)

The "front door(s)" to the application. Phase 1 is CLI-only
(`presentation/cli/`); later, FastAPI and NiceGUI are added *alongside* the
CLI, not as replacements. Every front door calls the same use cases — none
of them contain business logic themselves.

**Depends on:** application (to call use cases) and, at the composition
root only, infrastructure (to construct concrete implementations to inject).

### Cross-cutting: `utils/`

Small, pure, dependency-free helper functions used across layers. If a
"utility" needs file/network/database I/O, it isn't a util — it belongs in
infrastructure.

## Composition Root

Somewhere near the entry point (initially inside `presentation/cli/main.py`),
one place is responsible for constructing concrete infrastructure objects
and injecting them into use cases. This is the **only** place in the whole
codebase allowed to import both an interface and its concrete
implementation together. Everywhere else, only the interface is known.

## Composition Over Inheritance

- `ClaudeProvider` and `OllamaProvider` don't share a base class with
  shared behavior — each independently implements the `AIProvider`
  contract. A use case is *composed* with whichever provider is injected.
- `GreenhouseConnector`, `LeverConnector`, `WorkdayConnector` each
  implement `WebsiteConnector` independently, rather than forming an
  inheritance chain that gets brittle as soon as one site's flow looks
  nothing like another's.
- Repositories are injected into use case constructors, not provided via a
  shared "DatabaseAwareUseCase" base class.

This is what makes the system testable: every unit test hands a use case a
fake/mock implementation of whatever interface it depends on, so tests never
need a real database, browser, or network call.

## AI / Browser Separation

A structural rule, not just a convention: **AI code and browser automation
code never import each other.** The only thing that knows both exist is the
use case layer, and it only knows them as abstract interfaces
(`AIProvider`, `BrowserAutomationEngine`). Browser automation collects
structured page/form information; AI assists with text generation and
decision support; a use case orchestrates the two but never lets one
control the other directly.

## Data Flow — Worked Example

**Scenario:** generate a tailored cover letter, then autofill an
application, with human review at each hand-off.

1. **Presentation (CLI)** calls
   `GenerateCoverLetterUseCase.execute(profile_id, job_posting_id)`. It has
   no knowledge of Claude, Ollama, or the database engine — only that this
   use case exists and returns a `CoverLetter` domain object.
2. **Use case** asks its injected `ProfileRepository` and
   `JobPostingRepository` for domain objects. Whether that's backed by
   SQLite today or something else in the future is invisible to it.
3. **Use case** builds a prompt from those domain objects and calls its
   injected `AIProvider.generate_text(prompt)`. Whether that's Claude or
   Ollama underneath is invisible to it.
4. **Use case** returns a `CoverLetter` domain object to the CLI, which
   displays it to the user for review/editing.
5. Once approved, `AutofillApplicationUseCase` takes the reviewed cover
   letter, profile, and resume, and hands them to the injected
   `WebsiteConnector` (e.g. `GreenhouseConnector`), which uses the
   `BrowserAutomationEngine` (Playwright) to detect fields and fill them in
   — **stopping before final submission** and returning control to the user.

## Testing Strategy

- **Unit tests** (`tests/unit/`) — test one layer at a time, in isolation,
  using fakes/mocks for every injected interface. These are fast and
  deterministic; no real database, browser, or network call.
- **Integration tests** (`tests/integration/`) — exercise real
  infrastructure (a real SQLite file, a real Playwright browser in headless
  mode against fixture HTML) to verify the concrete implementations
  actually satisfy their contracts.
- Browser interactions and AI providers are always mocked in unit tests;
  integration tests are the only place real ones run.

## Where This Document Gets Updated

Whenever a new layer, interface, or cross-cutting concern is introduced,
this file is updated in the same commit/PR. Individual *decisions* (why a
choice was made, what alternatives were considered) belong in
[docs/adr/](docs/adr/) rather than here — this document describes the
current shape of the system, ADRs preserve the reasoning behind it.
