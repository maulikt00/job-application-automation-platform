# Changelog

All notable changes to this project are documented here. Format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows milestone-based versioning until the first tagged release, after
which it will move to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `docs/adr/0011-resume-upload.md`: the design decisions behind
  Milestone 11, including the finding that Playwright's
  `set_input_files()` fails slowly (30s) and misleadingly for a missing
  file, and why file-upload fields require an explicit resume synonym
  to match rather than matching any `type="file"` input.
- `BrowserAutomationEngine.upload_file(selector, file_path)`: validates
  the file exists before calling into Playwright, raising
  `BrowserAutomationError` immediately (not after a 30-second timeout)
  if it doesn't.
- `ExactFieldMatcher` now accepts an optional `resume` parameter
  (`FieldMatcher.match()`'s signature changed accordingly) and matches
  file-upload fields only via an explicit resume synonym
  (`resume`, `cv`, `resume-upload`, etc.) on the field's name/label --
  never unconditionally by `field_type == "file"`, since a real form can
  have file uploads for a cover letter, portfolio, or transcript too.
- `AutofillApplicationUseCase` gained `ResumeRepository` and an optional
  `resume_id` parameter on `execute()`, resolving the deferral from
  ADR-0010's decision #8. Verified end-to-end that a resume never gets
  uploaded into an unrelated file input even when both a resume field
  and a cover-letter field are present on the same page.
- `docs/adr/0010-autofill-engine.md`: the design decisions behind
  Milestone 10, including conservative/exact-only matching, the
  `application/services/` package rationale, and the finding that
  Playwright's default "element not found" timeout (30s) is too slow for
  tests -- fast, reliable failure triggers used instead.
- `BrowserAutomationEngine.fill()`, `.check()`, `.select_option()`: the
  three generic action primitives an autofill engine needs.
- `BrowserAutomationError` (`domain/exceptions.py`): every operational
  `PlaywrightBrowserEngine` method now translates Playwright's own
  exceptions into this, via exception chaining, resolving the deferral
  from ADR-0008/0009.
- `DetectedField.selector`: `#<id>` preferred, `[name="..."]` fallback,
  `None` if neither exists. Fields with no selector are never matched.
- `FieldMatcher` Protocol (`application/interfaces/field_matcher.py`)
  and `ExactFieldMatcher` (`application/services/field_matcher.py`, a
  new package for pure-logic implementations of application-layer
  interfaces with no external dependency) -- conservative, exact-match
  matching only (structural HTML type signals, a small explicit synonym
  set, exact label-to-`Answer.question_key` matching), never fuzzy.
- `AutofillApplicationUseCase`: orchestrates detection → matching →
  filling for a given Profile. Never submits. Verified end-to-end
  against real Chromium, reading back actual DOM state after autofill.
- `utils/slugify.py`: extracted from `Answer.question_key`'s
  normalization so `ExactFieldMatcher` uses the identical rule, rather
  than a separately-maintained regex that could silently drift.
- `docs/adr/0009-form-field-detector.md`: the design decisions behind
  Milestone 9, including a mid-design correction to ADR-0008's original
  plan (form detection composed separately, not added as a new
  `BrowserAutomationEngine` method) and precise findings about what
  `evaluate()`'s JSON round-trip guard actually catches.
- `BrowserAutomationEngine.evaluate(script) -> Any`: the one new generic
  primitive added this milestone, running JavaScript against the live
  rendered page. Enforces a JSON-compatible result
  (`allow_nan=False` specifically, since Python's `json.dumps()` permits
  `NaN`/`Infinity` by default).
- `FormFieldDetector` Protocol interface + `DetectedField` model
  (`application/interfaces/form_field_detector.py`) and
  `PlaywrightFormFieldDetector` (`infrastructure/browser/form_field_detector.py`),
  composed with `BrowserAutomationEngine` via constructor injection.
  Tested against a real constructed HTML page in real Chromium, covering
  every field type, exclusions (hidden, disabled, button-like inputs),
  and all label-priority levels (label-for, aria-label, placeholder, none).
- `docs/adr/0008-browser-automation-engine.md`: the design decisions
  behind Milestone 8 (Protocol interface, sync vs async Playwright API,
  never exposing raw Playwright objects, deferred exception translation,
  and the version-pin discovery below).
- `BrowserAutomationEngine` Protocol interface
  (`application/interfaces/browser_engine.py`) and its Playwright-backed
  implementation (`infrastructure/browser/playwright_engine.py`):
  `launch()`, `navigate()`, `screenshot()`, `close()`, context-manager
  support. Tested against a real headless Chromium instance, not mocks.
- `Settings.headless` (env var `JAAP_HEADLESS`, default `true`).
- `docs/adr/0007-cli-composition-root-and-error-handling.md`: the design
  decisions behind Milestone 7 (argparse choice, UUID validation at the
  CLI boundary, centralized exception translation, the composition root,
  and `create_all()`'s explicitly single-user/development scope).
- `presentation/cli/main.py`: the CLI composition root and entry point
  (`python -m jaap.presentation.cli.main ...`), plus commands for
  `profile create`, `resume add`, `application start`/`attach-resume`/
  `submit`/`list` in `presentation/cli/commands/`.
- `AttachResumeToApplicationUseCase`: resolves ADR-0006's deferred
  `SelectResumeUseCase` decision -- discovered as a real gap during
  Milestone 7's own end-to-end smoke test (`StartApplicationUseCase`
  created Drafts with no way to ever attach a resume before submission).
  Adds `ResumeNotFoundError` to `application/exceptions.py`.
- `scripts/seed_job_posting.py`: a standalone script for creating
  `JobPosting` rows directly, since job posting creation is deliberately
  left to Phase 4's connectors rather than a CLI command.
- `docs/adr/0006-core-use-cases-and-exception-placement.md`: the design
  decisions behind Milestone 6 (the finalized use case set replacing the
  original `RecordApplicationUseCase` placeholder, exception placement,
  deferred DTOs, and `StartApplicationUseCase`'s validation scope).
- Six use cases in `application/use_cases/`: `CreateProfileUseCase`,
  `AddResumeUseCase`, `SaveCoverLetterTemplateUseCase`,
  `SaveAnswerUseCase`, `StartApplicationUseCase`,
  `SubmitApplicationUseCase`. Each is constructor-injected with only the
  repository `Protocol` interfaces it needs.
- `application/exceptions.py`: `UseCaseError` (base),
  `ProfileNotFoundError`, `JobPostingNotFoundError`,
  `ApplicationNotFoundError`, `ApplicationNotReadyForSubmissionError` --
  business-rule violations, kept distinct from `domain/exceptions.py`'s
  invariant violations per ADR-0002.
- `tests/unit/application/use_cases/fakes.py`: in-memory fake
  repositories satisfying every repository `Protocol`, used to unit-test
  all six use cases with no database involved.
- `docs/adr/0005-repository-interfaces-and-mapping-strategy.md`: the
  design decisions behind Milestone 5 (Protocol vs ABC, mapper module
  placement, `get()` semantics, Application's two-strategy save, and
  exception translation).
- Six repository `Protocol` interfaces in
  `application/interfaces/repositories.py`: `ProfileRepository`,
  `ResumeRepository`, `CoverLetterTemplateRepository`,
  `AnswerRepository`, `JobPostingRepository`, `ApplicationRepository`.
- Six SQLite-backed repository implementations in
  `infrastructure/database/repositories/`, each verified to structurally
  satisfy its Protocol interface via mypy.
- `infrastructure/database/mappers/`: one domain/ORM translation module
  per aggregate, independently unit-tested without a database.
- `ReferentialIntegrityError` in `domain/exceptions.py`: repositories
  translate `RESTRICT`-triggered `IntegrityError`s (ADR-0004) into this
  domain-level exception, so the application layer never needs to import
  `sqlalchemy.exc`.
- `docs/adr/0004-session-loading-ordering-and-restrictive-deletes.md`: a
  lead-engineer review of the Milestone 4 database layer, addressing four
  issues before Milestone 5 builds repositories against it (see Changed,
  below, for the resulting code changes).
- `ApplicationAnswerORM`, an association object for `Application` <->
  `Answer` carrying a `position` column, replacing a plain many-to-many
  join table -- preserves `Application.answer_ids`' order across a
  save/load round trip, which a plain `secondary=` table cannot do.
- `infrastructure/database/`: SQLAlchemy ORM models for all six aggregate
  roots plus `ApplicationStatusEventORM` (child table) and an
  `application_answers` many-to-many join table, mapped separately from
  the Pydantic domain models (repositories, Milestone 5, are the
  translation boundary between the two).
- `UTCDateTime`, a custom SQLAlchemy type that requires timezone-aware
  datetimes on write and re-attaches UTC on read, since SQLite has no
  native timezone-aware datetime type -- resolves a risk flagged during
  the Milestone 2 architectural review.
- A partial unique index on `JobPosting(platform, external_id)` (only
  enforced when `external_id IS NOT NULL`), giving connectors a
  database-enforced deduplication key instead of relying on `url` alone
  -- resolves another risk flagged in that same review.
- `create_engine_from_settings()`, `create_session_factory()`, and
  `session_scope()` in `infrastructure/database/session.py`. SQLite
  foreign key enforcement (`PRAGMA foreign_keys=ON`) is wired
  automatically per connection, since SQLite ignores `ON DELETE
  CASCADE`/`SET NULL` without it.
- `infrastructure/config/settings.py`: a single, validated `Settings`
  object (pydantic-settings) loaded from environment variables/`.env`,
  covering environment, database URL, log level/directory, and AI
  provider config (Anthropic API key, Ollama host). Constructible either
  via env var aliases or plain Python attribute names
  (`populate_by_name=True`).
- `infrastructure/config/logging_config.py`: `configure_logging()`, setting
  up the root logger once with a human-readable console handler and a
  rotating JSON file handler (5 MB per file, 3 backups). Idempotent --
  safe to call more than once without stacking duplicate handlers.
- Domain models for all six aggregate roots: `Profile`, `Resume`,
  `CoverLetterTemplate`, `Answer`, `JobPosting`, `Application` (plus the
  `ApplicationStatus` enum and `ApplicationStatusEvent` value object),
  each with unit tests. No persistence yet -- pure domain layer.
- `Application.transition_to()`, a state-machine method enforcing
  structurally valid status transitions; invalid transitions raise
  `InvalidStatusTransitionError`.
- `domain/exceptions.py` with `DomainError` (base) and
  `InvalidStatusTransitionError`.
- `Entity` base class (`domain/models/entity.py`) giving all aggregate
  roots identity-based equality and hashing (by type + id), instead of
  Pydantic's default field-by-field equality.
- A mutation guard on `Application.current_status`/`status_history`:
  direct assignment raises `DomainError`; `transition_to()` is the only
  sanctioned way to change status. `Profile`, `Resume`,
  `CoverLetterTemplate`, `Answer`, and `JobPosting` gained
  `validate_assignment=True`, so their field validators re-run on any
  post-construction reassignment, not just at construction.
- `JobPosting.platform` changed from a closed `Enum` to an open, normalized
  string (with `JobPlatform` retained as suggested, non-exhaustive
  constants), plus new `external_id` and `platform_metadata` fields, so
  future job-site connectors (including LinkedIn) can be added without
  modifying this model.
- `docs/adr/0003-entity-identity-and-connector-extensibility.md` and a
  corresponding update to `docs/diagrams/domain-model.md`.
- Initial repository scaffolding: Clean Architecture directory structure
  (`domain/`, `application/`, `infrastructure/`, `presentation/`, `utils/`).
- `ARCHITECTURE.md` describing the layered design and data flow.
- `docs/adr/0001-clean-architecture.md` documenting the decision to use
  Clean Architecture with strict layer boundaries.
- `docs/adr/0002-progressive-application-lifecycle.md` documenting the
  decision to model `Application` as a progressive Draft lifecycle rather
  than requiring all fields at construction.
- `PROJECT_ROADMAP.md` with Phases 1–5 broken into milestones.
- `CONTRIBUTING.md` with branch naming, commit conventions, and testing
  expectations.
- Project metadata: `LICENSE` (MIT), `.gitignore`, `.env.example`,
  `requirements.txt`, `requirements-dev.txt`, `pytest.ini`.

### Fixed

- `tests/unit/application/use_cases/fakes.py`: `FakeBrowserEngine.upload_file`
  now records paths via `.as_posix()` instead of `str()`, matching the
  `resume_mapper.py` fix below. Caught on a real Windows checkout: the
  fake stored `str(file_path)`, which renders with Windows' native
  backslash separator, so a test asserting against a forward-slash
  string failed there while passing on Linux/Mac. The real
  `PlaywrightBrowserEngine.upload_file` correctly uses `str(file_path)`
  for actual OS file access -- only the test double needed to change,
  since it exists purely for platform-independent assertions.
- `requirements.txt`: `playwright` pinned tightly to `==1.56.0`, not a
  version range. A clean-venv check caught `1.62.0` raising "using
  Playwright Sync API inside the asyncio loop" the moment
  `PlaywrightBrowserEngine.launch()` ran, even with no async test
  plugin installed anywhere. `1.56.0` does not exhibit this; root cause
  not fully diagnosed, so pinning tightly rather than routing around it.
  See ADR-0008.
- `resume_mapper.py`: `Resume.file_path` is now stored via `.as_posix()`
  instead of `str()`. `str(Path(...))` renders using the OS's native
  separator (backslashes on Windows), so a path saved from a Windows
  machine failed to parse back correctly as a path on Linux/Mac, and
  vice versa. Caught on a real Windows checkout during Milestone 6
  development; `.as_posix()` normalizes to forward slashes on write
  regardless of OS, and `Path(...)` parses forward slashes correctly on
  read regardless of OS, making storage genuinely cross-platform.

### Changed

- `ApplicationORM.status_events` and the new `.answer_associations` now
  use `lazy="selectin"` (eager loading), removing the most common way to
  hit `DetachedInstanceError` when a repository accesses either
  relationship after its loading session has closed.
- `ApplicationORM.resume_id`, `.cover_letter_template_id`, and
  `ApplicationAnswerORM.answer_id` foreign keys changed from `ON DELETE
  CASCADE`/`SET NULL` to `ON DELETE RESTRICT`: deleting a
  `Resume`/`CoverLetterTemplate`/`Answer` still referenced by an
  `Application` now fails loudly instead of silently erasing or nulling
  the historical record of what was used.
- `requirements.txt`: `pydantic` → `pydantic[email]`, required for
  `Profile.email`'s `EmailStr` validation to work on a clean install.
  Added `pydantic-settings` for `Settings`.
- Relocated `logging_config.py` from `utils/` (its Milestone 1 scaffold
  location) to `infrastructure/config/`: it performs real I/O (creating
  directories, opening file handles) and depends on `Settings`, both
  disqualifying for `utils/` per that package's own dependency-free, no-I/O
  rule.

### Note

- ORM tables include an `updated_at` bookkeeping column not yet present
  on the corresponding domain models. This is deliberate, low-cost
  future-proofing flagged during the Milestone 2 review; Milestone 5's
  repositories decide whether/how to surface it to domain objects.
