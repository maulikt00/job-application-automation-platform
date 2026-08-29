# ADR-0032: Workday's Sign-In Wall Confirmed on a Second Tenant, Plus a Genuine Click-Timing Bug

## Status

Accepted — 2026-08-29

## Context

Following ADR-0031's finding on Workday's own careers site, validation
continued against a second, independent Workday tenant (NVIDIA's,
`nvidia.wd5.myworkdayjobs.com`) specifically to find out whether the
mandatory sign-in requirement was universal to Workday or specific to
one company's configuration.

The real modal sequence (Apply -> "Apply Manually") worked identically
on NVIDIA's tenant, confirming ADR-0031's mechanism generalizes.
**"Apply Manually" led to the same "Create Account/Sign In" step here
too** -- a second, independent confirmation that this is a real,
recurring Workday characteristic, not an artifact of one tenant's setup.

Separately, a genuine, fixable bug was found while confirming this:
`WorkdayConnector`'s own "Apply Manually" click sometimes raised
`BrowserAutomationError` (a Playwright timeout) even when the click had
actually succeeded -- confirmed directly, not assumed: after the
exception was raised, the page's URL had already changed to the
expected `.../applyManually` destination. Manual diagnostic scripts run
outside the connector's own code (with no artificial delay) succeeded
consistently and quickly (under 1.5 seconds each), while the same click
inside a longer, multi-step sequence (URL-append attempt, then the
click sequence) reported a timeout on a slower-responding real request.

## Decisions

### 1. The "Apply Manually" click's own exception is now caught and treated as informational, not fatal

This click causes an immediate page transition (the browser navigates
away as a direct result of the click). Playwright's own `click()`
implementation waits for the clicked element to remain stable/attached
to the DOM before declaring success; if the page has already moved on
by the time that check runs, `click()` can report a timeout even though
the click functionally succeeded. `navigate_to_application_form()` now
catches exactly this one call's `BrowserAutomationError` and proceeds
to check the resulting page state regardless, rather than letting the
exception propagate as a hard failure. The first click ("Apply," which
only opens an in-page modal without navigating anywhere) is
deliberately NOT wrapped this way -- there is no equivalent
transition-timing concern for it, and swallowing its own exceptions
too would risk masking a genuinely different kind of failure.

### 2. Verified with a targeted fake, not a forced real timeout

Reproducing an actual 30-second Playwright timeout deterministically
inside a fast, real-Chromium unit test is neither practical nor
reliable -- the underlying cause is inherently about response-time
variability on a real, remote server, not something a local test
server reproduces consistently. A minimal, narrowly-scoped fake engine
(not a general-purpose reusable fake, and not the pattern used by every
other connector test in this project, which uses real Chromium) is used
instead, to verify the exception-handling *logic* itself: that the
code correctly continues past this specific exception and still
reaches the right outcome (form found, or sign-in wall correctly
detected) either way. The real, underlying timing behavior this
simulates was already confirmed directly against a live site, not
invented for the test.

### 3. This does not change ADR-0031's conclusion -- it makes reaching that conclusion reliable instead of accidental

Before this fix, whether a user saw the correct, honest "requires
sign-in" message or a confusing raw timeout depended on unpredictable
real-world response-time variance. After this fix, the same underlying
situation (a Workday tenant requiring authentication) is reported
consistently and clearly, regardless of how quickly the intervening
page transition happens to occur.

## Alternatives Considered

- **Increasing the click timeout.** Rejected: the issue is not that 30
  seconds was too short in an absolute sense -- confirmed diagnostic
  runs succeeded in under 1.5 seconds when run in isolation. The
  underlying cause (an element becoming detached mid-check due to the
  navigation the click itself causes) is a category of Playwright
  behavior a longer timeout does not reliably fix, only delays.
- **Wrapping every click in this connector (including the first
  "Apply" click) in the same catch-and-continue logic**, for
  uniformity. Rejected: the first click only opens an in-page modal and
  never causes a page transition, so it has no equivalent
  timing-related failure mode to account for -- swallowing its
  exceptions too would risk hiding a genuinely different kind of bug
  behind the same reasoning that correctly applies only to the second
  click.
- **Attempting to force a real 30-second timeout in an automated
  test**, for maximum fidelity to the real bug. Rejected as
  impractical and unreliable; see decision #2.

## Consequences

**Positive:**
- Workday's mandatory-authentication characteristic (ADR-0031) is now
  confirmed on a second, independent real tenant -- meaningfully
  stronger evidence than a single observation that this is a real,
  recurring platform behavior, not one company's idiosyncrasy.
- The connector now reliably reports the correct, honest outcome
  regardless of real-world timing variance, rather than sometimes
  producing a confusing, unrelated-looking error for what is actually
  the same underlying situation ADR-0031 already named and explained.

**Trade-offs:**
- If the "Apply Manually" click genuinely fails for some other reason
  entirely (not the navigation-timing quirk this fix specifically
  addresses), that failure is now silently absorbed and the code
  proceeds to the post-click checks anyway -- which will then correctly
  report either "form found" or "sign-in wall detected," but not the
  original, different reason the click may have failed. This is an
  accepted trade-off: the two real, observed outcomes at this point
  (success, or a sign-in wall) are exactly the two cases this connector
  needs to distinguish; a third, unanticipated failure mode would still
  surface eventually via the final generic error message, just without
  attribution to the click specifically.

## References

- ADR-0031 -- the original sign-in-wall finding this ADR confirms on a
  second, independent tenant and makes reliably reportable.
- ADR-0028 -- Greenhouse's own real-world timing finding (form-presence
  polling), a related but structurally different kind of timing issue
  from the one this ADR addresses.
