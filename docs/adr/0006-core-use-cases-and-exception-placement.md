# ADR-0006: Core Use Case Set, Exception Placement, and Deferred DTOs

## Status

Accepted — 2026-07-09

## Context

Milestone 1's original roadmap sketch named a placeholder use case set
(`CreateProfileUseCase`, `AddResumeUseCase`, `SelectResumeUseCase`,
`SaveCoverLetterTemplateUseCase`, `RecordApplicationUseCase`) written
before ADR-0002 worked out `Application`'s progressive Draft→Submit
lifecycle in detail. By Milestone 6, every ADR referencing "the calling
use case" had been pointing specifically at a `SubmitApplicationUseCase`
that ADR-0002 deferred readiness validation to -- a design the original
placeholder name didn't reflect. Building Milestone 6 required
reconciling the actual use case set with what the architecture had
already evolved into, plus resolving several smaller open questions:
where business-rule exceptions live, whether to build DTOs now, and how
much cross-aggregate validation `StartApplicationUseCase` should do.

## Decisions

### 1. The finalized use case set

- `CreateProfileUseCase`, `AddResumeUseCase`,
  `SaveCoverLetterTemplateUseCase`, `SaveAnswerUseCase` -- straightforward
  create/upsert use cases for the four Profile-owned aggregates.
- `StartApplicationUseCase` -- creates a Draft `Application`, replacing
  half of the original `RecordApplicationUseCase` placeholder.
- `SubmitApplicationUseCase` -- transitions Draft → SUBMITTED, the use
  case ADR-0002 named explicitly when it deferred submission-readiness
  validation out of the domain model.

`SelectResumeUseCase` (from the original sketch) was dropped as its own
use case: "selecting" a resume for an application is just setting
`Application.resume_id`, which carries no invariant (ADR-0002/0003) and
needs no dedicated orchestration -- it doesn't warrant a use case
separate from whatever flow attaches it (Milestone 7's CLI, or a future
`SubmitApplicationUseCase` precondition check).

`SaveAnswerUseCase` was added, not in the original sketch: once
`AnswerRepository` existed (Milestone 5) alongside
`CoverLetterTemplateRepository`, the asymmetry of having upsert support
for templates but not answers was an arbitrary gap worth closing.

### 2. Business-rule exceptions live in `application/exceptions.py`,
not `domain/exceptions.py`

A new module, separate from `domain/exceptions.py`, holds
`ProfileNotFoundError`, `JobPostingNotFoundError`,
`ApplicationNotFoundError`, and `ApplicationNotReadyForSubmissionError`.
This follows directly from ADR-0002's domain-invariant/business-rule
split: none of these are violations of an aggregate's own internal
consistency (a `Profile` doesn't care whether some `Resume` claims to
reference it; `Application` is deliberately valid as an incomplete
Draft) -- they're preconditions a use case checks before acting.

The base class is named `UseCaseError`, not `ApplicationLayerError`:
"Application" already refers to two different things in this codebase
(the Clean Architecture layer, and the domain's `Application`
aggregate); a third overloaded meaning wasn't worth the naming
convenience.

### 3. No DTOs yet

`application/dto/` remains an empty scaffold. Building request/response
DTO classes now, with no consumer yet (the CLI is Milestone 7), would
mean guessing at a shape with nothing concrete to validate it against.
Use cases currently accept plain parameters and return domain objects
directly; real DTOs get introduced once Milestone 7's CLI has actual,
concrete needs to design them against.

### 4. `StartApplicationUseCase` verifies both `Profile` and
`JobPosting` exist

Neither check is a domain invariant -- `Application`'s constructor
accepts any `ProfileId`/`JobPostingId` per ADR-0002's progressive Draft
lifecycle, since the domain model has no way to know whether a given ID
corresponds to a real aggregate. Checking only `JobPostingId` (the more
obviously "external" reference) and skipping `ProfileId` was considered
and rejected: a Draft silently created against a nonexistent Profile is
a more confusing failure mode to debug later (e.g. in Milestone 7's CLI,
or a future REST API) than catching it immediately at creation time. The
two checks are ordered deliberately (`Profile` before `JobPosting`) and
that order is tested, so which error surfaces first for a
doubly-invalid request is predictable rather than incidental.

### 5. Use case file naming avoids overloading names reserved for later
phases

`manage_cover_letter_templates.py` (this milestone's CRUD for reusable
templates) is named to avoid colliding with a likely future
`generate_cover_letter.py` (Phase 3's AI-generated, per-application
content) -- these are different responsibilities and shouldn't share a
name even loosely. `start_application.py`/`submit_application.py`
replace the original scaffold's `record_application.py` name, which no
longer describes what either use case actually does.

## Alternatives Considered

- **Keeping `RecordApplicationUseCase`** as a single use case covering
  both creation and submission. Rejected: conflating "start a draft" and
  "submit it" into one use case would blur exactly the lifecycle
  distinction ADR-0002 spent an entire decision establishing.
- **A generic `NotFoundError(entity_type, id)`** instead of one
  exception class per aggregate. Considered, but rejected in favor of
  distinct classes: `except ProfileNotFoundError` at a call site is more
  informative and greppable than `except NotFoundError` with a
  string/enum discriminator, at a low cost (four short classes).
- **Skipping the `Profile` existence check** in
  `StartApplicationUseCase`, checking only `JobPosting`. Rejected; see
  decision #4.

## Consequences

**Positive:**
- Every use case is unit-tested with in-memory fake repositories (see
  `tests/unit/application/use_cases/fakes.py`), the direct payoff of
  Milestone 5's `Protocol`-based interfaces -- no database involved in
  any use case test.
- The domain-invariant/business-rule split from ADR-0002 now has a
  concrete second example (`ApplicationNotReadyForSubmissionError`)
  beyond the one that motivated it, confirming the split generalizes.

**Trade-offs:**
- Use cases currently return raw domain objects and accept plain
  parameters, which is fine for direct testing but will need
  reconciling once Milestone 7's CLI (and whatever presentation-layer
  formatting it needs) is built -- deferred deliberately, not
  overlooked (see decision #3).

## References

- ADR-0002 -- the domain-invariant/business-rule split this milestone's
  exception placement and `SubmitApplicationUseCase`'s design directly
  extend.
- ADR-0005 -- the repository `Protocol` interfaces every use case here
  is constructor-injected with.
- `PROJECT_ROADMAP.md` -- updated to reflect the finalized use case
  names in place of the original placeholder sketch.
