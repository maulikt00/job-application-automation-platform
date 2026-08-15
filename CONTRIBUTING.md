# Contributing to JAAP

JAAP is currently developed milestone-by-milestone, in the open, with a
strong emphasis on clean architecture, testability, and clear history. This
guide applies whether you're the sole contributor today or an outside
contributor later.

## Workflow

Development is trunk-based with short-lived feature branches:

1. Pick up one milestone (see [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md)) or
   one GitHub Issue.
2. Create a branch from `main` (see naming convention below).
3. Make small, reviewable commits (see commit convention below).
4. Open a pull request into `main`, even if you're the only reviewer.
5. Merge only after the milestone's stated tests/docs are in place.

Only one milestone is worked on at a time. Do not start work on a future
milestone's code while an earlier one is still open for review.

## Branch Naming

```
<type>/<short-description>
```

Where `<type>` matches the Conventional Commits type of the primary change:

- `feat/` — new functionality (e.g. `feat/resume-repository`)
- `fix/` — bug fixes (e.g. `fix/sqlite-migration-order`)
- `docs/` — documentation only (e.g. `docs/architecture-update`)
- `refactor/` — restructuring without behavior change
- `test/` — adding or improving tests only
- `chore/` — tooling, dependency bumps, scaffolding

The type prefix should describe what the branch's diff actually *is*, not
what phase of the project it belongs to — this keeps `git log --all` and
branch lists legible at a glance.

## Commit Messages — Conventional Commits

```
<type>(<scope>): <short summary>
```

Examples:

```
feat(profile): create user profile model
fix(database): resolve migration issue
docs(readme): update installation guide
refactor(browser): simplify page manager
test(forms): add autofill unit tests
chore(deps): bump SQLAlchemy to 2.0.31
```

Guidelines:

- Keep the summary under ~72 characters, imperative mood ("add", not
  "added"/"adds").
- Scope is usually the module or layer touched (`profile`, `database`,
  `ai`, `browser`, `connectors`, `cli`).
- One logical change per commit. If you're using "and" to describe a
  commit, it's probably two commits.
- Breaking changes get a `!` after the type/scope
  (`feat(ai)!: change AIProvider.generate_text signature`) and a
  `BREAKING CHANGE:` footer explaining the impact and migration.

## Pull Requests

- PR description should state: what milestone/issue this addresses, what
  layer(s) it touches, and how it was tested.
- A PR should correspond to one milestone (or a clearly-scoped slice of
  one) — not a batch of unrelated changes.
- All new code must include tests per the testing guidelines below.
- Update `ARCHITECTURE.md`, `README.md`, `PROJECT_ROADMAP.md`, and/or
  `CHANGELOG.md` in the same PR if the change affects them (see each
  file's own guidance).

## Code Standards

- Python 3.12+, full type hints on all public functions/methods.
- Pydantic models for data crossing a layer boundary; dataclasses are fine
  for simple internal structures.
- Use `pathlib`, not `os.path`.
- Use the standard `logging` module — no `print()` in library code.
- Docstrings on every module, class, and public function explaining
  intent, not just restating the signature.
- Favor several small functions/modules over one large one. If a function
  is hard to name concisely, it's probably doing more than one thing.
- Favor composition over inheritance (see [ARCHITECTURE.md](ARCHITECTURE.md)).
- Dependencies are injected (constructor injection), not imported as
  global singletons or constructed deep inside business logic.
- No giant classes, no duplicate logic, no premature optimization.

## Testing

- Every new module gets corresponding tests in `tests/unit/` (mirroring
  the `src/jaap/` structure) or `tests/integration/` as appropriate.
- Unit tests must not require a real database, browser, or network call —
  use fakes/mocks for every injected interface.
- Integration tests (real SQLite, real headless Playwright against
  fixture HTML) live separately and are allowed to be slower.
- Tests must be deterministic — no reliance on real network calls, real
  AI provider responses, or system time without freezing/mocking it.
- Run the full suite with `pytest` before opening a PR.

## Documentation Expectations

Documentation is not an afterthought — it's part of "done":

- **README.md** — update when functionality visible to a user changes.
- **ARCHITECTURE.md** — update when a layer, interface, or cross-cutting
  concern changes.
- **PROJECT_ROADMAP.md** — update milestone status as work progresses.
- **CHANGELOG.md** — add an entry under `Unreleased` for any
  user-facing change (see file for format).
- **docs/adr/** — add a new ADR for any significant, hard-to-reverse
  design decision (new dependency, new architectural pattern, a rejected
  alternative worth remembering).

## Questions or Unclear Requirements

If a requirement is ambiguous, raise it (as a comment, issue, or in
conversation) before writing code rather than guessing. This project
prioritizes deliberate design over fast-but-wrong implementation.
