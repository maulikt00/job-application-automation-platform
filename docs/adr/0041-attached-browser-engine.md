# ADR-0041: Attaching to a Real, Already-Signed-In Browser (`AttachedBrowserEngine`)

## Status

Accepted — 2026-08-31

## Context

Discussed directly with the project owner as the fourth and final item
on Phase 6's original list, after the other three were reordered:
rather than JAAP launching and navigating its own fresh browser session
(and hitting whatever sign-in wall a real site presents, ADR-0031/0040),
could JAAP instead act on a real, already-running browser window the
person launched and signed into themselves?

This is a meaningfully different thing from the persistent-session idea
already declined in ADR-0034: JAAP would never touch, store, or
transmit a credential at all -- it would only ever control a browser
the person authenticated in their own hands, in real time, in the
current session. The mechanism for this is Chrome's remote-debugging
(CDP) protocol, which Playwright can connect to via
`connect_over_cdp()` as an alternative to `launch()`.

Given the real, serious stake involved -- a mistake here could mean
JAAP's own cleanup code closing the person's actual, in-use browser
window -- this was researched directly against Playwright's own
official documentation before any code was written, not assumed.

## Research Findings, Stated Precisely

Playwright's official docs, consistent across every language binding,
state that `Browser.close()` behaves differently depending on how the
browser was obtained: "In case this browser is obtained using
`browserType.launch()`, closes the browser and all of its pages... In
case this browser is connected to, clears all created contexts
belonging to this browser and disconnects from the browser server."

This is reassuring on its face -- but a real, filed Playwright GitHub
issue (#30299, "Unclear docs on browser.close() behavior about closing
attached contexts") shows Playwright's own users find this exact
wording genuinely confusing, specifically around whether "clears all
created contexts" could include contexts/pages that existed *before*
the connection was made (i.e., the person's own, real, already-open
tab) as opposed to only ones Playwright itself created during the
session. This ambiguity was not resolved by further research, and is
treated honestly as unresolved, not glossed over.

## Decisions

### 1. `AttachedBrowserEngine.close()` never calls `.close()` on the connected Browser object, under any circumstances

Given the live ambiguity above, and given what's at stake (the
person's own real browser, potentially with other unrelated tabs
open), the safest possible design was chosen rather than the most
convenient one: `close()` only ever calls `self._playwright.stop()` --
shutting down JAAP's own local CDP client/driver process. No method
that could plausibly affect the connected browser itself is ever
called. Verified directly with a mock-based test asserting
`browser.close.assert_not_called()` after a full launch-then-close
cycle -- a permanent regression test guarding this exact property.

### 2. Shared page-operations logic extracted into `_PageOperationsMixin`

`PlaywrightBrowserEngine` (launches a fresh browser) and
`AttachedBrowserEngine` (connects to an existing one) differ only in
how a page is obtained and how cleanup works -- every other operation
(`navigate`, `evaluate`, `fill`, `check`, `select_option`,
`upload_file`, `click`, `screenshot`) is identical regardless. This was
extracted into a shared mixin rather than duplicated across two
classes. Verified as a clean, behavior-preserving refactor of
already-tested code: all 63 pre-existing `PlaywrightBrowserEngine`
tests passed unchanged after the extraction, before any new code was
added.

### 3. Target page selection: `context.pages[-1]` (the most recently opened tab)

CDP has no reliably documented way to determine which tab currently
has focus. Rather than guess at something more elaborate, the simplest
heuristic was chosen, paired with an explicit expectation stated in
this class's own docstring and the CLI command's own help text: the
person should use a dedicated Chrome window with only the one relevant
tab open, removing the ambiguity entirely rather than trying to solve
it programmatically. Clear, specific errors are raised if no context or
no page exists at all, rather than a confusing failure deeper in the
autofill pipeline.

### 4. A new CLI command, `jaap application autofill-current-page`, not folded into `application review`

Deliberately separate: `review`'s semantics (job posting lookup,
navigation, connector-driven multi-step handling) don't apply here at
all -- there is no job posting record, no navigation, no sign-in-wall
handling to do, since the person is already on the real form, already
signed in. Reuses `ReviewApplicationUseCase` directly, unchanged --
it already took only `profile_id`/`screenshot_path`/`resume_id`, with
no `JobPosting`/`Application` coupling at all, confirming this piece of
the existing architecture was already well-suited to a use case its
original designer hadn't anticipated. Also reuses the same connector
registry `review` uses: if the current page happens to be on a known
platform, its specialized field detector (e.g. Workday's
ARIA-combobox detection) is used automatically, with no navigation
step needed since the person is already on the real form.

### 5. The report-printing logic was extracted into a shared `_print_review_report()`

Both `review` and `autofill-current-page` produce the same
`ApplicationReview` shape and should report it identically -- extracted
rather than duplicated, verified via the full existing `review` test
suite passing unchanged after the extraction.

## What This ADR Does Not, and Cannot, Verify

This sandboxed development environment has no real Chrome instance
with remote debugging enabled, so a genuine CDP connection has never
actually been exercised. Every test written against
`AttachedBrowserEngine`'s connection logic uses mocks constructed to
match Playwright's documented API shape -- verifying the *code's own
logic* (correct URL passed, correct page selected, close() never
touching the browser) but not a real, live handshake, a real
already-authenticated session, or genuine confirmation that the
person's actual browser window remains open and undisturbed afterward.
This must be verified directly, carefully, and deliberately on the
project owner's own machine before this feature is trusted for regular
use -- starting with a disposable, throwaway browser window, not a
primary daily-use one, precisely because of the documentation ambiguity
named above.

## Alternatives Considered

- **Persistent session storage** (saving cookies to disk across runs).
  Already declined in ADR-0034; this ADR's approach is meaningfully
  different (no credential ever touched or stored) and was chosen
  specifically because it avoids that earlier decision's trade-offs
  rather than reopening them.
- **Attempting to determine the "active" tab more precisely** (e.g. via
  some CDP-level focus signal). Rejected: no reliably documented
  mechanism exists; a dedicated single-tab window, explicitly
  recommended, resolves the same ambiguity more simply and reliably.
- **Reusing `application review`'s existing command with a new flag**
  (e.g. `--attach` instead of `--job-posting-id`) rather than a wholly
  separate command. Rejected: the semantics diverge enough (no
  navigation, no job-posting record, no sign-in-wall handling) that
  forcing both into one command's argument surface would have made
  `review`'s own contract less clear, not more convenient.

## Consequences

**Positive:**
- A genuinely new capability -- filling in a form on a real,
  already-authenticated browser session -- without JAAP ever touching a
  credential, storing a session, or reopening the trade-offs already
  declined in ADR-0034.
- The safety-critical property (never closing the person's real
  browser) was researched against primary, official documentation
  before writing any code, and is directly, permanently tested.
- Confirmed, not just hoped: the existing `ReviewApplicationUseCase`
  and connector registry needed zero changes to serve this new use
  case, a positive signal about the architecture's own design.

**Trade-offs:**
- Real CDP connection behavior remains unverified in this sandbox --
  named explicitly, not glossed over, and treated as a required next
  step before relying on this feature for real applications.
- Multi-tab ambiguity is handled by convention (a dedicated
  single-tab window) rather than a technical guarantee.

## References

- ADR-0034 -- the persistent-session idea this approach deliberately
  differs from and avoids reopening.
- Official Playwright documentation (`Browser.close()`, all language
  bindings) and Playwright GitHub issue #30299 -- the primary sources
  this ADR's central safety decision rests on.
