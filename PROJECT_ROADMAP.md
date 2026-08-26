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
- ✅ **M6 — Core use cases**: `CreateProfileUseCase`, `AddResumeUseCase`,
  `SaveCoverLetterTemplateUseCase`, `SaveAnswerUseCase`,
  `StartApplicationUseCase`, `SubmitApplicationUseCase` -- the last two
  replacing the original placeholder `RecordApplicationUseCase` once
  ADR-0002 worked out the Draft→Submit lifecycle in detail. Each is
  unit-tested with in-memory fake repositories (no database), the payoff
  of Milestone 5's Protocol-based interfaces. Business-rule violations
  (not-found lookups, submission readiness) raise a new
  `application/exceptions.py` hierarchy, kept distinct from
  `domain/exceptions.py`'s invariant violations per ADR-0002.
- ✅ **M7 — CLI (Phase 1 front door)**: `argparse`-based CLI covering
  `profile create`, `resume add`, `application start`/`attach-resume`/
  `submit`/`list`, wired through a composition root in `main.py`
  (ADR-0007). `scripts/seed_job_posting.py` fills the job-posting-creation
  gap deliberately left for Phase 4's connectors. Includes
  `AttachResumeToApplicationUseCase`, added to resolve ADR-0006's
  deferred `SelectResumeUseCase` decision -- a real gap caught by this
  milestone's own end-to-end smoke test, not by writing code.

## Phase 2 — Browser Automation

**Goal:** detect and fill job application forms in a real browser via
Playwright, always stopping short of final submission for human review.

- ✅ **M8 — Playwright engine wrapper**: `BrowserAutomationEngine`
  Protocol interface + Playwright-backed implementation (launch,
  navigate, close, screenshot). Sync API, not async (ADR-0008); tested
  against a real headless Chromium instance, not mocks. Includes a
  tight version pin (`playwright==1.56.0`) after a clean-venv check
  caught a real asyncio-loop-detection regression in a newer release.
- ✅ **M9 — Form field detector**: `FormFieldDetector` Protocol +
  `PlaywrightFormFieldDetector`, composed with `BrowserAutomationEngine`
  via constructor injection rather than a new engine method (a
  mid-design correction to ADR-0008's original plan -- see ADR-0009).
  Uses one new generic engine primitive, `evaluate()`, to run JS against
  the live rendered DOM (catches JS-rendered SPA content a static parser
  would miss). Tested against a real constructed HTML page in real
  Chromium, covering every field type, both exclusion categories, and
  all label-priority levels.
- ✅ **M10 — Autofill engine**: `FieldMatcher` Protocol +
  `ExactFieldMatcher` (conservative/exact matching only, no fuzzy
  scoring), `AutofillApplicationUseCase` orchestrating detection →
  matching → filling. `BrowserAutomationEngine` gained `fill()`/
  `check()`/`select_option()`; Playwright's own exceptions are now
  translated into `BrowserAutomationError` (ADR-0010, resolving the
  deferral from ADR-0008/0009). `DetectedField` gained `selector`;
  fields without one are never matched. Verified end-to-end against a
  real page, reading back actual DOM state after autofill.
- ✅ **M11 — Resume upload handling**: `BrowserAutomationEngine.upload_file()`,
  validated against a real file before calling into Playwright (a
  missing file otherwise fails slowly and misleadingly -- see ADR-0011).
  `ExactFieldMatcher` matches file-upload fields only via an explicit
  resume synonym on the field's name/label, never by `field_type ==
  "file"` alone -- verified end-to-end that a resume never gets
  uploaded into an unrelated file input (e.g. a cover letter field) even
  when one is present on the same page. `AutofillApplicationUseCase`
  gained `ResumeRepository` and an optional `resume_id` parameter,
  resolving the deferral from ADR-0010.
- ✅ **M12 — Human review gate**: `ReviewApplicationUseCase` (composes
  `AutofillApplicationUseCase`, adds a screenshot) and the `jaap
  application review` CLI command -- the first command to touch the
  browser layer. No `click()`/`submit()` capability exists anywhere in
  `BrowserAutomationEngine`, deliberately: this is a structural fact
  making ADR-0001's "never blindly submit" promise verifiable by
  inspection, not just a passive absence (see ADR-0012). Verified fully
  end-to-end against a real local HTTP server and real Chromium. A real,
  previously-unnoticed Protocol/implementation signature mismatch on
  `BrowserAutomationEngine.__exit__` was found and fixed while wiring
  this up. **This completes Phase 2.**

## Pre-Phase-3 Cleanup

A lead-engineer-style review after Phase 2's completion identified four
items worth resolving before Phase 3 begins, rather than letting them
compound further. All four are complete:

- ✅ **Application content snapshot** ([ADR-0013](docs/adr/0013-submitted-content-snapshot.md)):
  `SubmittedContentSnapshot`/`SubmittedAnswer`, durable immutable
  evidence of what was actually submitted, set exactly once at the
  `DRAFT -> SUBMITTED` transition. Resolves a gap flagged as far back as
  the Milestone 2 review and formally deferred (twice) since. Directly
  unblocks Milestone 16's AI-generated, possibly one-off cover letters,
  which now have a concrete place to land even when never saved as a
  reusable `CoverLetterTemplate` (via `SubmitApplicationUseCase`'s new
  `cover_letter_text_override` parameter).
- ✅ **`ARCHITECTURE.md` brought current**: rewritten to accurately
  describe the architecture through this cleanup pass -- `application/services/`,
  `FormFieldDetector`/`FieldMatcher`, the CLI's `Context`/composition-root
  pattern, and a corrected Testing Strategy section (all tests actually
  live under `tests/unit/`; `tests/integration/` was an unused scaffold).
  Explicitly distinguishes built functionality from Phase 3/4/5 planned work.
- ✅ **Architecture boundary tests** (`tests/unit/architecture/test_dependency_boundaries.py`):
  AST-based, dependency-only (no third-party architecture-linting
  library) enforcement of the dependency rule and the AI/browser
  separation. Verified to actually catch a real violation (tested by
  deliberately introducing one, confirming failure, then removing it)
  before being relied on as a safety net -- this makes the "AI never
  touches browser automation" rule a continuously-checked fact rather
  than manual discipline alone, which matters starting now that
  Phase 3 is about to populate `infrastructure/ai/` for the first time.
- ✅ **`SECURITY.md`**: practical, current-state guidance (API keys,
  `.env`/`.gitignore`, Ollama, browser session data, logging, sensitive
  application data, vulnerability reporting) -- including an honest,
  undehedged note that `Settings.anthropic_api_key` has no secret-scrubbing
  yet (no `SecretStr`, no logging redaction), left as a known limitation
  rather than silently fixed as an unrelated change.

## Phase 3 — AI Integration

**Goal:** add AI assistance for content generation and decision support,
without AI ever touching browser automation.

- ✅ **M13 — `AIProvider` interface**: `Protocol`-based, one generic
  primitive (`generate_text(prompt, *, system_prompt=None) -> str`),
  never one method per feature -- the same lesson ADR-0009 established
  for `BrowserAutomationEngine`, applied here (see ADR-0014). No
  implementation yet (M14/15), no consumer yet (M16-18); deliberately
  minimal testable surface for a milestone that's just an interface.
- ✅ **M14 — `ClaudeProvider`**: first concrete implementation, built
  against the actually-installed `anthropic` SDK (inspected directly,
  not assumed) -- catching two real bugs via mypy along the way (wrong
  "not given" sentinel type; unsafe indexing into a union-typed response
  content list). Pinned tightly (`anthropic==1.0.0`), following ADR-0008's
  lesson. No exception translation yet, mirroring the exact precedent
  set by `BrowserAutomationEngine` (deferred from its own first
  milestone to its first real use-case consumer). See ADR-0015.
- ✅ **M15 — `OllamaProvider`**: second concrete implementation, built
  against the actually-installed `ollama` SDK (inspected directly). Real
  structural differences confirmed the interface generalizes rather than
  just being Claude-shaped: `system_prompt` translates into a
  `{"role": "system", ...}` message (Ollama has no separate `system`
  parameter), `max_tokens` maps to `options.num_predict`, and no API key
  is needed. Pinned tightly (`ollama==0.6.2`). See ADR-0016.

### CLI gap fix: `jaap answer` and `jaap cover-letter` commands

Found while answering a practical question about Workday-based
application forms, not part of any milestone's original scope:
`SaveAnswerUseCase` and `SaveCoverLetterTemplateUseCase` have existed
since Milestone 6, but neither was ever exposed through the CLI --
`jaap answer save/list` and `jaap cover-letter save/list` close that gap.
Directly relevant to autofill in practice: `ExactFieldMatcher` (Milestone
10) can only match a detected field to a saved `Answer` if one already
exists with a matching `question_key`, and there was previously no way
to create one without calling the use case directly in Python.

- ✅ **M16 — AI-generated cover letters**: `GenerateCoverLetterUseCase`,
  the first real use-case consumer of `AIProvider` -- resolving the
  exception translation deferred three times (M13-15). `ClaudeProvider`/
  `OllamaProvider` retroactively updated to translate their SDK's
  exceptions (a real asymmetry found: Anthropic's SDK shares one common
  base, Ollama's does not) into a shared `AIProviderError`. `jaap
  cover-letter generate` (with `--save-as`) and a second real gap fixed
  along the way (`jaap application submit --cover-letter-text-override`,
  previously missing despite the use case supporting it since ADR-0013).
  Verified genuinely end-to-end through the real CLI and database. See
  ADR-0017.
- ✅ **M17 — AI-generated application answers**: `GenerateAnswerUseCase`,
  deliberately taking no `job_posting_id` (unlike Milestone 16's cover
  letters) so generated answers stay genuinely safe to save and reuse
  across different companies -- resolving a real tension between
  "reusable answer" and "tailored to one employer" before it became a
  bug. Existing saved `Answer`s are passed as context for tone
  consistency. `jaap answer generate --save-as <question>` mirrors
  `cover-letter generate`'s shape; passing the same text for both
  `--question` and `--save-as` produces a `question_key` verified to
  exactly match what `ExactFieldMatcher` computes later. See ADR-0018.
- ✅ **M18 — Resume recommendation**: `RecommendResumeUseCase`, the
  third real `AIProvider` consumer. Honestly scoped: compares resume
  *labels* against job title/company only (no resume-text-extraction
  exists in this project), stated in both the code and the AI's own
  system prompt. Zero/one-resume cases never call the AI at all. A
  strict response format (chosen option's number, then reasoning) is
  parsed deterministically, with malformed or out-of-range responses
  raising a clear `ValueError`. `jaap resume recommend` is read-only --
  nothing to save, just a pointer at an existing `Resume` plus
  reasoning. See ADR-0019. **This completes Phase 3.**

## Pre-Phase-4 Cleanup

A lead-engineer-style review after Phase 3's completion identified two
items worth resolving before Phase 4 begins, matching the same
discipline applied before Phase 3. Both complete:

- ✅ **`--provider claude|ollama` on every AI-backed CLI command**:
  `jaap cover-letter generate`, `jaap answer generate`, and `jaap resume
  recommend` each previously hardcoded `ClaudeProvider(context.settings)`
  directly, with no way to actually choose `OllamaProvider` -- despite
  Milestone 15 proving the interface genuinely supports it. Fixed via a
  new shared `presentation/cli/ai_provider_factory.py`, avoiding
  duplicating provider-selection logic across three command modules.
- ✅ **`ARCHITECTURE.md` brought current a second time**: it had gone
  stale again, still describing `AIProvider`/`ClaudeProvider`/
  `OllamaProvider`/the three AI use cases as "not yet defined"/"planned"
  even after all of Phase 3 shipped -- because it was last updated just
  *before* Phase 3 began, not during it. Now documents the real
  `AIProvider` consumer pattern and a second worked data-flow example
  (AI-generated content), alongside the existing autofill/review one.

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
