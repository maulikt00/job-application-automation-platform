# ADR-0023: `WorkdayConnector` — Detection With an Honest Confidence Boundary

## Status

Accepted — 2026-07-09

## Context

Milestone 22 builds `WorkdayConnector`, the third concrete
`WebsiteConnector` and the one that directly motivated Phase 4's
existence: a much earlier conversation in this project's history asked
whether JAAP could fill in Workday application forms, and the honest
answer at the time was that `FormFieldDetector`'s generic detection
(`input, select, textarea` only) cannot see Workday's known custom
dropdown/combobox widgets at all, since those are typically `<div>`s or
`<button>`s. This ADR is where that limitation gets a real, if partial,
answer.

Following the same research-before-design discipline as
`GreenhouseConnector`/`LeverConnector` (ADR-0021/0022), Workday's URL
conventions were verified against multiple independent sources before
writing any code. Field-detection confidence, however, turned out
meaningfully lower than either prior connector's -- this ADR states that
difference precisely rather than let it blend into the same tone as the
better-evidenced decisions.

## Decisions

### 1. `matches()` checks two real domain families, confirmed independently

`{tenant}.wd{N}.myworkdayjobs.com` (the data-center number varies per
company -- confirmed explicitly: "Companies use different Workday data
centers (wd1, wd3, wd5, etc.)... Do not assume wd3 works for all
companies", from a Workday-scraping API guide) and the newer
`myworkdaysite.com` format (confirmed from the same source family).
`matches()` checks the stable substrings `myworkdayjobs.com` and
`myworkdaysite.com`, never a specific tenant or data-center number.

### 2. `navigate_to_application_form()` reuses Lever's deterministic `/apply` pattern -- confirmed independently for Workday, not assumed to generalize

A real, independently scraped Workday job posting example ends in
`.../apply` (`.../Machine-Learning-Engineer_JR-0097159/apply`) --
the same `/apply`-suffix relationship Lever's own API documents
explicitly (ADR-0022). Because this is now confirmed for two platforms
independently (not merely assumed to generalize from one), the
path-appending logic was extracted into a shared helper,
`infrastructure/connectors/_url_utils.py`, and `LeverConnector` was
updated to use it too -- a small, well-justified refactor of
already-merged Milestone 21 code, the same kind of "go back and update
earlier work once a real second consumer exists" pattern already used
for `BrowserAutomationError` (Milestone 8→10) and `AIProviderError`
(Milestone 13-15→16).

### 3. Confirmed as genuinely multi-step; this connector only reaches the start of the flow

Independent sources describe "the full Workday application flow
(upload, auto-fill form, review, submit)" -- multiple stages, not a
single page, a real and confirmed characteristic (unlike Greenhouse/Lever,
which are closer to single-page flows). `navigate_to_application_form()`
only navigates to the first step. This is not a new limitation
introduced by this milestone: `AutofillApplicationUseCase` has operated
on "whatever page is currently loaded" since Milestone 10, and a
multi-step flow already required re-running review/autofill after
manually advancing between pages, for any multi-step ATS, before this
connector existed.

### 4. `WorkdayFormFieldDetector`: composes the generic detector, adds ARIA `role="combobox"` detection -- with an explicitly lower, stated confidence level than Greenhouse/Lever's designs

This is the central, honestly-scoped decision of this milestone.
Greenhouse's `name="first_name"` (ADR-0021) and Lever's `hostedUrl`/
`applyUrl` relationship (ADR-0022) were each confirmed directly from
their platform's own published API documentation. No equivalent
primary-source confirmation of Workday's exact custom-widget DOM
structure was found or is claimed here. What was found is general
browser-automation-community knowledge that Workday uses custom
combobox-style widgets, consistent with (but not proof of) the standard,
cross-platform ARIA pattern for accessible custom dropdowns
(`role="combobox"`, typically paired with `role="listbox"`/`role="option"`).
`WorkdayFormFieldDetector` detects `[role="combobox"]` elements on that
basis -- a reasonable, standards-grounded inference, stated explicitly
as such, not asserted with the same confidence as Greenhouse/Lever's
confirmed selectors.

### 5. Every detected combobox field has `selector=None` -- a safety design that follows directly from decision #4's honest uncertainty

Per the already-established, already-tested invariant from Milestone
9/10 (`ExactFieldMatcher` never matches a field with no selector,
regardless of how well its label matches), setting `selector=None`
unconditionally for every detected combobox guarantees it can never be
automatically matched or filled -- verified directly by a test that
constructs an `Answer` with a question_key perfectly matching the
combobox's label, confirming the match still never happens. A detected
combobox can only ever surface as a visible "unmatched field" requiring
human attention.

### 6. This milestone's scope is detection only; filling a Workday combobox is real, separate, and explicitly not attempted here

`AutofillApplicationUseCase` (Milestone 10) has no dispatch branch for
"open this widget, then click the matching option" -- the interaction
sequence a combobox actually requires. Building one is real future work,
named here plainly rather than either silently worked around or
quietly left undiscovered. Given decision #4's honest confidence level,
attempting to also build automatic filling in this same milestone would
have compounded an already-uncertain detection mechanism with an
equally uncertain interaction mechanism, neither verified against a real
Workday tenant.

### 7. Same honest scope limitation as Greenhouse/Lever: embedded iframe integrations remain out of scope

For the same reason stated in both prior connectors' ADRs:
`BrowserAutomationEngine.evaluate()` runs against the main frame only,
and cross-frame interaction is a real, separate, unbuilt feature.

## Alternatives Considered

- **Not attempting any Workday-specific field detection**, reusing the
  generic detector unchanged (matching Greenhouse/Lever). Rejected:
  given the ARIA combobox pattern is a real, testable, standards-based
  enhancement that can only ever add detections (never remove or break
  existing ones) and carries zero risk of incorrect auto-fill (decision
  #5), the expected value justified building it, with the confidence
  level stated honestly rather than omitting the attempt entirely.
- **Building automatic combobox-filling in this same milestone.**
  Rejected; see decision #6.
- **Presenting the ARIA-combobox detection with the same confidence as
  Greenhouse's/Lever's confirmed selectors.** Rejected; see decision #4
  -- the evidence genuinely differs, and the documentation says so.
- **A new, Workday-specific exception category for detection
  uncertainty.** Not needed: the existing `ValueError` pattern (already
  used by `LeverConnector`'s post-navigation check) covers this
  connector's own defensive verification without a new category.

## Consequences

**Positive:**
- The custom-widget detection gap that motivated Phase 4's existence is
  now addressed, honestly, for the first time: a Workday combobox is at
  least *visible* to a human reviewing "unmatched fields," where it was
  previously entirely invisible to the generic detector.
- Zero risk of a broken or incorrect automatic fill attempt on a
  combobox field, verified directly, not just designed for.
- `LeverConnector`'s `/apply`-path logic is now shared, tested once, and
  confirmed (via a dedicated test) to work identically for a
  Workday-style URL -- concrete evidence the extraction was genuinely
  warranted, not premature abstraction.

**Trade-offs:**
- Actually filling a detected Workday combobox remains unbuilt -- a
  real, named gap, not a silently deferred one. A human still needs to
  fill these fields manually today.
- The ARIA-based detection may not match every real Workday tenant's
  actual markup (custom Workday configurations, or older/newer versions
  of Workday's own UI framework, could use different patterns this
  connector doesn't detect) -- an acknowledged limitation of an approach
  that was never claimed to be verified against a live Workday tenant.

## References

- ADR-0020 -- `WebsiteConnector`'s interface design, in particular
  `get_field_detector()`'s selection/composition pattern, which this
  connector is the first to extend rather than reuse unchanged.
- ADR-0021/0022 -- `GreenhouseConnector`/`LeverConnector`'s
  research-before-design discipline and honest scope-limitation
  practice, both continued here, alongside a genuinely lower confidence
  level stated as such.
- ADR-0009/0010 -- the `selector=None`-means-never-matched invariant
  this milestone's core safety property depends on.
