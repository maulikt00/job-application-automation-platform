# ADR-0030: Reported Field Name Falls Back to `id` — a Fifth Real-World-Validation Finding

## Status

Accepted — 2026-08-28

## Context

Re-running `jaap application review` after ADR-0029's fix (recognizing
Greenhouse's `id`-only frontend variant) completed successfully and
correctly auto-filled `email`. But the printed report showed `None` as
the identifier for every single field, including the successfully
matched one (`None = 'mthakar041@gmail.com'`) -- and several rows had
`label: None` as well, leaving genuinely nothing to identify some
fields by at all. A human reviewing this report has no way to know
which specific field on the real page a bare `"None (label: None)"`
entry refers to.

The root cause is simple, and directly follows from ADR-0029's finding:
`DetectedField.name` was populated from `el.name` only, with no
fallback -- and this Greenhouse frontend variant never sets `name` on
any field, using `id` exclusively.

## Decisions

### `_DETECTION_SCRIPT` now falls back to `el.id` when `el.name` is absent

`name: el.name || el.id || null` -- matching `selectorFor()`'s own
existing priority (`id` checked before `name` there too), so a field's
reported identifier is now consistent with whatever attribute actually
targets it. Verified directly: an `id`-only field now reports that `id`
as its name; a field with a real `name` attribute is unaffected even
when it also has a different `id`; a field with neither still correctly
reports `None`.

**Checked for safety before relying on it**, not just applied
optimistically: this change also affects `ExactFieldMatcher`'s own
`name_slug` computation, since matching and reporting share the same
`DetectedField.name` field. Confirmed this introduces no new,
unintended matches for the concrete fields observed on the real
Greenhouse page: `id="first_name"`/`id="last_name"` do not appear in
`_FULL_NAME_SYNONYMS` (which only recognizes combined-name synonyms,
consistent with `ExactFieldMatcher`'s existing, deliberate choice not to
split `full_name` -- restated in ADR-0029), so this fix does not change
which Greenhouse fields get auto-filled versus left for manual review,
it only improves how the *unmatched* ones are identified in the report.

## Alternatives Considered

- **Reporting the CSS selector itself in the CLI's printed output**,
  rather than changing what `DetectedField.name` contains. Rejected:
  the selector (`#first_name`) is arguably even more useful than the
  bare attribute value for a technical reader, but changing the CLI's
  print format for every field, everywhere, is a larger and less
  targeted change than fixing the underlying identifier at the source
  that's actually missing it -- and every existing connector/detector
  test asserts against `field.name`, not a printed selector string.
- **Only fixing this in the CLI's print formatting** (e.g., "use
  selector if name is None"), leaving `DetectedField.name` itself
  unchanged. Rejected: this would fix only the CLI's specific report
  formatting, not the same underlying gap for any future consumer of
  `DetectedField` (a future presentation surface, a future connector's
  own logic) that also reasonably expects `.name` to be a meaningful
  identifier when one exists at all.

## Consequences

**Positive:**
- The CLI's "needs your manual review" report is now actually readable
  for this real frontend variant -- every field that has *either* an
  `id` or a `name` now shows a real identifier, closing the specific gap
  that made several rows on the live Greenhouse posting completely
  unidentifiable.
- Verified not to change any matching outcome for the concrete fields
  this session found -- a genuine safety check performed before relying
  on the fix, not an assumption.

**Trade-offs:**
- In principle, a field whose `id` happens to coincidentally match a
  recognized synonym (unlike this session's specific observed fields)
  could now match via that `id`-derived name where it previously
  wouldn't have. This is treated as an acceptable, symmetric risk with
  `name`-based matching, which this project has always accepted as a
  small, explicit, human-reviewable synonym set -- not a new category of
  risk introduced by this fix.

## References

- ADR-0029 -- the id-only Greenhouse frontend finding this fix directly
  follows from and completes.
- `application/services/field_matcher.py`'s own module docstring -- the
  small, explicit synonym-set philosophy this fix's safety reasoning
  relies on.
