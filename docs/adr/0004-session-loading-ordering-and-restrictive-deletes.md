# ADR-0004: Session Eager-Loading Policy, Ordered Answer Associations, and Restrictive Deletes

## Status

Accepted — 2026-07-09

## Context

A lead-engineer-level review of Milestone 4 (the SQLite/SQLAlchemy
database layer), conducted before Milestone 5 builds repositories against
it, surfaced four issues:

1. `create_session_factory` sets `expire_on_commit=False`, which keeps
   already-loaded scalar attributes readable after `session.commit()`,
   but does **not** prevent `DetachedInstanceError` on a relationship
   that hasn't been touched yet once its session has closed. A
   repository that returns a raw ORM object (or accesses an unloaded
   relationship) after its `session_scope()` block exits would fail.
2. `ApplicationStatusEventORM.sequence` has no automatic value -- some
   code has to assign it. Where that responsibility lives needed to be
   made explicit before a repository is written to (potentially
   incorrectly) compute it independently.
3. `Application.answer_ids` is an ordered `tuple` in the domain model,
   but the `application_answers` join table (a plain SQLAlchemy
   `secondary=` many-to-many) has no column recording order. A save/load
   round trip could silently reorder `answer_ids`.
4. `application_answers.answer_id` used `ON DELETE CASCADE`. Deleting an
   `Answer` that a past `Application` referenced would silently delete
   the join row -- erasing, without warning, the record of which answer
   an application used. This is the persistence-layer expression of a
   gap flagged during the Milestone 2 review (`Application` has no
   snapshot of what was actually submitted, only mutable references).

## Decision

### 1. Eager-load relationships required for domain reconstruction; document the rule for everything else

`ApplicationORM.status_events` and `ApplicationORM.answer_associations`
(see #3 below) are marked `lazy="selectin"`, since a repository
reconstructing an `Application` domain object always needs both of these
to build `status_history` and `answer_ids`. This removes the most common
way to trip over `DetachedInstanceError` by construction, not by
discipline.

This does **not** extend to `ApplicationORM.profile`,
`.job_posting`, `.resume`, or `.cover_letter_template` -- the domain
model only needs their *IDs* (already-loaded scalar columns), never the
related objects themselves, so eager-loading them would be pure overhead
with no corresponding need.

For anything not covered by this default (a relationship added later, or
any case where an ORM object needs to be inspected outside its
originating session for some other reason), the rule remains: **all
attribute/relationship access needed to build a domain object happens
while its session is still open.** A repository returns a fully
constructed domain object out of its `session_scope()` block, never a
lingering ORM object.

### 2. `sequence` is derived from the domain object's already-ordered tuple, not independently computed

No schema change. `Application.status_history` is already a correctly
ordered `tuple[ApplicationStatusEvent, ...]` by construction --
`Application.transition_to()` only ever appends to it (see
`domain/models/application.py`). A repository persisting an `Application`
assigns `sequence = index` while enumerating that tuple; it never needs
to compute "the next sequence number" independently. This is a
documented repository responsibility (see `ApplicationStatusEventORM`'s
docstring), not a database-enforced one -- enforcing it in the schema
(e.g. via a per-parent auto-increment) would cost meaningfully more
complexity than the domain layer's existing ordering guarantee already
solves for free.

### 3. Application <-> Answer becomes an ordered association object

The plain `application_answers` many-to-many table is replaced with a
full ORM-mapped class, `ApplicationAnswerORM`, carrying its own
`position` column -- SQLAlchemy's simple `secondary=` relationship
pattern does not support setting extra columns on the join row, so
preserving order requires this "association object" pattern rather than
a plain join table.

`ApplicationORM.answer_associations` (ordered by `position`) replaces the
previous `ApplicationORM.answers`. A repository reconstructing the
domain object's `answer_ids` tuple reads `answer_associations` in
`position` order.

This decision assumes answer order carries meaning worth preserving --
e.g., matching the order questions appeared on the source application
form, which the Milestone 10 autofill engine may care about. The
domain model's `Application.answer_ids` already being an ordered `tuple`
(a Milestone 2 decision) is consistent with this assumption; no domain
model change is required here, only the persistence layer needed to
catch up to what the domain model already implied.

### 4. Restrictive deletes on Application's references, to stop silent history loss

`application_answers.answer_id`'s foreign key changes from `ON DELETE
CASCADE` to `ON DELETE RESTRICT`: deleting an `Answer` still referenced
by any `Application` now fails loudly (`IntegrityError`) instead of
silently deleting the join row and erasing the historical record.

**Extending the same reasoning beyond what was originally flagged:**
`ApplicationORM.resume_id` and `.cover_letter_template_id` had `ON DELETE
SET NULL`, which is the identical footgun in a different shape --
deleting a `Resume` or `CoverLetterTemplate` still referenced by an
`Application` would silently null out the reference, losing the record
of which one was used, with no error and no trace. Both now use `ON
DELETE RESTRICT` as well, for consistency with the same principle. This
extension was not part of the original four flagged items; it is called
out explicitly here (and in the corresponding code changes) rather than
folded in silently.

This is a deliberate partial fix, not the complete answer.
`RESTRICT` only stops *silent* data loss -- it does not solve "what did
this application actually say," which requires a snapshot of the
resolved content (the literal cover letter text, the literal
question-answer pairs used), separate from the mutable ID references.
That is the correct, larger fix identified in the Milestone 2 review, and
it is deliberately deferred to Milestone 6, when `SubmitApplicationUseCase`
is built and "what does submission actually preserve" becomes a concrete,
testable question rather than a database-layer concern to guess at ahead
of time.

## Alternatives Considered

- **For #1:** relying on documentation alone (no eager loading), or
  eager-loading every relationship on `ApplicationORM` regardless of
  whether the domain model needs it. Rejected the former as leaving a
  known, easy-to-hit footgun in place when a structural fix was cheap;
  rejected the latter as eager-loading data (`profile`, `job_posting`,
  `resume`, `cover_letter_template` objects) the domain reconstruction
  will never use.
- **For #2:** a per-`application_id` auto-increment computed by the
  database (via trigger or subquery). Rejected: SQLite has no native
  per-group auto-increment, and the complexity isn't justified when the
  domain object already provides a correct, ready-to-use order.
- **For #3:** changing `Application.answer_ids` from `tuple` to
  `frozenset` (i.e., deciding order never mattered) and leaving the
  plain join table as-is. Rejected on the judgment that order plausibly
  matters to a concrete, already-planned future consumer (the autofill
  engine), and the cost of preserving it now is small relative to
  retrofitting it once real data exists.
- **For #4:** implementing the full content-snapshot fix now, in this
  milestone. Rejected as out of scope for a database-layer cleanup pass
  -- it's a domain-model and use-case design question that belongs in
  Milestone 6, where `SubmitApplicationUseCase` actually needs to answer
  it. `RESTRICT` is a deliberately minimal, compatible-with-either-future
  stopgap.

## Consequences

**Positive:**
- The most common way to hit `DetachedInstanceError` during repository
  development is removed by construction, not left to reviewer vigilance.
- `answer_ids` ordering now survives a save/load round trip, matching
  what the domain model already implied.
- Deleting an `Answer`, `Resume`, or `CoverLetterTemplate` that's still
  referenced by an `Application` now fails loudly, giving a future use
  case the chance to handle it deliberately (block the delete, warn the
  user, etc.) instead of silent data loss.

**Trade-offs:**
- `ApplicationAnswerORM` is one more table/class than a plain join table
  would require, and any code working with an application's answers now
  goes through `answer_associations` (a list of association objects with
  `.answer` and `.position`) rather than a direct `list[AnswerORM]`.
- `RESTRICT` deletes mean any future "delete this resume" feature must
  explicitly handle the case where it's still referenced by an
  application -- this is intentional friction, not an oversight, but it
  is a use case (Milestone 6+) that now needs to exist rather than being
  silently unnecessary.

## References

- [docs/diagrams/domain-model.md](../diagrams/domain-model.md)
- ADR-0002 -- the progressive `Application` lifecycle this eager-loading
  policy and restrictive deletes both support.
- ADR-0003 -- entity identity and mutation strategy; `transition_to()`'s
  ordering guarantee on `status_history` is what makes decision #2 above
  free.
