# ADR-0035: Field-Presence Alone Cannot Rule Out Workday's Own Sign-In Form

## Status

Accepted — 2026-08-30

## Context

The first real use of `--interactive` (ADR-0034) against a real,
sign-in-gated NVIDIA Workday posting completed "successfully" -- no
interactive prompt ever appeared, `email` was reported as autofilled,
and two fields needed review: one labeled "Password," and one labeled
"Enter website. This input is for robots only, do not enter if you're
human." Neither of those looks like anything from a job application --
the second is a textbook bot-honeypot field, a pattern specific to
login/signup forms, not application forms. This was Workday's own
**sign-in form**, not the application form: JAAP had auto-filled a
profile's email address into a login page's own email field, believing
it had reached the real form.

The root cause follows directly from ADR-0033's own fix. That fix
correctly narrowed field detection to require Workday's own
`data-automation-id` attribute, ruling out unrelated site chrome (a nav
search box, cookie-consent checkboxes). But Workday's sign-in form is
*also* a genuinely Workday-rendered component, and its own email/
password inputs almost certainly carry the same `data-automation-id`
convention. `_field_present()` alone cannot distinguish "the real
application form" from "any Workday-rendered page with fields,
including its own sign-in form" -- and the code's check order made this
concrete: `_field_present()` was checked first, and returned `True`
immediately upon landing on the sign-in page (since it has
`data-automation-id`-tagged fields), before the sign-in-text check ever
ran. `navigate_to_application_form()` declared success and returned,
never raising `AuthenticationRequiredError` at all.

## Decisions

### A sign-in wall is now checked before ever declaring success on field-presence alone

`_on_real_application_form()` replaces the bare `_field_present()` check
at both call sites (after the URL-append attempt, and after the click
sequence): it checks the sign-in-indicator pattern first, and only
checks for fields if that comes back negative. Field-presence is
necessary but not sufficient for declaring success; it must also not
look like a sign-in wall, checked every time, not only as a fallback
once no fields are found at all.

Verified directly against the exact real scenario: a page containing
`<h2>Sign In</h2>` alongside `data-automation-id`-tagged email/password
inputs is now correctly rejected as "not the real form," and a full
click-through reproduction (posting page -> modal -> "Apply Manually"
-> a login page with real automation-id fields) now correctly raises
`AuthenticationRequiredError`, where it previously returned successfully
and silently auto-filled the login form's own email field instead.

### A regression test confirms the fix isn't overly broad

A genuinely real application form (no sign-in text anywhere) is still
correctly recognized as the real form -- the fix narrows exactly the
one case found, not field-presence detection generally.

## Alternatives Considered

- **Checking for the specific honeypot field pattern** ("for robots
  only") as an additional signal. Rejected: the existing sign-in-text
  check (`/sign in|log in|create.{0,10}account/i`) already correctly
  catches this exact page (it literally displays "Sign In" as a
  heading) -- the bug was in check *order*, not in needing a new
  detection signal. Adding a second, narrower signal for a symptom the
  existing signal already covers would be unnecessary complexity.
- **Excluding fields with `type="password"` specifically** from
  `_field_present()`'s query, as a more targeted fix. Considered, but
  rejected in favor of the sign-in-text check: a password field is a
  strong signal on its own, but the sign-in-text check is more general
  (also catches account-creation pages that might not have a password
  field visible in every state) and was already built and already
  correctly matches this exact real page -- reordering existing checks
  is a smaller, more conservative change than adding a new one.

## Consequences

**Positive:**
- Closes a genuinely serious gap: JAAP was auto-filling data into a
  login form under the belief it was the application form -- a
  meaningfully different, higher-stakes mistake than a merely wrong
  label, since the *page itself* was misidentified, not just a field
  within it.
- Confirmed against a full, realistic reproduction of the exact
  real-world scenario (posting -> modal -> Apply Manually -> login page
  with real fields), not just the isolated symptom.
- `--interactive`'s own value is now clearer: with this fix,
  `AuthenticationRequiredError` will actually be raised (and the pause
  prompt will actually appear) the next time this exact tenant is
  validated, rather than silently succeeding on the wrong page.

**Trade-offs:**
- This still has not been verified against a real, past-the-wall
  Workday application form -- ADR-0033's own open gap remains open.
  This fix makes it *more likely* the next validation attempt correctly
  reaches (or correctly reports being blocked from) the real form,
  rather than silently mistaking the sign-in page for it, but does not
  itself resolve that gap.
- The sign-in-text pattern is still a general heuristic (see ADR-0031's
  own caveat); a different Workday tenant's sign-in page phrased
  differently could in principle still evade it. No new evidence has
  emerged to suggest this, but it is not ruled out.

## References

- ADR-0031 -- the original sign-in-wall detection this fix reorders the
  check around, not replaces.
- ADR-0033 -- the `data-automation-id` requirement whose interaction
  with Workday's own sign-in form is what this ADR's finding is about.
- ADR-0034 -- `--interactive`, whose first real use is what surfaced
  this finding.
