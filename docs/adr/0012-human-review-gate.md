# ADR-0012: Human Review Gate — Screenshot as Artifact, No Submit Capability Exists

## Status

Accepted — 2026-07-09

## Context

Milestone 12, the capstone of Phase 2, needed to add "an explicit review
and confirm step... before any submit button is engaged" (per
`PROJECT_ROADMAP.md`'s own wording). This required confronting the most
safety-relevant design question in the project so far: what does a
"review gate" actually consist of, given that ADR-0001 committed from
the very first milestone to JAAP never blindly submitting applications.

## Decisions

### 1. No `click()`/`submit()` method exists anywhere in this codebase

This is a fact worth stating explicitly, not just a passive absence.
`BrowserAutomationEngine` has `launch`, `navigate`, `evaluate`, `fill`,
`check`, `select_option`, `upload_file`, `screenshot`, `close` -- and
nothing else. No milestone up to now added a generic click primitive,
because none needed one (following the "don't build an abstraction
without a concrete consumer" discipline from ADR-0006/0008/0009/0010).
Milestone 12 does not add one either. The practical consequence: **there
is no code path anywhere in this project that could click a submit
button**, even by accident. The human review gate is not primarily a
confirmation prompt that blocks a submit call -- it's this structural
fact, made visible and documented.

### 2. `ReviewApplicationUseCase` composes `AutofillApplicationUseCase`, adding exactly one responsibility: a screenshot

Matches the engine/detector (ADR-0009) and mapper/repository (ADR-0005)
splits already established: a focused component composed with an
existing one via constructor injection, rather than either duplicating
its logic or bloating its scope. `AutofillApplicationUseCase`'s
responsibility stays "fill matched fields"; `ReviewApplicationUseCase`'s
added responsibility is "capture the resulting state for a human to
look at." A new `ApplicationReview` type (`matched`, `unmatched`,
`screenshot_path`) keeps this cleanly separate from `FieldMatchResult`,
which stays scoped to Milestone 10's matching concern.

### 3. The screenshot is the reviewable artifact; the browser closes at the end of the review command, not left open for a live handoff

An alternative was seriously considered: leave the browser open after
`ReviewApplicationUseCase` returns, so a human (particularly with
`headless=false`) could take over the exact same live session and
review/submit interactively. This was rejected for two reasons: it
depends on process-lifecycle behavior this project has not verified
(whether a Playwright-launched browser subprocess survives its parent
CLI process's `main()` returning is not something to rely on without
much deeper investigation), and it is a meaningfully larger feature
(an interactive "pause and wait for confirmation" workflow) than this
milestone's stated scope. The screenshot, captured before the browser
closes, is judged sufficient: it gives the human what they need --
matched values, unmatched fields, and visual confirmation of the
resulting page state -- to decide whether and how to proceed manually,
without requiring a live session handoff.

### 4. `jaap application review` is the first CLI command that touches the browser layer

Required two additions to `Context` (`presentation/cli/main.py`):
`settings` (so the command can construct a `PlaywrightBrowserEngine` on
demand) and `answer_repository` (a real gap found while wiring this up
-- `AutofillApplicationUseCase` has always required an
`AnswerRepository`, but nothing in the CLI ever constructed one, since
no command needed it before this one). Both are added directly to
`Context` rather than threading them through some other mechanism,
consistent with `Context`'s existing role as "everything a command
handler might need." Browser construction happens inside the review
command's own handler, not eagerly in `build_context()` -- every other
command (`profile create`, `resume add`, ...) must keep completing
instantly with no browser launch cost.

### 5. A real, previously-unnoticed type mismatch was found and fixed while wiring this up

`BrowserAutomationEngine.__exit__`'s Protocol signature
(`def __exit__(self, *exc_info: object) -> None`) did not precisely
match Python's actual context manager contract, which
`PlaywrightBrowserEngine.__exit__` correctly implements
(`(exc_type, exc_value, traceback)`). This went unnoticed through
Milestones 8-11 because the only prior conformance check
(`engine: BrowserAutomationEngine = PlaywrightBrowserEngine(...)`, a
variable assignment) didn't exercise it strictly enough; passing a
`PlaywrightBrowserEngine` instance as a constructor argument elsewhere
(exactly what `_handle_review` does) did. Fixed at the source: the
Protocol's `__exit__` now uses the precise three-parameter signature,
not a loose `*args` stand-in. Full project mypy check (`src/jaap/`,
69 files) is clean after the fix.

## Alternatives Considered

- **A `click()`/`submit()` primitive, gated behind a confirmation
  prompt.** Rejected outright; see decision #1. Adding the primitive at
  all, even behind a gate, would be building an abstraction Phase 4's
  actual connectors (which know where and how to safely submit on a
  specific platform) are better positioned to design when they exist.
- **Leaving the browser open for a live human handoff after review.**
  Rejected; see decision #3.
- **A confirmation prompt/flag as the primary "gate" mechanism**
  (e.g. `--confirm` before proceeding). Not needed: since nothing in
  this codebase can submit regardless of any flag, a confirmation
  prompt would only be theater -- there's nothing real to gate.

## Consequences

**Positive:**
- The "never blindly submit" promise from ADR-0001 is now verifiably
  true by inspection of the entire `BrowserAutomationEngine` interface,
  not just asserted in documentation.
- `jaap application review` was verified genuinely end-to-end: a real
  local HTTP server (run in a background thread within the test
  process, chosen specifically because an earlier session this project
  learned that a separately-backgrounded shell process does not
  reliably survive between tool calls), real Chromium, real navigation,
  real autofill, and a real, non-empty screenshot file confirmed on disk.
- Fixing the `__exit__` signature mismatch closes a real gap in
  Protocol/implementation conformance that had gone undetected for four
  milestones.

**Trade-offs:**
- No interactive live handoff means completing an actual submission
  still requires the human to separately open the job posting
  themselves -- JAAP's automation and the human's final action are not
  connected in the same browser session. Acceptable for this project's
  current stage; worth revisiting if real usage shows this friction
  matters more than assumed here.

## References

- ADR-0001 -- the original "AI should never control browser automation...
  never blindly submitting applications" commitment this milestone makes
  structurally verifiable.
- ADR-0005/0009/0010 -- the composition patterns
  `ReviewApplicationUseCase` follows.
- ADR-0006/0008/0009/0010 -- the "don't build an abstraction without a
  concrete consumer" discipline that keeps `click()`/`submit()` out of
  this codebase entirely, for now.
