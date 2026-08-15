# ADR-0001: Adopt Clean Architecture with Strict Layer Boundaries

## Status

Accepted — 2026-07-09

## Context

JAAP needs to integrate with several volatile, third-party-dependent
systems that are expected to change independently and grow over time:

- Multiple AI providers (Claude, Ollama, and others in the future)
- Multiple job platforms (Greenhouse, Lever, Workday, and others in the
  future), each with different form structures and quirks
- Browser automation (Playwright), whose API surface will evolve
- A persistence layer (SQLite now, potentially something else later)
- Multiple front doors over time (CLI now, FastAPI/NiceGUI later)

The project is also explicitly a *learning vehicle* for software
architecture, so the chosen structure needs to make good design pressure
visible and enforceable, not just theoretically correct.

A secondary, non-negotiable constraint: **AI must never be able to control
browser automation directly.** The system should refuse to blindly submit
applications; a human reviews AI-generated content and browser-filled forms
before anything is finalized. This needs to be true structurally, not just
by convention, so it survives contributors who haven't read this ADR.

## Decision

Adopt Clean Architecture with four layers — **Domain, Application,
Infrastructure, Presentation** — with the Dependency Rule strictly enforced:
source code dependencies point inward only.

- **Domain** holds business objects and rules with zero external
  dependencies.
- **Application** holds use cases (orchestration logic) plus abstract
  interfaces ("ports") for anything it needs from the outside world
  (repositories, AI providers, browser automation, website connectors).
- **Infrastructure** holds concrete implementations of those interfaces
  (SQLAlchemy repositories, `ClaudeProvider`/`OllamaProvider`, the
  Playwright engine, `GreenhouseConnector`/`LeverConnector`/
  `WorkdayConnector`).
- **Presentation** holds the front door(s) (CLI first) that call use cases
  and contain no business logic themselves.

Interfaces are defined in the application layer (not infrastructure), so
that infrastructure depends on application — never the reverse. This is
Dependency Inversion in practice: a use case says "I need something that
generates text," never "I need Claude specifically."

Composition over inheritance is used throughout: `ClaudeProvider` and
`OllamaProvider` each independently implement `AIProvider`; they don't
share a base class with default behavior. The same applies to website
connectors and repositories. New providers/connectors are added by writing
a new class that satisfies an existing interface — never by modifying an
existing one.

The AI/browser separation is enforced structurally: `infrastructure/ai/`
and `infrastructure/browser/` never import each other. Only the
application layer's use cases know both exist, and only as abstract
interfaces. A use case can call an `AIProvider` to draft text and, in a
later, separate step, call a `BrowserAutomationEngine`/`WebsiteConnector`
to fill a form — but nothing in the codebase allows an AI provider to
invoke browser automation directly, and the autofill use case always stops
before final submission for human review.

## Alternatives Considered

- **A simpler layered (n-tier) architecture** without strict inward-only
  dependencies (e.g., a "service layer" that directly imports SQLAlchemy
  and Playwright). Rejected because it would let volatile third-party
  changes (a Playwright API change, a new AI SDK) ripple into business
  logic, and would make unit testing require real infrastructure.
- **Inheritance-based provider/connector hierarchies** (e.g.
  `BaseAIProvider` with shared logic, `ClaudeProvider(BaseAIProvider)`).
  Rejected because job platforms and AI APIs differ enough in behavior
  that shared base-class logic tends to become a leaky abstraction that
  gets special-cased per subclass — composition against a narrow interface
  keeps each implementation independent and easier to reason about.
- **A monolithic script/module approach** (fastest to get *something*
  working). Rejected outright given the project's explicit goals: this is
  meant to be a multi-year, contributor-friendly, portfolio-quality
  codebase, not a one-off script.

## Consequences

**Positive:**
- New AI providers or website connectors require adding a file, not
  editing existing, working code.
- Every use case is unit-testable in isolation using fakes/mocks for its
  injected interfaces — no real database, browser, or network call needed
  in unit tests.
- The "AI never controls the browser" requirement is enforced by the
  dependency structure itself, not just documented as a policy.

**Trade-offs:**
- More upfront ceremony than a flat script: every new capability requires
  thinking about which layer it belongs in and, often, defining an
  interface before an implementation.
- Requires discipline to maintain the boundary (e.g., resisting the
  temptation to import SQLAlchemy directly into a use case "just this
  once"). Code review and this ADR are the main safeguards against drift.

## References

- Robert C. Martin, *Clean Architecture* (the source of the layer names
  and the Dependency Rule used here)
- [ARCHITECTURE.md](../../ARCHITECTURE.md) for the current, formalized
  shape of the system this decision produced
