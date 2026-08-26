# ADR-0020: `WebsiteConnector` Interface — `click()` Added With an Explicit Safety Boundary

## Status

Accepted — 2026-07-09

## Context

Milestone 19 opens Phase 4 with the `WebsiteConnector` interface --
just the abstract contract, no implementation yet
(`GreenhouseConnector`/`LeverConnector`/`WorkdayConnector` are
Milestones 20/21/22), the same interface-then-implementation sequencing
already used successfully for `BrowserAutomationEngine` (Milestone 8)
and `AIProvider` (Milestone 13). Designing this required resolving one
safety-relevant question directly, not by default: `BrowserAutomationEngine`
has never had a `click()` method, and a connector's "locate apply flow"
responsibility will realistically need one (clicking an "Apply Now"
button, or "Continue" in a multi-step wizard). This was flagged to, and
explicitly confirmed by, the project owner before being added --
matching the deliberateness the "no automatic submission" boundary
(ADR-0001/0012) has been held to throughout this project.

## Decisions

### 1. `BrowserAutomationEngine.click(selector)` is added, as a generic primitive

Same category as `fill()`/`check()`/`select_option()`/`upload_file()` --
usable for any web automation need, not forms-specific. The critical
distinction, stated explicitly in both `BrowserAutomationEngine`'s and
`WebsiteConnector`'s own docstrings: **a generic click primitive existing
is not, by itself, a reopening of the "no automatic submission"
boundary.** That boundary (ADR-0001/0012) is specifically about there
being no code path that submits a completed application without human
review. Clicking "Apply" to reach a form, or "Next" to advance a
wizard, is navigation through an application flow, not submission of
one. `WebsiteConnector.navigate_to_application_form()`'s own docstring
states explicitly that it must never click a final submission control
-- this remains entirely off-limits, unchanged from every prior
milestone's design.

Implemented in `PlaywrightBrowserEngine.click()` with the same exception
translation as every other operational method (Playwright's `Error`
caught, re-raised as `BrowserAutomationError`).

**A real testing finding worth recording:** unlike `check()`/
`select_option()` (which have an obvious "wrong element type" fast-fail
path -- calling `check()` on a text input fails immediately), `click()`
has no such path, since it can be called on nearly any element. A
missing selector waits the full ~30-second actionability timeout. The
fastest reliable failure trigger found was a syntactically malformed CSS
selector (`:::invalid-selector:::`), which fails during selector parsing
before any actionability wait begins -- around 10.5 seconds, not
sub-second like the other methods' fast-fail tests, but meaningfully
better than the alternative and accepted as the cost of a single,
necessary regression test.

### 2. `WebsiteConnector` has exactly three methods, matching the roadmap's own three named responsibilities

- `platform_name` (a property) -- "detect current platform," paired with
  `matches(url)`.
- `navigate_to_application_form(engine)` -- "locate apply flow."
- `get_field_detector(engine)` -- "map fields."

### 3. `platform_name` is meant to correspond to `JobPosting.platform`/`JobPlatform`

`JobPlatform`'s constants (`domain/models/job_posting.py`) were written
in Milestone 2 with a docstring stating exactly this: "so that a new
connector (Milestone 19+) can introduce support for a job site... without
needing to modify this domain model." This milestone's `platform_name`
is that anticipated connector arriving on schedule, not a new pattern
invented now.

### 4. `get_field_detector()` selects/provides a `FormFieldDetector`, rather than `WebsiteConnector` duplicating its responsibility

A connector for a platform that's mostly standard HTML can return the
existing `PlaywrightFormFieldDetector` unchanged. A connector for a
platform with custom, non-native widgets -- the concrete motivating
example discussed before this milestone began: Workday's custom
dropdown/checkbox components, invisible to the generic detector's
`document.querySelectorAll("input, select, textarea")` query -- can
provide its own specialized detector. Both still produce the same
`DetectedField` type `ExactFieldMatcher` already knows how to consume.
This was evaluated explicitly against giving `WebsiteConnector` its own
parallel `detect_fields()` method (duplicating `FormFieldDetector`'s
whole responsibility) and rejected in favor of composition/selection,
consistent with this project's established preference (mappers
composed with repositories, detectors composed with engines) for
focused components over duplicated responsibility.

### 5. Minimal testable surface, by design -- same as `AIProvider` (Milestone 13)

With zero implementations and zero consumers, this milestone has almost
nothing to test beyond "is this Protocol well-formed and satisfiable" --
verified with a throwaway stub class, not a reusable fake (no real
consumer exists yet to design a fake against, matching how
`FakeBrowserEngine` wasn't added until Milestone 10 needed one).

## Alternatives Considered

- **Deferring `click()` until a concrete connector (Milestone 20+)
  proved it was needed**, matching the "don't build without a concrete
  consumer" discipline applied elsewhere. Considered seriously, and
  explicitly put to the project owner as the alternative -- but decided
  against: `WebsiteConnector`'s own three stated responsibilities make
  a click capability's necessity clear enough now (unlike, say,
  `AIProvider`'s deferred exception translation, which genuinely needed
  a real consumer's perspective to design correctly).
- **`WebsiteConnector.detect_fields()` as its own method**, duplicating
  `FormFieldDetector`. Rejected; see decision #4.
- **Not stating the click()/submit distinction explicitly**, treating it
  as obvious. Rejected: given how central and carefully-held the
  no-submission boundary has been throughout this project (ADR-0001,
  reaffirmed in ADR-0012), a safety-adjacent addition like this warranted
  explicit confirmation and explicit documentation, not an assumption
  that the distinction would be self-evident to a future reader.

## Consequences

**Positive:**
- Phase 4's connectors have a real navigation primitive (`click()`)
  available without needing to reopen or weaken the no-submission
  boundary -- the two concerns are now demonstrably separable, not
  just asserted to be.
- `get_field_detector()`'s design directly addresses the concrete
  Workday custom-widget limitation named earlier in this project's
  history, giving Milestone 22 a clear, already-designed extension
  point rather than requiring a new one.

**Trade-offs:**
- `click()`'s existence means a future connector implementation *could*
  misuse it to click a submit button, if someone weren't careful. This
  is a documentation/discipline safeguard (explicit docstrings, this
  ADR), not an enforced one -- there is no automated check preventing a
  connector from clicking whatever selector it's given. Worth watching
  for specifically during Milestone 20+'s code review, not something
  this milestone's design alone can guarantee.

## References

- ADR-0001/0012 -- the "no automatic submission" boundary this
  milestone's `click()` addition was explicitly confirmed not to
  reopen.
- ADR-0009 -- `evaluate()`'s addition to `BrowserAutomationEngine`, the
  precedent for adding a new generic primitive once a real, named need
  exists.
- ADR-0014 -- `AIProvider`'s "minimal interface, no implementation yet"
  precedent, followed identically here for `WebsiteConnector`.
