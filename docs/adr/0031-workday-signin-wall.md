# ADR-0031: Workday's Real Apply Flow — a Modal, Then a Sign-In Wall

## Status

Accepted — 2026-08-28

## Context

Real-world validation moved from Greenhouse to Workday, using Workday's
own careers site (`workday.wd5.myworkdayjobs.com/Workday`) as the
lowest-risk starting point. The very first attempt failed with
`WorkdayConnector`'s own generic error. A genuine, iterative diagnostic
investigation -- the same discipline used for Greenhouse's two findings
(ADR-0028/0029) -- uncovered a real, and more significant, characteristic
of Workday's actual application flow than anything assumed at design
time (ADR-0023).

1. The real posting URL used a `/details/` path segment, not `/job/`,
   contradicting the third-party-scraped `/apply`-suffix example
   `WorkdayConnector` was originally built around.
2. Clicking "Apply" produced no URL change at all and no visible
   effect in an early diagnostic -- but a screenshot revealed the
   actual reason: it opens an **in-page modal**, not a navigation,
   titled "Start Your Application" with four choices: "Autofill with
   Resume" (Workday's own AI resume-parsing feature -- a different
   thing from JAAP's own autofill), "Apply Manually", "Use My Last
   Application" (requires an existing session), and a third-party
   redirect option ("Apply with SEEK").
3. Clicking "Apply Manually" -- the most neutral of the four, avoiding
   Workday's own AI feature, an existing-session dependency, and a
   third-party site entirely -- still navigated to a **mandatory
   account-creation/sign-in step** ("Create Account/Sign In," the first
   stage of an eight-stage wizard) before any actual application field
   could be reached.

This last finding is categorically different from every prior
real-world-validation fix in this project. ADR-0025 through ADR-0030
were all fixable engineering gaps -- a missing label-detection pattern,
a wrong assumption about attribute names, a timing issue. This one is
not: it is a genuine product/platform characteristic of at least this
Workday tenant's configuration, and this ADR treats it accordingly.

## Decisions

### 1. JAAP will not automate account creation or sign-in, under any circumstances

This is restated here as a firm decision, not merely inherited silently:
regardless of what path forward might technically be possible, entering
credentials or creating accounts on a candidate's behalf is out of scope
for this project, permanently. This is consistent with, and reinforces,
what `SECURITY.md` already stated before this session: JAAP's browser
sessions are not persistent and it does not collect, store, or transmit
login credentials for third-party sites. It is also independent of this
project's own design choices -- it reflects a boundary held regardless
of which specific automation task is being requested.

### 2. `navigate_to_application_form()` now attempts the real, confirmed flow: click "Apply," then "Apply Manually"

The original `/apply`-suffix URL attempt (ADR-0022/0023, shared via
`_url_utils.append_apply_path()`) is kept as a first, cheap attempt --
it may still work for some Workday tenants, and costs nothing to try
first. If it doesn't reveal a form, the connector now falls back to the
real, confirmed click sequence: `engine.click("text=Apply")` (opens the
modal), then `engine.click("text=Apply Manually")` (the deliberately
chosen, most-neutral option). Verified against a direct reproduction of
the real modal structure (a button that reveals a hidden div containing
a second button, which in turn reveals the form) -- not a synthetic
guess disconnected from what was actually observed.

### 3. A specific, honest error when the flow leads to a sign-in wall, distinct from the generic "structure doesn't match" message

If neither the URL attempt nor the click sequence reveals a form or
combobox, the page is checked for sign-in/account-creation indicators
(a simple, general text pattern -- `/sign in|log in|create.{0,10}account/i`
-- checked only after every real attempt to reach the form has already
failed). If matched, `navigate_to_application_form()` raises a specific
`ValueError` stating plainly that this posting requires an account or
sign-in, and that JAAP does not automate that step -- rather than the
generic, unhelpful "page structure may not match assumptions" message
this same failure previously produced. Verified against a direct
reproduction of the real observed sequence (Apply -> Apply Manually ->
redirected to a sign-in page).

### 4. This is treated as an honestly-acknowledged, possibly unfixable limitation within JAAP's current architecture -- not a bug awaiting a future patch

Even if some *other* Workday tenant's "Apply Manually" path does not
require sign-in, this specific tenant's did, via every path except a
third-party redirect. If sign-in genuinely is required to reach any
application field, the *only* way JAAP could proceed past it would be
for a human to authenticate first and for that authenticated session to
somehow persist into JAAP's own browser automation -- which would
require `PlaywrightBrowserEngine` to support persistent browser
contexts/cookie storage across runs, a real, separate architectural
change this project has not made and is not making as part of this fix.
Building that capability, if it's ever wanted, deserves its own
deliberate design conversation (with its own real security/privacy
questions -- where session cookies would be stored, what that expands
JAAP's attack surface to look like) -- not something to bolt on
mid-validation-session as a side effect of a bug fix.

## Alternatives Considered

- **Attempting to persist a login session or accept user-supplied
  credentials for Workday specifically.** Rejected outright; see
  decision #1. Not reconsidered as an implementation option at any
  point during this fix.
- **Silently treating a sign-in wall the same as any other "form not
  found" case**, leaving the existing generic error message unchanged.
  Rejected: a human reading "this page's structure may not match
  assumptions" would reasonably try to debug a nonexistent selector
  problem, when the real, correct action is simply "there is nothing
  JAAP can do here; complete this application yourself." A specific,
  honest message serves the person better than a generic one that
  implies a fixable bug.
- **Trying additional guesses at other Workday tenants' URL/click
  patterns speculatively**, hoping to find one that doesn't require
  sign-in, before writing this ADR. Rejected in favor of documenting
  what was actually found on the one real tenant tested, honestly, and
  leaving further validation (a different company's Workday posting) as
  an explicit next step rather than papering over the current finding
  with untested optimism.

## Consequences

**Positive:**
- `WorkdayConnector` now attempts the real, confirmed mechanism
  (modal-then-click) rather than an assumption that turned out not to
  hold for this tenant, and gives a genuinely more honest, actionable
  error when the flow leads somewhere JAAP correctly won't follow.
- This project's firm stance against automating credentials is
  reinforced by a concrete, real example, not just an abstract
  principle -- useful precedent for any future connector that
  encounters the same wall.

**Trade-offs:**
- It is not yet known whether Workday's own careers site's
  authentication requirement is typical of Workday tenants generally or
  specific to this one configuration. If it turns out to be typical,
  Workday support may be structurally limited to "detect the platform
  and clearly explain that manual completion is required" rather than
  genuine autofill, for as long as JAAP's browser sessions remain
  non-persistent -- a real, honest possibility this ADR does not rule
  out, and does not attempt to solve today.
- The sign-in text-pattern check is deliberately general and may
  produce false positives or negatives on some other real page's
  wording; it was not exhaustively tested against every possible
  Workday tenant's phrasing, only the one actually observed.

## References

- ADR-0023 -- `WorkdayConnector`'s original design and its own honest
  confidence caveats, several of which this ADR's findings directly
  extend.
- ADR-0028/0029 -- the prior Greenhouse findings from the same overall
  real-world-validation effort, both genuinely fixable engineering gaps,
  offered here by contrast with this ADR's structurally different
  finding.
- `SECURITY.md` -- the pre-existing statement that JAAP's browser
  sessions are not persistent and do not handle third-party credentials,
  reinforced rather than revised by this ADR.
