# Changelog

All notable changes to this project are documented here. Format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
follows milestone-based versioning until the first tagged release, after
which it will move to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

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

### Changed

- `requirements.txt`: `pydantic` → `pydantic[email]`, required for
  `Profile.email`'s `EmailStr` validation to work on a clean install.
  Added `pydantic-settings` for `Settings`.
- Relocated `logging_config.py` from `utils/` (its Milestone 1 scaffold
  location) to `infrastructure/config/`: it performs real I/O (creating
  directories, opening file handles) and depends on `Settings`, both
  disqualifying for `utils/` per that package's own dependency-free, no-I/O
  rule.
