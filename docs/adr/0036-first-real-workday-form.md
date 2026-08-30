# ADR-0036: First Real Workday Form Reached — a Retry-Loop Fix and a Confirmed, Known Limitation

## Status

Accepted — 2026-08-30

## Context

The first genuine, end-to-end use of `--interactive` (ADR-0034), after
ADR-0035's sign-in-detection-order fix, produced two real, separate
results across two runs against the same NVIDIA Workday posting.

**Run 1**: the sign-in wall was correctly detected this time (confirming
ADR-0035's fix), the prompt appeared, and after the person signed in and
pressed Enter, the retry failed -- but with the generic "no field with a
data-automation-id attribute was found" `ValueError`, not another
`AuthenticationRequiredError`. `_wait_for_manual_sign_in()` only caught
the latter, so this different exception type propagated straight out,
ending the command. The most likely explanation: immediately after
signing in, the page was briefly in a transitional state (mid-redirect,
still loading) that matched neither "form found" nor "still requires
sign-in."

**Run 2**: a completely separate invocation (a fresh browser, signing in
again, since sessions never persist between runs) succeeded --
`Detected platform: workday`, and the review reported 16 real fields:
`legalName--firstName`, `legalName--lastName`, `addressLine1`, `city`,
`postalCode`, `phoneNumber`, `candidateIsPreviousWorker`, and others.
**This is the first time in this project's history that a real,
authenticated Workday application form has actually been observed.**
Every prior validation attempt (ADR-0031/0032/0033/0035) was blocked by
the sign-in wall before ever reaching this point.

`Autofilled 0 field(s)` was reported. This is not a new bug: no `email`
field appears anywhere in the list at all (Workday likely already knows
it from the authenticated account, so there is nothing to autofill
there), and the name field is split (`legalName--firstName`/
`legalName--lastName`). `ExactFieldMatcher`'s own module docstring
already states, as a deliberate, pre-existing design choice, that it
does not attempt to split `Profile.full_name` into first/last parts --
the exact same limitation already confirmed on Greenhouse (ADR-0029),
now also confirmed on Workday's real form. Whether to build first/last
name splitting is a real, separate decision, explicitly left to the
project owner rather than decided unilaterally here.

## Decisions

### `_wait_for_manual_sign_in()` now also retries on a connector's other exception types, not only a repeated `AuthenticationRequiredError`

The retry loop catches `(ValueError, BrowserAutomationError)` in
addition to `AuthenticationRequiredError` -- the two other exception
types a `WebsiteConnector`'s `navigate_to_application_form()` can
plausibly raise (a connector's own "structure doesn't match" message, or
an underlying browser automation failure). On catching either, the loop
prints a message explaining the attempt didn't succeed and that the
page may still be loading, then continues waiting for the next
Enter/`'q'`, exactly as it already did for a repeated sign-in-wall
detection. This directly reflects what was actually observed: a real
site can be in a transient, hard-to-categorize state immediately after
a redirect, and a human actively driving this interactively should be
able to simply try again rather than have the whole command die.

Verified with a fake connector that raises the exact real error message
observed (the ADR-0033/0035 generic fallback `ValueError`) on its first
call, then succeeds on the second -- reproducing the actual scenario,
not a synthetic guess.

## What This ADR Deliberately Does Not Decide

Whether to build first/last name splitting (so `legalName--firstName`/
`legalName--lastName`-style fields, and Greenhouse's own
`first_name`/`last_name` fields, could be auto-filled) is left as an
open question for the project owner, not resolved here. Splitting a
full name correctly is itself a real design problem (multiple middle
names, single-word names, non-Western name ordering) that
`ExactFieldMatcher`'s own docstring already named as a reason to avoid
guessing -- building it now would be a real, separate feature decision,
not a natural extension of this retry-loop fix.

## Alternatives Considered

- **Catching a bare `Exception`** in the retry loop, to cover any
  possible future failure mode. Rejected: this project has consistently
  avoided overly broad exception handling that could mask genuinely
  unrelated bugs; the three specific types caught here
  (`AuthenticationRequiredError`, `ValueError`, `BrowserAutomationError`)
  are exactly the types a connector's own contract can plausibly raise,
  not an unbounded catch-all.
- **Deciding to build name-splitting as part of this ADR**, since it was
  discovered in the same session. Rejected; see "What This ADR
  Deliberately Does Not Decide" above -- this is a real, separate
  decision warranting its own conversation, not something to fold in
  opportunistically.

## Consequences

**Positive:**
- `--interactive` is now more resilient to the specific, real timing
  behavior observed on an actual site, rather than requiring a full
  command restart (and a fresh sign-in) for what may just be a moment's
  loading delay.
- For the first time, this project has real evidence of what a genuine
  Workday application form's field names actually look like
  (`legalName--firstName`, `addressLine1`, `candidateIsPreviousWorker`,
  etc.) -- confirming `WorkdayFormFieldDetector`'s generic detection
  correctly recognized these fields as fields at all (the ADR-0033 gap
  about never having observed real form markup is now partially
  addressed, for at least this one tenant's non-combobox fields).

**Trade-offs:**
- The "Autofilled 0" outcome, while correctly explained by an existing,
  documented limitation, means Workday's real form is not yet
  meaningfully more autofillable in practice than before this session --
  the value delivered here is confirmed reachability and correct,
  safe reporting, not new autofill capability.
- Whether name-splitting is worth building remains genuinely open,
  deliberately not decided by this ADR.

## References

- ADR-0034 -- the `--interactive` mechanism this fix extends.
- ADR-0035 -- the sign-in-detection-order fix that made reaching this
  point possible in the first place.
- ADR-0029 -- Greenhouse's own first observation of this exact same
  split-name limitation, now confirmed a second time on Workday.
- `application/services/field_matcher.py`'s own module docstring -- the
  pre-existing, deliberate choice not to split `full_name`, restated
  here rather than revisited unilaterally.
