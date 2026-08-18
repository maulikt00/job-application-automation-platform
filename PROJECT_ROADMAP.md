# Project Roadmap

This roadmap breaks each phase into small, single-purpose milestones. Per
project convention, only one milestone is worked on at a time, each ending
with a review before the next begins. Checkboxes are updated as milestones
complete; this file is updated whenever scope changes.

Status legend: ⬜ not started · 🟨 in progress · ✅ done

---

## Phase 1 — Core Domain & Data

**Goal:** a working, tested, persistent core: profiles, resumes, cover
letter templates, reusable answers, and application history, usable from a
simple CLI, with no browser or AI dependency yet.

- ✅ **M1 — Architecture & repository scaffolding** (this milestone):
  Clean Architecture design, ADR-0001, directory structure, project docs.
- ✅ **M2 — Domain models**: `Profile`, `Resume`, `CoverLetterTemplate`,
  `Answer`, `JobPosting`, `Application`, `ApplicationStatus` as Pydantic
  models, with unit tests and no persistence yet. Includes a
  post-implementation refinement (ADR-0003): an `Entity` base class for
  identity-based equality/hashing, a mutation strategy split between
  `validate_assignment` and a guarded `transition_to()`, and an open,
  connector-extensible `JobPosting.platform`/`external_id`/
  `platform_metadata`.
- ✅ **M3 — Configuration & logging**: Pydantic `Settings`, `.env` loading,
  centralized logging configuration. Console output is human-readable
  text; a rotating file handler writes structured JSON alongside it.
- ✅ **M4 — Database layer**: SQLAlchemy ORM models + SQLite session
  management, mapped to domain models. Includes a `UTCDateTime` custom
  type (SQLite has no native timezone-aware datetime type) and a partial
  unique index on `(platform, external_id)` for `JobPosting` deduplication
  -- both resolving risks flagged during the Milestone 2 architectural
  review. `PRAGMA foreign_keys=ON` is enforced automatically per
  connection so cascade deletes actually work under SQLite. A follow-up
  lead-engineer review (ADR-0004) added eager loading for
  `status_events`/`answer_associations`, replaced the plain
  `Application`↔`Answer` join table with an ordered association object,
  and switched `resume_id`/`cover_letter_template_id`/`answer_id`
  foreign keys from CASCADE/SET NULL to RESTRICT to prevent silent
  historical data loss.
- ✅ **M5 — Repository interfaces & SQLite implementations**: all six
  repository interfaces (`Protocol`-based, ADR-0005) plus their SQLite
  implementations, with a dedicated mapper module per aggregate for
  domain/ORM translation. `Application`'s save reconciles status history
  (append-only) and answer associations (full delete-and-recreate, with
  the mid-flush requirement that turned up during development) via two
  different strategies -- see ADR-0005. Database-level `RESTRICT`
  violations (ADR-0004) are translated into a new domain-level
  `ReferentialIntegrityError` at the repository boundary.
- ⬜ **M6 — Core use cases**: `CreateProfileUseCase`,
  `AddResumeUseCase`, `SelectResumeUseCase`,
  `SaveCoverLetterTemplateUseCase`, `RecordApplicationUseCase`, each with
  unit tests using fake repositories.
- ⬜ **M7 — CLI (Phase 1 front door)**: minimal CLI commands to exercise
  the above use cases end-to-end (create profile, add resume, list
  applications).

## Phase 2 — Browser Automation

**Goal:** detect and fill job application forms in a real browser via
Playwright, always stopping short of final submission for human review.

- ⬜ **M8 — Playwright engine wrapper**: `BrowserAutomationEngine`
  interface + Playwright-backed implementation (launch, navigate, close).
- ⬜ **M9 — Form field detector**: inspect a loaded page and produce a
  structured list of detected fields (name, type, label guess).
- ⬜ **M10 — Autofill engine**: given structured profile/resume/answer
  data and detected fields, fill matching fields; unmatched fields
  surfaced to the user rather than guessed.
- ⬜ **M11 — Resume upload handling**: attach the selected resume file to
  a detected file-upload field.
- ⬜ **M12 — Human review gate**: an explicit "review and confirm" step
  in the use case/CLI flow before any submit button is engaged; JAAP never
  clicks submit automatically at this stage.

## Phase 3 — AI Integration

**Goal:** add AI assistance for content generation and decision support,
without AI ever touching browser automation.

- ⬜ **M13 — `AIProvider` interface**: abstract contract
  (`generate_text`, and related methods) in `application/interfaces/`.
- ⬜ **M14 — `ClaudeProvider`**: first concrete implementation.
- ⬜ **M15 — `OllamaProvider`**: second concrete implementation, proving
  the interface generalizes to a local model with no use-case changes.
- ⬜ **M16 — AI-generated cover letters**: `GenerateCoverLetterUseCase`
  composing profile + job posting + template into a prompt, with human
  edit/approval before saving.
- ⬜ **M17 — AI-generated application answers**: reusable-answer
  suggestions for free-text application questions, again with review.
- ⬜ **M18 — Resume recommendation**: suggest which stored resume best
  fits a given job posting.

## Phase 4 — Website Connectors

**Goal:** support real job platforms without modifying existing, working
code — adding a platform means adding a connector.

- ⬜ **M19 — `WebsiteConnector` interface**: abstract contract
  (detect current platform, locate apply flow, map fields) in
  `application/interfaces/`.
- ⬜ **M20 — `GreenhouseConnector`**
- ⬜ **M21 — `LeverConnector`**
- ⬜ **M22 — `WorkdayConnector`**
- ⬜ **M23 — End-to-end application flow**: profile + resume + AI cover
  letter + connector + human review, exercised against a real (test)
  posting on each supported platform.

## Phase 5 — Platform & Scale (Future)

Not yet broken into milestones; scope will be defined once Phase 4 is
complete and real usage informs priorities.

- ⬜ Dashboard (likely NiceGUI or FastAPI + simple frontend)
- ⬜ Job analytics (application funnel, response rates)
- ⬜ Resume scoring against job descriptions
- ⬜ AI job ranking (surfacing best-fit postings)
- ⬜ Email notifications (status changes, follow-up reminders)
- ⬜ Docker packaging
- ⬜ Cloud deployment
- ⬜ Plugin system (third-party connectors/providers without forking)
- ⬜ REST API (FastAPI), so the CLI/dashboard/future clients share one backend
- ⬜ Multi-user accounts

---

## How This File Is Maintained

- Checkboxes flip to 🟨 when a milestone starts and ✅ when it's merged to
  `main`.
- New milestones are only added within the phase currently being worked on
  plus the immediate next phase's placeholder list — we don't pre-plan
  Phase 4 milestones in detail while still in Phase 1.
- Significant scope changes get a short note here and, if they reflect a
  real design decision, a new ADR in `docs/adr/`.
