# ADR-0027: Visible-Text-Only Label Extraction — a Fourth Real-World-Validation Finding

## Status

Accepted — 2026-08-28

## Context

Continuing the same Lever validation session as ADR-0025/0026: after
both prior fixes, re-running `jaap application review` completed
successfully and every `eeo[...]` field correctly stayed unmatched with
real, useful labels ("Gender," the full EEOC race-category text,
"Veteran status," etc.) -- confirming both earlier fixes work on the
live site. Two other fields' labels were still badly noisy:

- `resume`: `"Resume/CV ✱ATTACH RESUME/CVCouldn't auto-read resume.Analyzing resume...Success!"`
- `location`: `'Current location No location found. Try entering a different locationLoading'`

Both are clearly several distinct UI-state messages concatenated
together -- a resume-upload widget's "Analyzing resume...", "Success!",
and a location-autocomplete widget's "Loading"/"No location found" text
all being read as part of the label, when only one such message can
actually be visible to a real user at any given moment (the rest are
almost certainly toggled via CSS `display`/`visibility` depending on
upload/typing state).

## Decisions

### 1. Label text extraction now walks the live DOM and filters to visible text only, not a detached clone

The previous implementation (ADR-0025) cloned the label element,
stripped nested form controls, and read the clone's `textContent`.
This cannot distinguish visible from hidden text: a node's computed
style is only meaningful for elements actually attached to the
document's layout tree, and a `cloneNode()` result is not. The new
implementation uses `document.createTreeWalker()` to visit the label's
real, live text nodes directly, rejecting any node whose ancestor chain
(up to and including the label element itself) contains a nested form
control OR an element that isn't currently visible.

Visibility is checked via `el.offsetParent === null` (catches
`display:none`, on the element itself or any ancestor -- a cheap,
single-property check) combined with an explicit
`getComputedStyle(el).visibility === "hidden"` check (since
`visibility:hidden` elements still participate in layout and so are
*not* caught by the `offsetParent` check alone). Both were verified
independently with dedicated tests before being relied on together.

### 2. This fix could not be fully verified against Lever's actual resume/location widget markup, and that limitation is stated directly rather than glossed over

Unlike the implicit-label fix (ADR-0025) or the EEO exclusion
(ADR-0026), the exact real HTML for Lever's resume-upload and
location-autocomplete widgets was not captured directly -- only the
noisy label *output* was observed, not the underlying markup. The fix
here is verified to work correctly against a synthetic reconstruction
built to plausibly match the observed symptom (multiple status
messages, mixed `display:none`/`visibility:hidden`/genuinely-visible),
and the underlying mechanism (visible-text-only extraction) is sound
and general regardless of Lever's exact markup. But whether Lever's
*real* widget's default, unfilled state happens to leave some other
message visible that this synthetic reconstruction didn't anticipate is
not yet confirmed -- that requires re-running the validation against
the live posting again, which is the natural next step after this fix
lands.

## Alternatives Considered

- **Continuing to use a detached clone**, attempting some other way to
  infer "was this visible" without live computed style (e.g., checking
  inline `style` attributes only). Rejected: real sites overwhelmingly
  toggle visibility via CSS classes, not inline styles, so this would
  have missed the actual observed case entirely.
- **Truncating the label to some maximum length instead of filtering by
  visibility.** Rejected: this would treat the symptom (a long label)
  rather than the cause (irrelevant, currently-hidden text being
  included at all), and could just as easily truncate a long but
  entirely legitimate and relevant label.

## Consequences

**Positive:**
- Label extraction is now based on what a human actually sees when
  looking at the real page, not everything textually present in the
  DOM regardless of current visibility -- a more accurate general
  principle for any real site, not just Lever's specific widgets.
- Verified against both real CSS visibility mechanisms found relevant
  during validation (`display:none` and `visibility:hidden`)
  independently, plus a regression test confirming genuinely visible
  sibling text is still included (not over-zealously stripped).

**Trade-offs:**
- As stated in decision #2, this fix's real-world effectiveness against
  Lever's actual resume/location widgets specifically is not yet
  confirmed -- only its correctness against the general mechanism it's
  meant to fix. Re-validation against the live posting is needed to
  close this out with the same confidence as ADR-0025/0026's fixes had
  once confirmed.

## References

- ADR-0025 -- the implicit-label-wrapping fix this one extends (label
  text now filtered for visibility regardless of whether it came from
  the explicit or implicit association path).
- ADR-0026 -- the other two fixes from the same validation session,
  both confirmed working against the live site; this ADR's honest
  caveat in decision #2 is offered by contrast with that stronger
  confirmation.
