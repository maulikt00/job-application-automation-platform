# ADR-0007: CLI Composition Root, Centralized Error Handling, and Raw UUID Arguments

## Status

Accepted — 2026-07-09

## Context

Milestone 7 built the first real front door into the system --
`presentation/cli/`, wired to every use case from Milestone 6. Building
it required resolving several concrete questions `ARCHITECTURE.md`'s
Composition Root section describes in principle but hadn't been applied
in practice yet: where object construction happens, how errors surface
to a user typing commands, how command-line ID arguments are validated,
and how the schema gets created for a fresh checkout.

A real gap also surfaced during this milestone's own end-to-end smoke
test (not caught by writing code, only by running it): `Application`
Milestone 2's decision to allow `resume_id` to be set freely after
Draft creation, and ADR-0006's decision to drop `SelectResumeUseCase` on
the assumption that "whatever flow attaches it" would cover this,
concretely required a use case that was never written. Without one,
`SubmitApplicationUseCase`'s "a resume must be attached" precondition
could never be satisfied by any code path that actually existed.

## Decisions

### 1. `argparse`, not a third-party CLI framework

Stdlib, zero new dependency. Subcommand structure (`jaap <entity>
<action>`) uses nested `add_subparsers()` calls, one level per noun
(`profile`, `resume`, `application`) and one level per verb (`create`,
`add`, `start`, `attach-resume`, `submit`, `list`).

### 2. Raw UUID strings as CLI arguments, validated and converted at the boundary

ID arguments (`--profile-id`, `--resume-id`, etc.) are typed
`uuid.UUID` in argparse (`type=uuid.UUID`), so a malformed UUID string
is rejected by argparse itself before any command handler runs, with
argparse's own clean usage-error message. Handlers then wrap the
resulting `uuid.UUID` in the appropriate strongly-typed domain ID
(`ProfileId(args.profile_id)`, etc.) before calling a use case -- this
is the CLI's translation boundary between "a string the user typed" and
"a type the domain layer understands," matching the same boundary
`SqliteXRepository` classes hold for the database layer.

No lookup-by-label exists yet (e.g. `--profile "Maulik Patel"` instead
of a UUID) -- deferred as a usability improvement, not a correctness
requirement, since every command already prints the UUID it just
created for the next command to reuse.

### 3. Exception translation is centralized in `main()`, not duplicated per command

A single `try`/`except (UseCaseError, DomainError)` wraps the one
dispatch call (`args.handler(args, context)`) inside `main()`. No
command handler contains its own `try`/`except`. This keeps
user-facing error formatting and the exit-code convention (1 for a
caught business-rule/domain error, argparse's own 2 for a malformed
argument, 0 for success) defined in exactly one place, and keeps every
`_handle_*` function pure orchestration: call a use case, print a
result, return 0. An exception type not explicitly caught here (a
genuine bug, not a business-rule violation) is deliberately left to
propagate as a real traceback -- swallowing unexpected errors silently
would be worse than a stack trace during this project's current
single-user, development-stage usage.

### 4. `main.py` is the composition root; no global repository/use-case state

`build_context()` constructs `Settings`, the engine, the session
factory, and all four repositories fresh on every call, bundled into a
`Context` dataclass passed explicitly to every command handler. Nothing
is held at module scope. This mirrors how `Settings` and `configure_logging()`
were already designed (Milestone 3): constructed once, injected
everywhere, never reached for as an implicit global.

### 5. `Base.metadata.create_all()` remains the schema-creation approach for now, explicitly scoped as single-user/development-only

Documented directly in `build_context()`'s docstring: `create_all()`
only creates missing tables -- it never alters an existing table's
columns, indexes, or constraints. This is fine for the project's
current stage (single developer, no deployed schema to migrate), but is
explicitly NOT a migration strategy. A real tool (e.g. Alembic) or an
explicit migration script will be needed once a schema change needs to
alter something that already exists in a database someone is actually
using -- likely around Phase 5's multi-user/deployment work.

### 6. `AttachResumeToApplicationUseCase` resolves ADR-0006's deferred `SelectResumeUseCase` decision

Discovered as a genuine gap while running Milestone 7's own end-to-end
smoke test, not while writing code: `StartApplicationUseCase` creates a
Draft with `resume_id=None`, and nothing in Milestones 1-6 provided any
way to set it afterward, making `SubmitApplicationUseCase`'s readiness
check permanently unsatisfiable. `AttachResumeToApplicationUseCase`
follows the same shape as `StartApplicationUseCase`: verify both
referenced aggregates exist (`Application` via
`ApplicationNotFoundError`, `Resume` via a new `ResumeNotFoundError`),
then set the field and save. This is the concrete "whatever flow
attaches it" ADR-0006 pointed to.

## Alternatives Considered

- **`typer`** for the CLI framework. Rejected by direct choice --
  stdlib-only was preferred over the nicer UX/one dependency trade-off.
- **A `CreateJobPostingUseCase` + `jaap posting create` command**, so the
  demo flow needed no external script. Rejected by direct choice: job
  posting creation belongs to Phase 4's connectors, and a CLI command for
  it now would need to be reconciled with (or thrown away for) that
  future design. `scripts/seed_job_posting.py` fills the gap for local
  development without pretending it's a permanent CLI feature.
- **Per-command `try`/`except` blocks** instead of centralizing in
  `main()`. Rejected; see decision #3.
- **An explicit `jaap db init` command** instead of unconditional
  `create_all()` on every invocation. Rejected for now as unnecessary
  ceremony for a single-user CLI; see decision #5.

## Consequences

**Positive:**
- Every command handler is a few lines of pure orchestration, unit
  tested directly with a `Context` built from Milestone 6's fake
  repositories -- no database, no subprocess.
- One true end-to-end test (`test_main.py`) exercises the real `main()`
  entry point, real argument parsing, and a real temp-file SQLite
  database, proving the full wiring actually works end to end -- caught
  the `AttachResumeToApplicationUseCase` gap precisely because it does.
- The composition root's scope is unambiguous: exactly one file imports
  both repository interfaces and their concrete implementations
  together.

**Trade-offs:**
- `create_all()`'s single-user/development-only scope (decision #5)
  means a future schema change to an existing table needs new tooling
  before it can ship safely -- a known, deliberately deferred cost, not
  an oversight.
- No lookup-by-label for IDs (decision #2) means every multi-command
  workflow currently requires copy-pasting UUIDs between commands --
  acceptable for a development-stage CLI, worth revisiting once real
  day-to-day use makes the friction concrete.

## References

- ADR-0001 -- the Composition Root concept this milestone implements
  concretely for the first time.
- ADR-0002/0003 -- `Application.resume_id`'s lack of a domain invariant,
  which is what makes `AttachResumeToApplicationUseCase`'s existence a
  business-rule/use-case concern, not a domain-model one.
- ADR-0005/0006 -- the repository `Protocol` interfaces and fake
  repositories this milestone's tests depend on.
