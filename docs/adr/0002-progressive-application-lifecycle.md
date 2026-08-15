# ADR-0002: Model `Application` as a Progressive Lifecycle, Not a Fully-Formed Record

## Status

Accepted — 2026-07-09

## Context

An `Application` needs to represent a real user workflow: a job is
identified, a draft is started, a resume is picked, answers are filled in,
a cover letter is attached, and only then is it submitted. At any point
before submission, it's normal and expected for `resume_id`,
`cover_letter_template_id`, and `answer_ids` to be unset.

If the `Application` Pydantic model required all of these fields at
construction time, there would be no way to represent an in-progress draft
as a valid domain object — every partially-filled-in application would
either fail validation or require awkward placeholder values.

## Decision

`Application` is modeled as a lifecycle:

- **Required at creation (`DRAFT` state):** `id`, `profile_id`,
  `job_posting_id`, `created_at`, `current_status` (defaults to `DRAFT`),
  and an initial `status_history` entry.
- **Optional, filled in progressively:** `resume_id`,
  `cover_letter_template_id`, `answer_ids` (defaults to an empty list).

Validation is split by *kind of rule*, not lumped into one place:

- **Domain invariants**, enforced inside the `Application` model itself:
  `status_history` is append-only and non-empty; `current_status` always
  equals the most recent history event; status transitions are
  structurally valid (e.g. `DRAFT` cannot jump directly to `OFFER`). These
  protect the object's own internal consistency and hold true regardless
  of the surrounding workflow.
- **Business process rules**, enforced in use cases (e.g.
  `SubmitApplicationUseCase`, Milestone 6): a resume must be attached
  before submission, the target job posting must still be valid, etc.
  These rules are about *when an action is permitted* — they depend on
  context and can change over time without altering what an `Application`
  fundamentally *is*.

## Alternatives Considered

- **Require all fields at construction, with placeholder/sentinel values
  for unset ones.** Rejected: this makes "no resume yet" indistinguishable
  from "resume field misused," and pushes accidental complexity into every
  consumer of the model, which now has to know about sentinel values.
- **Pydantic validators on `Application` that require resume/answers once
  `current_status != DRAFT`.** Considered, and not unreasonable, but
  rejected for now: it ties the domain model to the full set of
  submission requirements, which are a business process concern likely to
  evolve per job platform (Phase 4) — e.g., some platforms may not require
  a cover letter at all. Keeping that check in `SubmitApplicationUseCase`
  means the domain model doesn't need to change every time a platform's
  submission requirements do.
- **A separate `DraftApplication` vs. `SubmittedApplication` type
  hierarchy.** Considered for modeling the lifecycle via distinct types
  (a common DDD/functional pattern). Rejected for this project's current
  scale: it would meaningfully increase complexity (repository and
  use-case code would need to handle multiple types per aggregate) for a
  benefit — compile-time-enforced state — that Python's type system
  doesn't check as strictly as a language like TypeScript or Rust would.
  Worth revisiting if the lifecycle grows significantly more complex.

## Consequences

**Positive:**
- A `DRAFT` application with no resume attached is a perfectly valid
  domain object — no placeholder values, no special-casing.
- Submission requirements can evolve (e.g., per-connector rules in Phase
  4) without touching the domain model, only the relevant use case.
- The domain model stays focused on "is this object internally
  coherent," which is the question it's actually positioned to answer.

**Trade-offs:**
- It's possible to construct an `Application` that "looks done" (has a
  resume, template, and answers) but was never actually validated for
  submission — the model itself won't stop you from inspecting a
  not-yet-submitted `Application` that happens to have every optional
  field filled in. This is intentional: readiness is a use-case-level
  question, but it does mean a reviewer can't tell "ready" from "actually
  submitted" by looking at field presence alone — `current_status` is the
  authoritative signal for that, not field completeness.
- Two places to look (domain model + use case) to understand the full
  set of rules governing an `Application`'s lifecycle, rather than one.
  Mitigated by keeping this ADR and `ARCHITECTURE.md` up to date as the
  authoritative map of which rule lives where.

## References

- [docs/diagrams/domain-model.md](../diagrams/domain-model.md) — aggregate
  diagram reflecting the optional fields described here
- ADR-0001 — Clean Architecture layering that this decision depends on
  (use cases as the home for business process rules)
