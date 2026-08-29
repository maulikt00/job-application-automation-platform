# ADR-0033: Field-Presence Check Was Too Weak Against Real Site Chrome

## Status

Accepted — 2026-08-29

## Context

Continuing NVIDIA Workday validation after ADR-0032's click-timing fix,
`jaap application review` reported completing successfully with 13
"needs review" fields -- but every single one was unrelated to any job
application: a nav search box (`q`), a country selector, and several
OneTrust cookie-consent widget checkboxes (`ot-group-id-C0002`, etc.).
None of these came from a Workday application form at all.

The root cause: `_field_present()`'s check
(`document.querySelector('input, [role="combobox"]') !== null`) matches
*any* input or combobox anywhere on the page. A real corporate site's
job posting page -- before any Apply interaction happens at all -- can
easily have several genuinely unrelated form-like elements already in
the DOM (a header search box, a cookie-consent banner, a locale
selector). On NVIDIA's posting, this caused the check to report "form
found" immediately, meaning the connector likely never even attempted
the Apply flow this run, and the "review" that appeared to complete was
never looking at an application form in the first place.

This is a more foundational bug than ADR-0028/0029/0032's findings: it
affects the very first thing `navigate_to_application_form()` checks,
before any of the later logic even runs.

## Decisions

### `_field_present()` now additionally requires Workday's own `data-automation-id` attribute

`input[data-automation-id], select[data-automation-id], textarea[data-automation-id],
[role="combobox"][data-automation-id]` -- narrowing the check from "any
form-like element" to "a form-like element carrying Workday's own
automation-id marker." This is the same attribute
`WorkdayFormFieldDetector`'s combobox detection already uses (for
reporting a field's name), on the same honest, community-sourced (not
primary-source-confirmed) basis already stated in ADR-0023: Workday is
widely discussed in the automation community as tagging its own
interactive elements this way, but this has not been confirmed against
official documentation the way Greenhouse's/Lever's field structures
were.

Verified against a direct reproduction of the exact real false-positive
(NVIDIA's own observed field names/ids: a search input, cookie-consent
checkboxes, a country selector, none carrying `data-automation-id`) --
the fix correctly rejects all of them, while still recognizing a field
that does carry the attribute.

## An honest limitation this fix does not resolve

**This has still not been verified against an actual, real Workday
application form's markup.** Every real validation attempt so far --
Workday's own careers site (ADR-0031) and NVIDIA's (ADR-0032) -- has hit
the mandatory sign-in wall before ever reaching a genuine form page.
This fix is grounded in the best available evidence (the same
`data-automation-id` convention already used elsewhere, applied
consistently) and in directly ruling out the one real false-positive
this session actually observed, but it remains an informed hypothesis
about real Workday form markup, not a confirmed fact the way
Greenhouse's `name="first_name"` or Lever's `hostedUrl`/`applyUrl`
relationship were. If a future validation attempt against a
non-login-gated Workday tenant reveals real form fields that do NOT
carry `data-automation-id`, this check will need to be revisited with
that new evidence, the same way Greenhouse's own assumptions were
revisited twice (ADR-0028/0029).

## Alternatives Considered

- **Requiring a minimum count of matched fields** (e.g., "5 or more
  inputs anywhere"), rather than a specific attribute. Rejected: the
  real false-positive page had 13 matching elements, well above any
  reasonable small threshold -- a count-based check would not have
  caught this actual failure.
- **Excluding specific known site-chrome patterns** (e.g., ids starting
  with `ot-` for OneTrust, or `nv-` for NVIDIA's own nav). Rejected:
  this would be a brittle, company-specific denylist rather than a
  general fix, and would need constant expansion for every other real
  company's own site chrome conventions.
- **Requiring fields to be inside a `<form>` element.** Considered, but
  rejected in favor of the `data-automation-id` approach: it isn't
  known whether Workday's own React-based UI actually renders its
  application form using a native `<form>` element at all (a common
  thing for modern SPA frameworks to skip), so this could just as
  easily introduce a new, unverified assumption in place of the one
  being fixed.

## Consequences

**Positive:**
- The connector no longer falsely reports "form found" against generic
  site chrome, closing a real, foundational gap that made every prior
  Workday validation result questionable (any apparent "success" could
  have been this same false positive, not a real form).
- The fix is grounded in evidence actually observed this session, not
  a hypothetical guess at what site chrome might look like.

**Trade-offs:**
- As stated above, this remains unverified against real Workday form
  markup -- a genuine, acknowledged gap in confidence, not resolved by
  this fix, only narrowed from "definitely too weak" to "the best
  available guess given current evidence."
- If Workday's real form fields turn out not to use
  `data-automation-id` at all (contrary to the community-sourced
  understanding this and ADR-0023 both rely on), this fix would
  introduce a new false *negative* -- correctly rejecting site chrome,
  but also failing to recognize a real form. This risk is accepted
  given it is currently the best-evidenced hypothesis available, and
  is stated honestly rather than hidden.

## References

- ADR-0023 -- the original, honestly-caveated `data-automation-id` usage
  for combobox naming, whose same confidence basis this fix relies on.
- ADR-0031/0032 -- the sign-in-wall findings that are the reason no real
  Workday form has ever actually been observed by this project.
- ADR-0028/0029 -- Greenhouse's own precedent for an initial assumption
  needing revision once new real evidence appeared, the same posture
  this ADR takes toward its own unverified assumption.
