# ADR-0026: EEO Field Exclusion and Per-Field Fill Resilience — Two More Real-World-Validation Findings

## Status

Accepted — 2026-08-28

## Context

Continuing the same real-world validation session as ADR-0025 (a real
Lever posting, `jobs.lever.co`): after fixing implicit label detection,
re-running `jaap application review` against the same posting produced
a new, more serious failure: an attempt to fill `eeo[disabilitySignature]`
timed out after 30 seconds ("element is not visible"), and the entire
review command aborted -- no report, no screenshot, nothing, despite
every other field on the page having been correctly detected.

Two genuinely separate problems were found here, not one:

1. **A safety problem**: the field being filled at all. `eeo[disabilitySignature]`
   is a voluntary EEO self-identification form's signature line -- a
   legal attestation, not a routine contact field. ADR-0025's own
   implicit-label fix, applied correctly and generally, had the
   unintended side effect of extracting this field's real label ("Full
   Name" -- the standard wording on the U.S. federal CC-305 disability
   self-identification form template) instead of its placeholder
   ("Enter your full name"). `label_slug("full-name")` is an *exact*
   match in `ExactFieldMatcher`'s `_FULL_NAME_SYNONYMS` set, so the
   field was matched and an attempt was made to fill it with the
   applicant's actual name -- automating what should be a deliberate,
   conscious human decision to complete a voluntary disclosure.
2. **A reliability problem**: even setting the safety issue aside, one
   field's fill failure (for any reason -- in this case the field was
   also conditionally hidden until a prior step, hence "not visible")
   should never have been able to abort the entire review and produce
   zero usable output.

## Decisions

### 1. EEO/voluntary self-identification fields are excluded at detection time, not left to depend on label-matching happening to fail

`PlaywrightFormFieldDetector`'s `selectorFor()` now forces `selector = null`
for any field whose `name` attribute starts with `eeo[`, `eeo_`, or
`eeo-` (case-insensitive) -- confirmed against the real, observed Lever
field names (`eeo[gender]`, `eeo[race]`, `eeo[veteran]`, `eeo[disability]`,
`eeo[disabilitySignature]`, `eeo[disabilitySignatureDate]`). This is the
same structural safety pattern already established for Workday's
ARIA-combobox fields (ADR-0023): `selector = null` is an already-tested
invariant (`ExactFieldMatcher` never matches a field with no selector,
verified independently of label text -- see the Milestone 22 test
proving this holds even with a perfectly matching saved `Answer`
available) that makes this a hard guarantee, not something that depends
on every current and future `FieldMatcher` implementation separately
remembering to special-case EEO fields, or on label text happening not
to collide with an ordinary synonym.

The field is still *detected and labeled* -- only its selector is
suppressed -- so it still surfaces in the "needs your manual review"
list with a readable label, rather than disappearing from the report
entirely.

**Honestly scoped**: this pattern (`eeo[...]`) is confirmed for Lever
specifically. Greenhouse and Workday almost certainly have their own
voluntary self-identification sections, under different field-naming
conventions not yet validated against real postings from either
platform -- this exclusion will need extending once that validation
happens, not assumed to already cover them.

### 2. `AutofillApplicationUseCase.execute()` no longer aborts the whole run when one matched field fails to fill

Each `_apply_fill()` call is now wrapped individually; a
`BrowserAutomationError` is caught, logged as a warning (the first real
use of this project's logging infrastructure in the business logic --
configured since Milestone 3, never actually exercised until now), and
the field is demoted from `matched` to `unmatched` rather than
re-raised. Every other successfully-filled field, and the screenshot,
are still produced. Verified with three new tests: one failing field
alongside a succeeding one, one failing field alongside fields already
unmatched for other reasons, and a regression check that the
all-succeed case is completely unaffected by this change.

This is a genuinely general reliability fix, not specific to EEO fields
or to Lever: any real site can have a field that's conditionally hidden,
disabled until a prior step, or otherwise not actionable yet, and the
review command should degrade to "report what we could, flag what we
couldn't" rather than fail entirely.

## Alternatives Considered

- **Fixing only the visibility/timeout symptom** (e.g., checking
  visibility before attempting to fill, or catching the specific
  timeout). Rejected as the primary fix: it would not have addressed
  the more serious underlying issue -- that this field should never
  have been eligible for automatic filling in the first place,
  regardless of whether the fill would have technically succeeded.
- **Relying on `ExactFieldMatcher` to recognize EEO fields by name/label
  and refuse to match them**, rather than excluding them at detection
  time. Rejected in favor of the `selector = null` pattern for the same
  reason ADR-0023 chose it for Workday comboboxes: a structural
  guarantee at the point fields are produced is stronger than a rule
  every matcher implementation must remember to apply correctly.
- **A new `FieldMatchResult` bucket for "matched but failed to fill"**,
  distinct from `unmatched`. Considered, but rejected for now in favor
  of the simpler merge into the existing `unmatched` list -- both
  outcomes mean the same thing to a human reviewing the report ("you
  need to handle this yourself"), and the failure reason is still
  available via the new log warning if deeper diagnosis is ever needed.

## Consequences

**Positive:**
- A legally/ethically sensitive category of field (voluntary EEO
  self-identification) is now structurally guaranteed never to be
  auto-filled, on Lever at least, closing a real gap that a purely
  incidental label-text mismatch had been the only thing preventing
  until this session.
- A single problematic field on a real site can no longer take down an
  entire review run -- a direct, concrete improvement to exactly the
  kind of real-world reliability the post-Phase-4 checkpoint review
  identified as the top priority.
- This project's logging infrastructure (configured since Milestone 3)
  now has its first real use in application logic, for a genuinely
  useful diagnostic purpose.

**Trade-offs:**
- The EEO exclusion pattern is verified for Lever only; Greenhouse and
  Workday's own voluntary self-identification field naming remains
  unvalidated and may need a different or additional pattern once
  checked against their real postings.
- Merging failed-to-fill fields into the same `unmatched` bucket as
  never-matched fields loses the distinction between "we didn't know
  how" and "we tried and couldn't" in the CLI's own printed report --
  available in the log file, but not in the primary user-facing output.

## References

- ADR-0025 -- the implicit-label fix from the same validation session
  whose correct, general behavior is what surfaced this EEO field's
  matchability in the first place.
- ADR-0023 -- the `selector = null` structural safety pattern this
  decision reuses directly, originally established for Workday's
  ARIA-combobox fields.
- ADR-0009/0010 -- the underlying `selector = null` => never-matched
  invariant both this ADR and ADR-0023 depend on.
