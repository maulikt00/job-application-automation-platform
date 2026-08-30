# ADR-0037: First/Last Name Splitting — Deliberately Narrow, By Explicit Request

## Status

Accepted — 2026-08-30

## Context

`ExactFieldMatcher`'s own module docstring had, since Milestone 10,
stated a deliberate non-goal: never split `Profile.full_name` into
first/last parts, since guessing which part maps to which is itself a
form of guessing this project's whole matching philosophy avoids. This
limitation was confirmed real on two separate platforms during
real-world validation -- Greenhouse's split `first_name`/`last_name`
fields (ADR-0029) and Workday's `legalName--firstName`/
`legalName--lastName` (ADR-0036) -- both correctly left unmatched.

After the second confirmation, the project owner made an explicit,
informed choice: they will only ever enter a name in the simple "First
Last" form (exactly two words), and asked for splitting to be built for
that specific case. This is a real, bounded scope decision, not a
reversal of the original non-goal -- the original concern (ambiguity in
how to split more complex names) remains completely valid and is
explicitly preserved in what this feature does NOT attempt.

## Decisions

### Splitting is implemented, but only for the exact two-token case

`_split_full_name()` splits on whitespace and returns a `(first, last)`
tuple only when there are **exactly two** resulting tokens. A name with
zero, one, three, or more tokens (a single stage name, a middle name,
multiple last/family names, non-Western name ordering) returns `None`,
and any first/last-name field is then left unmatched -- exactly the
same safe fallback as any other unrecognized field. This is not an
approximation of general name-parsing; it is a precise implementation
of the one case explicitly requested, with everything else deliberately
left alone.

### Two small, generic synonym sets, matched against both name and label

`_FIRST_NAME_SYNONYMS` (`first-name`, `firstname`, `given-name`,
`givenname`) and `_LAST_NAME_SYNONYMS` (`last-name`, `lastname`,
`family-name`, `familyname`, `surname`) -- checked against both a
field's `name` and `label`, exactly like every other synonym set in
this matcher. Verified directly against both real-world field
structures that motivated this feature: Greenhouse's `name="first_name"`
matches directly by name; Workday's `name="legalName--firstName"` does
NOT match by name (its own internal naming convention doesn't fit any
generic synonym), but its label ("First Name") does -- the same
label-based fallback path already proven necessary for Greenhouse's own
no-`name`-attribute fields (ADR-0029). No platform-specific name
patterns (e.g. `legalname-firstname`) were added; relying on the label
match kept the synonym sets small and generic, consistent with every
other set in this file.

## Alternatives Considered

- **General name-parsing** (handling middle names, prefixes/suffixes,
  non-Western ordering). Explicitly discussed and declined: this is a
  genuinely different, harder problem than what was requested, and
  building it now would reintroduce exactly the guessing this matcher
  has always avoided, for names the project owner stated they will
  never actually use.
- **A configurable/pluggable name-splitting strategy**, anticipating a
  future need for more complex splitting. Rejected as premature: no use
  case for it exists yet, and this project has consistently preferred
  building the smallest mechanism the current, real need calls for.
- **Adding Workday's specific `legalname-firstname`-style name pattern**
  to the synonym set directly, avoiding reliance on the label. Rejected:
  the label-based match already works, is more general (would also
  cover a differently-prefixed field on some other Workday tenant, or a
  future platform), and avoids growing the synonym set with
  increasingly platform-specific entries.

## Consequences

**Positive:**
- Real fields confirmed on two independent platforms (Greenhouse,
  Workday) are now genuinely autofillable, for the person's actual,
  stated use case, closing a real, concrete gap discovered during
  validation.
- The original safety concern behind the non-goal is fully preserved:
  a name that isn't exactly two tokens is never guessed at, verified
  directly with both a single-word and a three-word name.

**Trade-offs:**
- This does not, and is not intended to, help anyone whose name isn't
  exactly two space-separated tokens -- a real, accepted limitation
  given the project owner's own stated, narrow use case, not a general
  capability this project now claims to have.

## References

- ADR-0029 -- Greenhouse's first observation of this limitation, and
  the label-based fallback pattern this feature reuses.
- ADR-0036 -- Workday's confirmation of the same limitation on a real
  form, and the direct prompt for this feature.
- `application/services/field_matcher.py`'s own module docstring -- the
  original non-goal this ADR narrows, not reverses.
