# ADR-0040: Sign-In Wall Detection Generalized to the No-Connector Fallback Path

## Status

Accepted — 2026-08-31

## Context

As part of validating the generic, no-connector fallback path against a
real, unknown site (`careers.ibm.com`), a posting returned "Autofilled 0
field(s): All detected fields were matched" -- a report meaning
literally zero fields were found at all, not "fields found but
unrecognized." A screenshot showed a real, fully-rendered
"Choose an option to apply" page, but direct diagnostic scripts against
the same URL returned empty content, then a `BrowserAutomationError`
("execution context was destroyed, most likely because of a
navigation"), and finally, after waiting long enough, landed cleanly on
`login.ibm.com` -- "IBMid - Sign in or create an IBMid." The page the
person saw in their own browser only rendered because they were already
signed into IBM; JAAP's fresh, unauthenticated session was redirected to
a login wall the whole time.

This is the same category of finding as Workday's sign-in wall
(ADR-0031), but on a wholly unrelated platform with no connector at
all. `AuthenticationRequiredError` and `jaap application review
--interactive` (ADR-0034) were always designed to be general -- formalized
directly in `WebsiteConnector`'s own interface contract, not
Workday-specific -- but until this finding, they had only ever been
exercised through `WorkdayConnector`. The generic fallback path
(`_handle_review`'s `else` branch, used whenever no connector matches a
URL) had no sign-in-wall awareness whatsoever.

## Decisions

### 1. Sign-in-wall detection extracted into a shared module

`application/services/sign_in_wall_detector.py`, with a single function
`looks_like_sign_in_wall(engine)`. Previously private to
`WorkdayConnector`. `WorkdayConnector` now imports and uses this shared
function instead of its own copy -- verified as a clean,
behavior-preserving refactor (all pre-existing Workday tests passed
unchanged after the change).

### 2. A new `_check_generic_sign_in_wall()` for the no-connector fallback path

Polls for the current page to resolve, raising
`AuthenticationRequiredError` if it looks like a sign-in wall.

### 3. A real bug found and fixed in this function's own first draft, before it ever shipped

The first version returned as soon as a single check came back
negative ("no sign-in wall right now"). This completely defeated the
actual, confirmed problem: IBM's redirect is *delayed* -- the initial
page has no sign-in text at all, and only becomes a sign-in wall after
a real, multi-second client-side redirect. A direct reproduction (a
synthetic page that redirects to a sign-in page after a delay) caught
this immediately: the buggy version failed to detect the wall at all.
Fixed by never exiting early on a negative result -- the function now
polls for the *entire* configured window unless a sign-in wall is found
first, guaranteeing a delayed redirect anywhere within that window is
still caught. Re-verified against the same reproduction, which now
passes, and against a dedicated regression test specifically guarding
against this exact class of bug recurring.

### 4. The transient `BrowserAutomationError` found mid-redirect is tolerated, not a hard failure

Matches the exact real error observed ("execution context was destroyed,
most likely because of a navigation") -- caught and treated as "not
settled yet, keep polling," the same reasoning already established for
Workday's own click-timing quirk (ADR-0032).

### 5. This check is gated behind `--interactive`, not run unconditionally

Polling for a delayed redirect that may or may not happen takes real,
multi-second time. Running this unconditionally, on every single
generic-path review, would add that cost even to the common case where
no sign-in wall exists at all -- a real, unwanted latency regression for
the majority of usage. Gating it behind `--interactive` means: without
the flag, behavior is completely unchanged from before this fix (the
existing, if less informative, "0 fields found" outcome); with the
flag -- signaling the person has already opted into a more hands-on,
interactive session -- the extra wait is a reasonable, worthwhile cost
for a correct, actionable "this requires signing in" message instead.

### 6. `_wait_for_manual_sign_in()` decoupled from `WebsiteConnector`

Now takes a plain `retry: Callable[[], None]` instead of a
`WebsiteConnector` instance directly. The same pause-and-retry loop now
serves both a connector's own `navigate_to_application_form()` and the
generic path's own `_check_generic_sign_in_wall()`, without either
needing to know about the other, and without duplicating the loop's own
logic (multi-attempt retry, `'q'` to give up, tolerance for
`ValueError`/`BrowserAutomationError` from ADR-0036) a second time.

## Alternatives Considered

- **Running the generic sign-in check unconditionally, on every
  generic-path review.** Rejected; see decision #5.
- **A fixed, unconditional sleep before the first check**, rather than
  a proper poll loop. Rejected: this either wastes time when no
  redirect happens (an unconditional worst-case wait every time) or
  still risks missing a slower redirect than whatever fixed duration
  was chosen -- an adaptive poll that exits as soon as a wall is
  *found* (while still covering the full window when it isn't) is
  strictly better on both axes.
- **Leaving the early-return bug in place**, reasoning that "some
  detection is better than none." Rejected outright: shipping a check
  that provably fails against the exact real scenario that motivated
  building it in the first place would have been worse than not
  building it at all -- silent, false confidence.

## Consequences

**Positive:**
- Sign-in-wall detection is now genuinely general, exactly as ADR-0034
  originally intended, rather than a capability that existed on paper
  but was only ever exercised by one connector.
- A real, working bug was found and fixed via direct reproduction
  before ever being relied upon -- the delayed-redirect regression test
  now specifically guards against this exact failure mode recurring.
- Non-interactive usage (the default, and almost certainly the more
  common case) is completely unaffected -- verified by design, not just
  asserted.

**Trade-offs:**
- `--interactive` runs against a genuinely unknown, no-connector site
  now carry a real, multi-second latency cost even when no sign-in wall
  turns out to be present -- an accepted cost of correctness for the
  case where one does.
- The underlying sign-in-text pattern remains a general heuristic (the
  same caveat already stated in ADR-0031); confirmed correct on two
  real, unrelated sites now (Workday, IBM), but not exhaustively
  verified against every possible site's wording.

## References

- ADR-0031/0032/0033/0035 -- Workday's own sign-in-wall findings, the
  origin of the detection pattern and the click-timing/tolerance
  reasoning this ADR reuses and generalizes.
- ADR-0034 -- `--interactive`'s original design, which explicitly
  intended this mechanism to be general from the start.
