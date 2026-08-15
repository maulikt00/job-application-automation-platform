# ADR-0003: Entity Identity, Mutation Strategy, and Connector Extensibility

## Status

Accepted — 2026-07-09

## Context

A lead-engineer-level review of Milestone 2's domain models, run specifically
against the systems the roadmap commits to next -- SQLite persistence
(Milestone 4-5), Playwright automation (Milestone 8-12), multiple AI
providers (Milestone 13-18), and additional job-site connectors including
LinkedIn (Milestone 19-23) -- surfaced four structural risks worth fixing
before more code is built on top of today's shape.

### 1. Entity identity was undefined

Pydantic's default `BaseModel.__eq__` compares every field. For entities
(`Profile`, `Resume`, `Application`, etc.), that's wrong: two `Application`
objects with the same `id` but different `current_status` -- e.g. one
freshly loaded from the database, one locally mutated -- are the *same*
application, not two different ones. Left unaddressed, this becomes a real
bug the moment repository code deduplicates loaded entities, uses one as a
dict/set key, or diffs "what changed" before calling `save()` -- all of
which rely on identity, not field equality, and none of which existed yet
in Milestone 2 to expose the gap.

### 2. Nothing enforced invariants on mutation, only on construction

Pydantic v2 validates fields at construction time only, by default. Every
domain model could have a field reassigned after creation with no
re-validation: a `Resume.file_path` changed to a `.txt`, an
`Answer.question_key` set to something never slugified, an
`Application.current_status` set directly, bypassing `transition_to()` and
leaving `status_history` out of sync. This matters specifically because of
what's coming: repositories reconstructing objects from raw rows, and
Playwright/AI code writing back into these objects as workflows progress,
are exactly the code paths most likely to assign a field directly rather
than go through a constructor.

### 3. `JobPosting.platform` was a closed enum

ADR-0001 commits to new job-site support being additive (a new connector
file), never requiring changes to existing code. A fixed `JobPlatform`
enum broke that promise: supporting LinkedIn meant editing
`job_posting.py`, a core domain file, which is exactly the coupling the
architecture was designed to avoid.

### 4. `JobPosting` had no extension point for connector-specific data

Greenhouse, Lever, Workday, and LinkedIn each expose their own identifiers
and metadata shapes (a Greenhouse board token, a LinkedIn job URN) that a
connector needs in order to reliably re-identify or re-fetch a posting.
Without a shared, open slot for this, the natural failure mode is each
connector milestone adding its own dedicated field
(`greenhouse_board_token`, `lever_posting_id`, ...) directly to the shared
domain model -- the same coupling problem as #3, showing up in the data
shape instead of the type system. This also doubles as the fix for a
related gap: `url` alone is an unreliable deduplication key, since
`HttpUrl` normalization and redirects can make the same posting
serialize to different URL strings across scrapes.

## Decision

### Entity identity

Introduce an `Entity` base class (`domain/models/entity.py`) that all
aggregate roots (`Profile`, `Resume`, `CoverLetterTemplate`, `Answer`,
`JobPosting`, `Application`) inherit from instead of `BaseModel` directly.
`Entity` defines `__eq__` and `__hash__` based solely on `(type, id)` --
not on any other field -- reflecting that entities are defined by identity,
not by their current attribute values. `ApplicationStatusEvent` remains a
plain `BaseModel` (frozen), since as a value object its equality is
correctly structural, not identity-based.

### Aggregate mutation strategy

Two tiers, depending on whether a field carries a cross-field invariant:

- **Fields with only single-field validation** (`Resume.file_path`,
  `Answer.question_key`, `JobPosting.platform`, `Profile.email`, etc.):
  enable `validate_assignment=True` on these models. Any later
  reassignment re-runs the same validator that ran at construction, so
  the gap between "validated at creation" and "silently invalid after a
  later assignment" is closed for the cost of one config flag per model.
- **Fields with a cross-field invariant** (`Application.current_status`
  and `status_history`, which must always agree with each other):
  `validate_assignment` cannot safely apply, because updating both fields
  to keep them consistent requires two sequential assignments, and
  validating after each one individually would reject the intermediate
  state. Instead, `Application` overrides `__setattr__` to reject direct
  assignment to `current_status` or `status_history` from outside the
  class, raising `DomainError`. `transition_to()` remains the sole
  sanctioned way to change status, and internally updates both fields
  together via a bypass (`object.__setattr__`) that skips the guard only
  for its own, already-consistent update. Fields on `Application` without
  a cross-field invariant (`resume_id`, `cover_letter_template_id`,
  `answer_ids`) remain freely settable, consistent with allowing a Draft
  to be filled in progressively (ADR-0002).

### Open platform identifiers

`JobPosting.platform` changes from a closed `Enum` to a plain, normalized,
non-empty string. `JobPlatform` remains as a small class of suggested
constants (`JobPlatform.GREENHOUSE`, `.LEVER`, `.WORKDAY`, `.LINKEDIN`,
`.OTHER`) for convenience and typo-avoidance, but the field itself accepts
any string a connector supplies. A new connector introducing a new
platform is then purely additive -- it never requires editing this model.

### Connector extension point

`JobPosting` gains two fields:

- `external_id: str | None` -- the source platform's own identifier for
  the posting (a Greenhouse job token, a LinkedIn job URN), used as a
  stable deduplication/re-fetch key, since `url` alone is not reliable
  for this.
- `platform_metadata: dict[str, str]` -- an open, connector-defined bag
  for any additional platform-specific data that doesn't warrant its own
  dedicated field.

Together these mean a new connector (Milestone 19+, including LinkedIn)
can carry whatever platform-specific data it needs without adding a new
field to `JobPosting` for every platform.

## Alternatives Considered

- **Entity identity via `__eq__`/`__hash__` defined individually on each
  model** instead of a shared base class. Rejected: six copies of
  identical logic is exactly the kind of duplication that drifts once one
  copy is updated and the others aren't.
- **`validate_assignment=True` on `Application` as well**, accepting that
  `transition_to()` would need to construct a new object via
  `model_copy(update=...)` rather than mutate in place. Rejected for now:
  it would change `Application`'s mutation semantics from "mutate in
  place" to "replace with a new instance," which ripples into how
  repositories and use cases are expected to hold and pass around an
  `Application` reference -- a bigger behavioral change than this
  refinement warrants. Worth reconsidering during Milestone 4 if
  persistence design finds in-place mutation awkward.
- **Dedicated fields per connector on `JobPosting`** (e.g.
  `greenhouse_board_token`, `linkedin_job_urn`). Rejected as the exact
  coupling problem this ADR exists to avoid.
- **Fully removing `JobPlatform`** in favor of bare string literals
  everywhere. Rejected: the constants cost nothing to keep and prevent
  typos (`"greenhouse"` vs `"Greenhouse"`) for the platforms we already
  know about, without constraining what a new connector can supply.

## Consequences

**Positive:**
- Repository code (Milestone 4-5) can safely deduplicate, hash, and diff
  loaded entities without hand-rolling identity comparisons per model.
- A field reassigned after construction -- by a repository reconstructing
  from a row, or by Playwright/AI code writing back into a workflow
  object -- is validated the same way it would be at construction, for
  five of the six aggregates.
- `Application`'s status invariant is now enforced structurally (raises
  `DomainError`), not just by documentation and convention.
- New job-site connectors, including LinkedIn, require no changes to
  `JobPosting` or any other existing domain file.

**Trade-offs:**
- `Application` still has one asymmetry: most fields validate on
  assignment (indirectly, since `validate_assignment` isn't set there
  either -- see note below) while `current_status`/`status_history` are
  actively guarded. This is a deliberate, documented exception, not an
  oversight, but it's a detail a new contributor needs to learn from this
  ADR or the class docstring rather than infer from the code alone.
- `platform_metadata: dict[str, str]` is intentionally untyped/open,
  which means no compile-time or validation-time guarantee about what
  keys a given connector will populate -- that contract lives in each
  connector's own documentation, not in the shared domain model.

## References

- ADR-0001 -- Clean Architecture and the connector-additivity promise this
  decision protects.
- ADR-0002 -- Progressive `Application` lifecycle; this ADR's mutation
  strategy extends that reasoning to cover *how* fields change, not just
  *which* fields are required at creation.
- [docs/diagrams/domain-model.md](../diagrams/domain-model.md) -- updated
  to reflect the `Entity` base class and `JobPosting`'s new fields.
