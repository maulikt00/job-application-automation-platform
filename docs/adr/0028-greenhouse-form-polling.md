# ADR-0028: Greenhouse Form-Presence Polling — a Real-World Timing Bug

## Status

Accepted — 2026-08-28

## Context

Real-world validation moved from Lever (ADR-0025/0026/0027) to
Greenhouse: a live posting at `job-boards.greenhouse.io/remotecom/jobs/7774935003`.
`jaap application review` failed immediately with
`GreenhouseConnector`'s own designed error: "Clicked an 'Apply' element,
but no Greenhouse application form was found afterward."

A screenshot of the real page showed the application form (First Name,
Last Name, Email, Country, Phone -- all real, native inputs) fully
present and rendered, with no separate "Apply" step needed at all --
directly confirming `GreenhouseConnector`'s original assumption
(ADR-0021) that Greenhouse job posts typically serve the description
and the form on the same page. The connector's own check for that
exact condition (`_form_is_present()`) should have short-circuited as a
no-op. It didn't -- meaning the check ran before the form had actually
finished rendering, not that the form-on-same-page assumption itself
was wrong.

## Decisions

### 1. `navigate_to_application_form()` now polls for the form's presence instead of checking exactly once

`_wait_for_form()` checks up to 10 times, 0.5 seconds apart (5 seconds
total), before concluding the form isn't there and falling back to the
existing "click Apply" path. This addresses a timing issue, not a
structural one: Playwright's `navigate()` resolves once the page's
"load" event fires, but a JS-heavy page (as Greenhouse's evidently is)
can continue rendering content -- including the application form itself
-- after that event, for some amount of additional time this project
has no way to predict in advance without observing it, which is exactly
what this validation run did.

Verified against a direct reproduction of the real bug: a synthetic
page whose form is injected via `setTimeout(..., 1500)` with **no**
"Apply" element present at all (matching the real page's actual
structure -- no click needed, just a render delay). Before this fix,
this reproduction failed with the exact same error message observed on
the live site; after, it succeeds.

### 2. A plain polling loop (`time.sleep()`), not a new `BrowserAutomationEngine` primitive

`BrowserAutomationEngine` has no "wait for selector" method. Adding one
now, for a single connector's single call site, would be exactly the
kind of interface expansion this project has consistently avoided
without a demonstrated need spanning more than one caller (see
ADR-0006 and others on this theme). A bounded polling loop built from
existing primitives (`evaluate()`, already used for the presence check)
is the smaller, sufficient mechanism -- reconsider a real "wait for
selector" primitive only if a second connector is found to need the
same capability for a different reason.

## Alternatives Considered

- **Changing `PlaywrightBrowserEngine.navigate()`'s wait strategy
  globally** (e.g., waiting for `networkidle` instead of `load`).
  Rejected: this would change behavior for every connector and every
  other caller of `navigate()`, not just Greenhouse's specific,
  observed rendering delay -- Lever's own `/apply` navigation, for
  example, showed no evidence of needing this. A connector-scoped fix
  is the more surgical, appropriately-bounded change.
- **Increasing the poll count/delay arbitrarily high "to be safe."**
  Rejected in favor of a bounded, modest total wait (5 seconds): a
  connector that genuinely can't find the form after 5 seconds of
  polling should fail with a clear error rather than hang indefinitely
  on a page that may simply not match its assumptions at all.

## Consequences

**Positive:**
- `GreenhouseConnector` now correctly handles a real, observed
  characteristic of at least one live Greenhouse-hosted posting, closing
  a failure that would have blocked every real Greenhouse validation
  attempt at the very first step.
- The fix is verified against a direct reproduction of the actual
  observed failure, not just a plausible guess at what might have
  happened.

**Trade-offs:**
- Every `navigate_to_application_form()` call for a posting whose form
  genuinely isn't found (a real structural mismatch, not a timing one)
  now takes up to 5 seconds longer to report that clearly, rather than
  failing immediately -- an acceptable cost for correctly handling the
  common, real case first.
- This specific render delay was observed on one real Greenhouse
  posting; it is not yet known whether this is typical of Greenhouse
  postings generally or specific to this one tenant's configuration.

## References

- ADR-0021 -- `GreenhouseConnector`'s original design, whose
  "form-on-same-page" assumption this fix confirms rather than revises.
- ADR-0025/0026/0027 -- the preceding real-world-validation findings
  from the same overall effort, against Lever.
