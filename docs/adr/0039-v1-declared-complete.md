# ADR-0039: JAAP v1 — Declared Complete

## Status

Accepted — 2026-08-30

## Context

The post-Phase-4 checkpoint review proposed a specific, concrete
definition of "v1 complete": *a single user can find a real job posting
on one of the three supported platforms, have JAAP correctly autofill
what it can on the actual live page, get a clear, accurate report of
what needs manual attention, and manually finish and submit — with this
proven to work on at least a handful of real postings, not just
synthetic ones.*

This ADR is where that bar is checked against what has actually
happened, and declared met.

## What Was Actually Verified, Platform by Platform

**Lever** (ADR-0025/0026/0027, three real validation rounds against
`jobs.lever.co`): implicit-label detection fixed, a genuinely serious
EEO-signature-field auto-fill risk found and closed structurally
(`selector=None`, unconditional), per-field autofill resilience added
so one bad field can't crash the whole run, and label-extraction
correctly limited to visible text only. Confirmed working: `name` and
`email` correctly autofilled on a real, live posting; every `eeo[...]`
field correctly excluded regardless of label collisions.

**Greenhouse** (ADR-0028/0029/0030, three real validation rounds
against `job-boards.greenhouse.io`): a real timing bug (form-presence
polling), a second, structurally different frontend variant (fields
using `id`, never `name`) found and handled, and a reporting fix
(falling back to `id` for a field's displayed name). Confirmed working:
`email` correctly autofilled via label matching even with no `name`
attribute at all.

**Workday** (ADR-0031 through ADR-0038, the deepest and most eventful
validation line): a mandatory sign-in wall confirmed on two independent
tenants (Workday's own site, NVIDIA's) -- and a firm, explicit
reaffirmation that JAAP will never automate account creation or login,
regardless of the mechanism. A real, working `--interactive`
pause-and-retry mechanism was built and formalized at the
`WebsiteConnector` interface level (not Workday-specific). Along the
way: a click-timing quirk, a field-presence false positive against
generic site chrome, and a genuinely serious confusion between
Workday's own sign-in form and the real application form -- all found
and fixed. **This is the only platform where a real, authenticated
application form was actually reached and fully exercised**, and by the
final validation round, **6 of 6** fields with a natural home in
`Profile` were correctly autofilled: split first/last name, all five
address components, and phone.

## An Honest Caveat, Not Glossed Over

Address, phone, and first/last-name splitting (ADR-0037/0038) were
built *after* Lever's and Greenhouse's own validation rounds concluded.
Their "correctly autofilled" results were verified against the fields
that existed in `Profile` at the time (name as a single field, email) --
not against the fuller profile Workday's later rounds exercised. The
checkpoint bar has been met independently on each platform, but the
*combination* (a complete profile against Lever or Greenhouse
specifically) has not yet been directly re-confirmed. This is
explicitly named as the next, immediate step (see "What's Next" below),
not asserted as already covered.

## What Remains Deliberately Deferred, Not Forgotten

Each of these was found during validation, evaluated, and consciously
left for later rather than overlooked:

- Lever's redundant resume label (cosmetic; safety unaffected).
- Lever's/Greenhouse's custom, per-posting application questions
  (`cards[...]`-style fields) -- genuinely harder, needs more real
  evidence before a responsible fix is possible.
- Workday's ARIA-combobox fields are detected but not fillable
  (ADR-0023's own honest scope boundary, unchanged) -- confirmed still
  present on the real form (`phoneNumber--countryPhoneCode`, etc.).
- Persistent browser sessions across runs, which would reduce (but not
  eliminate) the recurring Workday sign-in cost -- deliberately deferred
  in ADR-0034 pending real usage data, which now exists in limited form
  but has not prompted revisiting this decision.
- Lever's single, combined `location` field has no equivalent match:
  found during the confirmatory validation round with the now-complete
  `Profile`. Not a bug -- Workday's address fields are structured
  (separate `addressLine1`/`city`/`state`/`postal_code`/`country`),
  while Lever's is one free-text field, and the matcher correctly
  declines to guess how to combine several profile fields into one
  string rather than doing something wrong. A real, separate,
  small feature (concatenating address components into a single
  formatted string for this specific shape) if ever revisited.

None of these represent a safety risk or a broken core flow -- they are
scoped, accepted trade-offs, each with its own ADR-documented reasoning.

## Decision

**JAAP v1 is declared complete**, per the checkpoint review's own
stated bar. Active, open-ended gap-hunting across the three connectors
stops here. This does not mean development stops -- see "What's Next"
below -- but it does mean the project has crossed from "validating
whether the core loop works at all" into "a working tool with a known,
bounded set of remaining polish items."

## What's Next

A final, confirmatory validation round: the now-complete `Profile`
(name, email, phone, full address) against a fresh Greenhouse or Lever
posting, to directly close the honest caveat above. Not because either
platform is expected to reveal new problems -- but because "probably
fine" and "directly confirmed" are different things, and this project
has consistently preferred the latter throughout.

## References

- The post-Phase-4 checkpoint review -- the original source of the v1
  bar this ADR checks against.
- ADR-0025 through ADR-0038 -- the full, real-world-validation record
  this declaration rests on.
