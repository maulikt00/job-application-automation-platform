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

- ✅ **M19 — `WebsiteConnector` interface**: `platform_name`/`matches()`
  ("detect current platform"), `navigate_to_application_form()`
  ("locate apply flow"), `get_field_detector()` ("map fields" via
  selecting/providing a `FormFieldDetector`, not duplicating it).
  `BrowserAutomationEngine` gained `click()` -- confirmed explicitly
  with the project owner beforehand that a generic navigation click
  primitive is not a reopening of the "no automatic submission"
  boundary (ADR-0001/0012); connectors must never use it on a final
  submit control. No implementation yet (M20-22); deliberately minimal
  testable surface, matching M13's `AIProvider`. See ADR-0020.
- ✅ **M20 — `GreenhouseConnector`**: the first concrete `WebsiteConnector`,
  designed against Greenhouse's own published documentation and a real
  embed-integration script (not assumed) -- two real hosting domains
  found (`boards.greenhouse.io` and `job-boards.greenhouse.io`), plain
  native HTML form fields confirmed (so `get_field_detector()` reuses
  the generic `PlaywrightFormFieldDetector` unchanged), and an honest,
  named scope limitation (embedded iframe integrations are out of
  scope -- `BrowserAutomationEngine` has no cross-frame capability).
  Verified against a real headless Chromium instance for both the
  form-already-present and click-to-reveal-form cases. See ADR-0021.
- ✅ **M21 — `LeverConnector`**: the second concrete `WebsiteConnector`,
  designed against Lever's own published API documentation (not
  assumed) -- two real domains found (`jobs.lever.co`,
  `jobs.eu.lever.co`), and a genuinely different, more reliable
  navigation strategy than Greenhouse's: Lever's own API documents a
  deterministic `hostedUrl` -> `applyUrl` relationship (`/apply`
  appended to the posting URL), so navigation here is pure URL
  manipulation, never a click. Honestly notes a weaker post-navigation
  verification than Greenhouse's (no confirmed Lever field-name
  selector was found, so a generic "any input present" check is used
  instead of guessing one). Same iframe-embedding scope limitation as
  Greenhouse, for the same reason. Verified against real Chromium and a
  real local HTTP server (not `file://` URLs, which can't replicate
  Lever's extension-less directory-style routes). See ADR-0022.
- ✅ **M22 — `WorkdayConnector`**: the third concrete `WebsiteConnector`
  -- the one that directly addresses the custom-widget limitation that
  motivated Phase 4's existence. Two real domain families confirmed
  (`myworkdayjobs.com`, `myworkdaysite.com`), and a `/apply`-suffix URL
  pattern confirmed independently for a *second* platform (Lever being
  the first) -- the path-appending logic was extracted into a shared
  `_url_utils.py` and `LeverConnector` updated to use it too.
  `WorkdayFormFieldDetector` composes the generic detector and adds
  detection of ARIA `role="combobox"` custom dropdowns, with an
  explicitly *lower*, stated confidence level than Greenhouse/Lever's
  confirmed selectors (general ARIA/automation-community knowledge, not
  primary-source Workday documentation). Every detected combobox has
  `selector=None`, guaranteeing (verified directly) it can never be
  automatically matched or filled -- surfaced only as a visible
  "unmatched field." Actually filling a combobox remains real, named,
  unbuilt future work (`AutofillApplicationUseCase` has no dispatch
  branch for it yet). See ADR-0023. **This completes Phase 4's connectors.**
- ✅ **M23 — End-to-end application flow**: found and closed a real gap
  discovered while investigating this milestone's own scope --
  `jaap application review` had never once constructed or consulted a
  `WebsiteConnector` since Milestone 12, meaning all three connectors
  built in M19-22 were correct in isolation but unreachable from real
  usage. Added `infrastructure/connectors/registry.py`
  (`find_connector()`) and wired it into `_handle_review`; a second
  real gap found alongside it (`main.py` never caught the plain
  `ValueError` every connector raises for its own failure mode) was
  fixed too. Verified genuinely twice: once by hand (a temporary
  `/etc/hosts` redirect to a real Greenhouse domain, confirmed against
  the real CLI), then via a permanent, portable automated suite (a real
  `GreenhouseConnector` instance injected via `find_connector`, avoiding
  a fragile DNS dependency in the checked-in tests). A comprehensive
  test ties every piece together: profile + resume + AI-generated cover
  letter (fake provider) + connector-aware review + submission,
  verified against the final `SubmittedContentSnapshot` directly. See
  ADR-0024. **This completes Phase 4.**

## Real-World Validation (v1 declared complete — see ADR-0039)

Following the post-Phase-4 checkpoint review's top recommendation:
before any further Phase 5 work, validate the three connectors against
actual live postings, not just synthetic test pages -- something none
of Milestones 20-23 had done.

**v1 status**: declared complete ([ADR-0039](docs/adr/0039-v1-declared-complete.md))
after the validation record below. One confirmatory round remains
open: the now-complete `Profile` (address/phone/split-name, all added
after Lever's and Greenhouse's own rounds concluded) has not yet been
directly re-verified against either of those two platforms.

- ✅ **Lever, first pass** ([ADR-0025](docs/adr/0025-implicit-label-detection.md)):
  ran `jaap application review` against a real `jobs.lever.co` posting.
  The connector was correctly detected and navigation/autofill worked
  mechanically (`name`/`email` correctly filled), but most fields came
  back with no label at all. Root cause: Lever wraps its inputs
  *inside* `<label>` elements (a standard, valid HTML pattern our
  generic detector never checked for -- it only recognized
  `<label for="id">`). Fixed generically, not as a Lever-specific
  patch. Two unrelated bugs were also caught purely by running this for
  real: a Python `SyntaxWarning` from a non-raw string holding the
  detector's JS, and a `data:` URL character-encoding trap distinct from
  Milestone 20's earlier `#`-fragment one. One real gap remains open and
  named, not silently worked around: a completely unlabeled EEO dropdown
  field (no `label`, no `aria-label`, sibling-only text) would need a
  meaningfully more fragile "nearest sibling text" heuristic -- not
  attempted without more evidence.
- ✅ **Lever, second pass** ([ADR-0026](docs/adr/0026-eeo-exclusion-and-fill-resilience.md)):
  re-ran `application review` after the label fix above and found a
  more serious issue -- an EEO voluntary self-identification
  **signature** field (a legal attestation) got auto-matched and an
  attempt was made to fill it with the applicant's real name, because
  its real label ("Full Name," the standard federal CC-305 form's own
  wording) now correctly resolved and happened to exactly match the
  ordinary full-name synonym set. Fixed structurally: any field named
  `eeo[...]` now always has `selector=None` at detection time (the same
  safety pattern already used for Workday's ARIA-combobox fields,
  ADR-0023), guaranteeing it can never be auto-filled regardless of
  label text. A second, more general problem was fixed alongside it:
  that one field's fill failure (it also happened to be conditionally
  hidden) had aborted the entire review with no report or screenshot at
  all -- `AutofillApplicationUseCase` now demotes a failing field to
  "needs review" and continues, so one bad field can no longer take
  down an otherwise-successful run.
- ✅ **Lever, third pass** ([ADR-0027](docs/adr/0027-visible-text-label-extraction.md)):
  after both fixes above, the review command completed cleanly and every
  `eeo[...]` field showed real, correct labels (confirming ADR-0025/0026
  work on the live site) -- but `resume` and `location` still had badly
  noisy labels, clearly several UI-state status messages
  ("Analyzing resume...", "Success!", "Loading") concatenated together,
  since label extraction read all text inside a label regardless of
  whether it was actually visible right now. Fixed by walking the live
  DOM (not a detached clone, which has no meaningful computed style)
  and filtering to visible text only. **Honestly incomplete**: the
  exact real markup for Lever's resume/location widgets wasn't
  captured, so this fix is verified against a plausible synthetic
  reconstruction of the symptom, not the real widget directly --
  needs one more live re-check to confirm fully.
- ⬜ Lever, re-check resume/location labels against the live posting
- ⬜ Lever, remaining fields (custom application questions)
- ✅ **Greenhouse, first pass** ([ADR-0028](docs/adr/0028-greenhouse-form-polling.md)):
  the first real Greenhouse posting tested (`job-boards.greenhouse.io`)
  failed immediately -- `GreenhouseConnector`'s own "form not found"
  error, even though a screenshot confirmed the form was genuinely on
  the same page with no separate "Apply" step needed, exactly matching
  the connector's original assumption. Root cause: a timing issue, not
  a structural one -- the page's own "load" event fires before the form
  finishes rendering. Fixed by polling for the form's presence (up to
  5 seconds) instead of checking exactly once; verified against a
  direct reproduction of the real failure (a form injected via
  `setTimeout`, no "Apply" element at all).
- ✅ **Greenhouse, second pass** ([ADR-0029](docs/adr/0029-greenhouse-id-only-frontend.md)):
  re-running after ADR-0028's polling fix still failed with the same
  error. A genuine, iterative diagnostic investigation (checking for
  iframes, polling without clicking, clicking and dumping page text,
  then dumping every real field) found the actual cause: this posting's
  frontend uses `id` on every field and sets `name` on NONE of them --
  a second, structurally different Greenhouse implementation from the
  one its own API docs describe (ADR-0021), served under the same
  domain. Fixed by checking both `name` and `id` for the form-presence
  marker. The generic detector and matcher needed no changes at all --
  verified directly, not assumed, including a new test confirming
  `email` still matches via its label even with no `name` attribute
  and a non-`email` `type`. `first_name`/`last_name` correctly remain
  unmatched, per `ExactFieldMatcher`'s own pre-existing, documented
  choice not to split `full_name`.
- ✅ **Greenhouse, third pass** ([ADR-0030](docs/adr/0030-name-fallback-to-id.md)):
  after ADR-0029's fix, the review completed cleanly and `email`
  correctly auto-filled -- but the printed report showed `None` as the
  identifier for every single field (including the matched one), since
  `DetectedField.name` only ever came from `el.name`, never `el.id`, on
  a frontend that sets no `name` attributes at all. Fixed by falling
  back to `el.id`, matching `selectorFor()`'s own existing priority.
  Verified this introduces no new, unintended auto-fill matches for the
  real fields observed before relying on it. Real Greenhouse validation
  now stands on genuinely solid footing: platform detection, timing,
  frontend-variant recognition, and reporting all confirmed against a
  live posting.
- ✅ **Workday, first pass** ([ADR-0031](docs/adr/0031-workday-signin-wall.md)):
  the most significant finding of this whole real-world validation
  effort so far -- not a fixable engineering bug like the Greenhouse/
  Lever findings, but a genuine platform characteristic. Workday's own
  careers site required clicking through an in-page "Start Your
  Application" modal (never a direct URL navigation, contradicting the
  original `/apply`-suffix assumption), and even the most neutral
  option ("Apply Manually") led to a mandatory account-creation/sign-in
  wall before any application field could be reached. **JAAP will not
  automate account creation or sign-in, under any circumstances** --
  this is restated as a firm, permanent boundary, not a gap to engineer
  around. `WorkdayConnector` now attempts the real, confirmed
  modal-click sequence and, if it leads to a sign-in wall, raises a
  clear, honest error explaining that JAAP cannot proceed, rather than
  a confusing generic one. Whether this authentication requirement is
  typical of Workday generally or specific to this one tenant remains
  unknown -- a genuinely open question, not resolved by this fix.
- ✅ **Workday, second pass** ([ADR-0032](docs/adr/0032-workday-click-timing.md)):
  tested a second, independent tenant (NVIDIA's Workday careers site) to
  find out whether the sign-in wall was universal or specific to
  Workday's own site. **Confirmed universal on this second tenant
  too** -- "Apply Manually" led to the identical mandatory
  account-creation step. Also found and fixed a genuinely separate,
  fixable bug along the way: the "Apply Manually" click itself
  sometimes reported a Playwright timeout even though it had actually
  succeeded (confirmed directly: the URL had already changed to the
  expected destination despite the raised exception) -- a real
  navigation-during-click timing quirk, not a sign the click failed.
  Fixed by catching that specific exception and proceeding to check the
  resulting page state regardless, so the correct "requires sign-in"
  message is now reported reliably rather than depending on real-world
  response-time variance.
- ✅ **Workday, third pass** ([ADR-0033](docs/adr/0033-workday-field-presence-false-positive.md)):
  a MORE foundational bug than either prior finding -- the "is a form
  present" check matched *any* input/combobox anywhere on the page,
  and NVIDIA's real posting page had a nav search box, a country
  selector, and OneTrust cookie-consent checkboxes already present
  before any Apply interaction at all, causing the connector to falsely
  report success without ever attempting the Apply flow. Fixed by
  additionally requiring Workday's own `data-automation-id` attribute
  (the same marker already used, with the same honest, unconfirmed
  caveat, for combobox naming in ADR-0023). **Still an open,
  acknowledged gap**: this has never actually been verified against a
  real Workday form's markup, since every real attempt has hit the
  sign-in wall first -- stated honestly, not resolved by this fix.

- ✅ **`--interactive` sign-in pause-and-retry** ([ADR-0034](docs/adr/0034-interactive-signin-pause-retry.md)):
  discussed explicitly before building -- distinguished from JAAP
  automating credentials (still a firm, unchanged boundary) since this
  is a human signing in themselves while JAAP pauses and gets out of
  the way, then resumes. A new `AuthenticationRequiredError` was
  formalized as part of `WebsiteConnector`'s own interface contract
  (not Workday-specific), so any connector can raise it and get this
  behavior for free. `jaap application review --interactive` catches
  it, prints instructions, and loops on `input()` (press Enter to
  retry, `q` to give up) with the browser still open -- opt-in, default
  behavior completely unchanged, requires `JAAP_HEADLESS=false`
  (checked before any browser launches). Persistent session storage
  (removing the recurring sign-in cost entirely) was deliberately
  deferred as its own, separate, future conversation, not folded into
  this feature.
- ✅ **Workday, `--interactive` first real use** ([ADR-0035](docs/adr/0035-workday-signin-field-check-order.md)):
  a genuinely serious finding. The run completed "successfully" with no
  interactive prompt ever appearing -- but the "autofilled" email had
  actually gone into Workday's own **sign-in form**, not the
  application form (confirmed by the other unmatched fields: a
  "Password" field and a bot-honeypot field, both characteristic of a
  login page, not a job application). Root cause: the sign-in form
  itself has fields carrying `data-automation-id` too, and the
  field-presence check ran before the sign-in-text check, so it
  declared success on the wrong page before ever detecting the wall.
  Fixed by checking for a sign-in wall FIRST, every time, not only as a
  fallback when no fields are found. Verified against a full,
  realistic reproduction of the exact scenario (posting -> modal ->
  Apply Manually -> a login page with real fields), which now
  correctly raises `AuthenticationRequiredError` instead of silently
  succeeding.
- ✅ **First real Workday application form reached** ([ADR-0036](docs/adr/0036-first-real-workday-form.md)):
  after the fix above, two runs against NVIDIA's posting -- one hit a
  real, fixable bug (a transient error right after signing in killed
  the whole retry loop instead of allowing another attempt; fixed by
  broadening which exceptions the loop retries on), and the other
  **reached a real, authenticated Workday application form for the
  first time in this project's history**: 16 real fields
  (`legalName--firstName`, `addressLine1`, `candidateIsPreviousWorker`,
  etc.), correctly detected as fields. `Autofilled 0` was reported, but
  this is the same, already-known, deliberate limitation confirmed a
  second time (Greenhouse's own split first/last name fields, ADR-0029)
  -- not a new bug. Whether to build name-splitting is left as an open
  decision, not resolved here.
- ✅ **First/last name splitting** ([ADR-0037](docs/adr/0037-first-last-name-splitting.md)):
  after the split-name limitation was confirmed on two real platforms,
  the project owner made an explicit, informed choice: they will only
  ever enter a simple two-word "First Last" name, and asked for
  splitting to be built for exactly that case. `ExactFieldMatcher` now
  splits `Profile.full_name` -- but ONLY when it has precisely two
  space-separated tokens; a single name, a middle name, or any other
  ambiguity is deliberately left unsplit, and the field stays
  unmatched, same as before. Verified against both real field
  structures that motivated this (Greenhouse's `first_name`/`last_name`,
  matched by name; Workday's `legalName--firstName`/`legalName--lastName`,
  matched by label) and against the safety property directly (a
  single-word and a three-word name both correctly stay unmatched).
- ✅ **Profile address fields** ([ADR-0038](docs/adr/0038-profile-address-fields.md)):
  requested directly after the real Workday form showed `addressLine1`,
  `city`, `postalCode` fields with no equivalent on `Profile` at all.
  Added six new optional fields (`address_line1`, `address_line2`,
  `city`, `state`, `postal_code`, `country`), matching synonym sets in
  `ExactFieldMatcher` verified against the exact real field names/labels
  observed, and a new `UpdateProfileUseCase` + `jaap profile update`
  command (a partial update -- only fields explicitly passed change),
  closing an independently-flagged gap from the post-Phase-4 checkpoint
  review at the same time. A one-off migration script
  (`scripts/migrate_add_profile_address_fields.py`) safely adds the new
  columns to an existing database without losing data, since this
  project has no formal migration system and `create_all()` never
  alters existing tables -- verified directly against a simulated
  pre-migration database, confirming existing data survives and the
  script is safely idempotent.
- ✅ **JAAP v1 declared complete** ([ADR-0039](docs/adr/0039-v1-declared-complete.md)):
  checked against the post-Phase-4 checkpoint review's own stated bar
  and confirmed met, platform by platform. Workday specifically reached
  a real, authenticated application form and correctly autofilled 6 of
  6 fields with a natural home in `Profile` (split name, full address,
  phone). Active, open-ended gap-hunting stops here; the remaining
  known items (Lever's resume label, custom application questions,
  Workday's comboboxes, persistent sessions) are scoped, accepted
  trade-offs, not oversights.
- ✅ **Confirmatory round** (a fresh Lever posting, now-complete
  `Profile`): directly closed the one honest caveat ADR-0039 named.
  `name`/`email`/`phone` all correctly carried over to a second
  platform; every `eeo[...]` field still correctly excluded regardless
  of the fuller profile. One new, real, small item found and added to
  the deferred list: Lever's single combined `location` field has no
  match, since address is structured (separate line/city/state/postal/
  country) on `Profile` -- correctly left unmatched rather than
  guessing how to combine several fields into one string.
- ✅ **Generic fallback validated against a real, unknown site**
  ([ADR-0040](docs/adr/0040-generic-sign-in-wall-detection.md)): tested
  against a real IBM careers posting (no connector for this platform)
  specifically to see if the no-connector path holds up beyond the
  three named platforms. Found a real, significant gap: IBM's careers
  site redirects an unauthenticated session to a login page -- the
  same category of wall Workday's connector already detects, but the
  generic fallback path had zero sign-in-wall awareness at all.
  Extracted the detection into a shared module, added a generic check
  gated behind `--interactive` (so non-interactive usage is completely
  unaffected), and found and fixed a real bug in the first draft before
  it shipped: an early-exit that would have missed IBM's *delayed*
  redirect entirely, caught via direct reproduction before being
  relied upon.

## Phase 6 — Making Real Applications Genuinely Easier (Proposed)

Discussed directly with the project owner after the real-world
validation above: given a URL (possibly on none of the three named
platforms, possibly already signed in), can JAAP get further toward a
finished application with less manual effort? Four ideas, in the
order agreed to tackle them:

- ✅ Validate the generic fallback against an unknown site -- see
  ADR-0040 above; this is what surfaced the sign-in-wall gap.
- ⬜ Semi-automated multi-page flow: fill the current page, then stop
  and tell the person exactly which button to click to advance, rather
  than attempting to click through multiple pages automatically.
  Deliberately NOT fully-automated page-walking -- a real site can
  label its actual final submit control as "Continue" or "Next," and
  automatically clicking through every page risks eventually clicking
  that control by mistake, which would be an irreversible violation of
  the no-auto-submit boundary (ADR-0001/0012). A human stays in the
  loop at every page transition, not just at the end.
- ⬜ Combobox-filling for safe cases (e.g. a country-code dropdown, a
  saved reusable Answer) -- needs careful scoping so it never widens
  the EEO exclusion boundary (ADR-0026), which relies on the same
  combobox detection mechanism staying non-fillable by design.
- ⬜ Attaching to a real, already-running, already-logged-in Chrome
  window (via Playwright's `connect_over_cdp()`, an alternative to
  `launch()`) instead of a fresh, isolated session. Meaningfully
  different from the persistent-session-storage idea already declined
  in ADR-0034: JAAP would never touch or store a credential at all,
  only control a browser the person logged into themselves, in real
  time. The most architecturally interesting of the four, and the one
  most deserving its own dedicated design conversation before building
  it, the same way `--interactive` itself was designed before being
  built.

Also tracked: a `jaap apply --url <url>` command to reduce the
repetitive manual copy-pasting of posting/application IDs between
`seed_job_posting.py`, `application start`, and `application
attach-resume` -- a real, separate usability idea, not yet designed in
detail (open questions: whether to auto-detect the platform via the
connector registry, whether to find-or-create existing postings/
applications for the same URL rather than duplicating them, and what
default behavior makes sense when `--company`/`--title` are omitted).

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
