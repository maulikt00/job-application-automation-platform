# ADR-0005: Repository Interfaces and Domain/ORM Mapping Strategy

## Status

Accepted — 2026-07-09

## Context

Milestone 4 built the SQLite/SQLAlchemy schema but deliberately stopped
short of implementing repositories, per the roadmap's own split (M4:
"SQLAlchemy ORM models + SQLite session management, mapped to domain
models"; M5: "Repository interfaces & SQLite implementations"). Several
design questions needed answers before writing any repository code:
how the interfaces themselves should be defined, where domain/ORM
translation logic lives, what `get()` returns for a missing entity, how
`Application`'s status history and answer associations should be
reconciled on save, and how a database-level constraint violation should
surface to the application layer.

## Decisions

### 1. `typing.Protocol`, not `abc.ABC`

The six repository interfaces (`ProfileRepository`, `ResumeRepository`,
`CoverLetterTemplateRepository`, `AnswerRepository`,
`JobPostingRepository`, `ApplicationRepository`) are defined as
`Protocol` classes in `application/interfaces/repositories.py`, not
`ABC` subclasses.

This matches how `ARCHITECTURE.md` already describes `AIProvider` and
`WebsiteConnector` -- structural contracts the application layer depends
on, not a class hierarchy -- and extends `CONTRIBUTING.md`'s existing
"favor composition over inheritance" principle to the repository layer.
Concretely, it means a test double satisfying one of these interfaces
never needs to inherit from anything; it just needs matching method
names and signatures, which mypy verifies statically. `ABC` would give
the same static safety plus a runtime check at instantiation time, at
the cost of requiring every implementation (real or fake) to explicitly
subclass the interface.

### 2. Six independent interfaces, not one generic base

Each of the six interfaces is defined independently rather than
extending a shared `Repository[T]` generic base. The aggregates differ
enough in their extra methods (`JobPostingRepository`'s dedup lookup,
`ApplicationRepository`'s list-by-profile, etc.) that a generic base
would mostly save re-typing three method signatures six times, which
wasn't judged worth the added abstraction layer.

### 3. Mapping logic lives in dedicated mapper modules, not on the
repository or ORM classes

`infrastructure/database/mappers/` has one module per aggregate
(`profile_mapper.py`, etc.), each exposing `to_domain(orm) -> Domain`
and `update_orm(domain, orm) -> None`. This was chosen over two
alternatives: private methods inside each repository class (co-located,
but not independently testable without a repository instance), and
static methods on the ORM classes themselves (rejected outright, since
it would mean `models.py` needs to import domain types beyond the one
narrow, already-justified exception -- `JobPlatform`, per ADR-0004 --
eroding the "repositories are the translation boundary" principle
`models.py`'s own docstring states). Separate mapper functions mean the
trickiest translation logic (Application's, see #5 below) is unit
testable with plain Python objects, no database required.

### 4. `get()` returns `Optional[Entity]`; missing is not an error

Every repository's `get()` returns `None` when nothing matches, never
raises. This mirrors `session.get()`'s own semantics at the layer just
below, and keeps "not found" available as a normal, expected outcome a
use case can interpret in context, rather than forcing an exception-
handling path for what's often not an error at all (e.g. "does this
resume still exist" is a legitimate question, not a failure).

### 5. `Application.save()`: append-only status history, full
delete-and-recreate for answer associations

Two different reconciliation strategies for `Application`'s two
collections, because they have different mutation shapes:

- **`status_history`** is append-only in the domain model --
  `Application.transition_to()` (ADR-0002/0003) only ever adds events,
  never removes or reorders them. `update_orm()` compares
  `len(orm.status_events)` against `domain.status_history` and inserts
  only the tail beyond what's already persisted. This is provably
  correct, not just simple: the domain object's history is guaranteed
  by `transition_to()` to never be shorter or reordered relative to
  what's already in the database.
- **`answer_ids`** is not append-only -- a use case could remove an
  answer before submission, not just add one. Rather than compute a
  precise add/remove/reorder diff, every `save()` fully replaces the
  persisted `ApplicationAnswerORM` rows from the domain object's current
  `answer_ids` tuple. This is a deliberate simplicity-over-precision
  trade-off: the only thing lost is per-association "when was this
  answer first attached" history (there is no `created_at` on
  `ApplicationAnswerORM` to lose in the first place), which nothing in
  the roadmap currently needs. Revisit if a future feature (e.g. Phase 5
  analytics) needs that history -- at which point `ApplicationAnswerORM`
  would need its own `created_at` and this method would need a real diff
  instead of a replace.

**Implementation note surfaced during development, not just design:**
the answer-association replacement cannot safely live inside
`application_mapper.update_orm()`, because doing it correctly requires
an explicit `session.flush()` between clearing the old associations and
adding new ones. Without that flush, SQLAlchemy's unit-of-work can
conflate a removed-then-re-added association that happens to share the
same composite primary key (`application_id`, `answer_id` -- e.g. an
answer that stays attached but moves to a different `position`) with an
in-place `UPDATE`, which collides with the `(application_id, position)`
unique constraint mid-flush. This was caught by
`test_answer_ids_persist_and_reflect_removal_across_saves`, a real
repository-level integration test against SQLite -- the equivalent
mapper-only unit test (a transient, never-flushed ORM object) did not
catch it, since the bug only manifests when SQLAlchemy's unit-of-work
actually reconciles against previously-persisted rows. Because mappers
never touch a `Session` (see #3), this reconciliation -- clear, flush,
re-append -- lives in `SqliteApplicationRepository.save()` instead;
`application_mapper.update_orm()` handles every other field.

### 6. Database exceptions are translated at the repository boundary

`ResumeRepository.delete()`, `CoverLetterTemplateRepository.delete()`,
and `AnswerRepository.delete()` catch SQLAlchemy's `IntegrityError` (
raised by the `RESTRICT` foreign keys added in ADR-0004) and re-raise
`jaap.domain.exceptions.ReferentialIntegrityError` instead. This keeps
the dependency rule intact: the application layer's use cases only ever
need to handle exceptions in the domain's own vocabulary, never
`sqlalchemy.exc`. `ProfileRepository`, `JobPostingRepository`, and
`ApplicationRepository` don't need this translation, since none of
their delete paths hit a `RESTRICT` constraint (see each repository
class's docstring for which cascade behavior applies).

### 7. Session ownership: constructor-injected `session_factory`,
one `session_scope()` per method call

Every repository's constructor takes a `sessionmaker[Session]` (see
`session.py`'s `create_session_factory()`), and every method opens its
own `session_scope()`, does its work, and returns a fully-built domain
object before that `with` block closes. This directly enforces the
eager-loading/session-lifecycle rule from ADR-0004: all ORM
attribute/relationship access happens while the session is open, and a
repository never hands back a raw ORM object.

## Alternatives Considered

- **`abc.ABC`** for the interfaces -- rejected in favor of `Protocol`;
  see #1.
- **A generic `Repository[T]` base class** -- rejected; see #2.
- **Static `to_domain`/`to_orm` methods on the ORM classes** -- rejected
  outright; see #3.
- **Raising a `NotFoundError` from `get()`** instead of returning `None`
  -- rejected; see #4.
- **A precise add/remove/reorder diff for `answer_ids`**, mirroring
  `status_history`'s approach -- rejected as unnecessary complexity at
  this project's scale; see #5.
- **Letting `IntegrityError` propagate untranslated** -- rejected, since
  it would require the application layer to import `sqlalchemy.exc`,
  violating the dependency rule.

## Consequences

**Positive:**
- Every repository is swappable behind its `Protocol` interface without
  any implementation needing to know about the others.
- Mapping logic for all six aggregates is unit-testable without a
  database; the trickiest logic (`Application`'s status history) has
  dedicated coverage for exactly the append-only guarantee it relies on.
- The `answer_associations` flush requirement is now documented in three
  places (this ADR, the mapper's docstring, and an inline comment at the
  actual `session.flush()` call) specifically so it survives a future
  "simplification" that removes it without understanding why it's there.

**Trade-offs:**
- `Application`'s save logic is split across two files (the mapper
  handles most fields; the repository handles answer associations),
  which is less tidy than having all mapping logic in one place. This
  is a deliberate consequence of #3 combined with the flush requirement
  in #5, not an oversight -- documented at both ends so the split is
  discoverable, not surprising.
- Full delete-and-recreate for `answer_ids` means slightly more database
  churn per save than a precise diff would produce. Irrelevant at this
  project's actual scale (single user, SQLite, infrequent saves).

## References

- ADR-0001 -- Clean Architecture; the dependency rule #6 protects.
- ADR-0002/0003 -- `Application`'s progressive lifecycle and
  `transition_to()`'s append-only guarantee, which #5's `status_history`
  handling relies on.
- ADR-0004 -- the eager-loading policy #7 follows, and the `RESTRICT`
  foreign keys #6 translates.
