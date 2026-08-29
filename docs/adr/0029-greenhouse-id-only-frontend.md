# ADR-0029: A Second, Structurally Different Greenhouse Frontend — `id`, Not `name`

## Status

Accepted — 2026-08-28

## Context

After ADR-0028's polling fix, re-running `jaap application review`
against the same live Greenhouse posting
(`job-boards.greenhouse.io/remotecom/jobs/7774935003`) failed with the
identical error as before. Diagnosis this time required a genuine,
iterative investigation rather than a single fix: three targeted
diagnostic scripts were run directly against the live page (not
guessed at) before the actual cause was found.

1. **Iframe check**: zero iframes on the page -- ruling out ADR-0021's
   known embedded-integration limitation.
2. **Wait-longer check**: polled for 20 seconds with no click at all;
   the form never appeared. This ruled out "the poll window is just too
   short" as the explanation.
3. **Click-and-wait check**: confirmed a real, clickable `<button>`
   containing the text "Apply" exists, and clicking it produced no URL
   change and no `input[name="first_name"]` even after a further 10
   seconds -- but a raw dump of `document.body.innerText` after the
   click showed the actual application form's surrounding page content
   (job title, "About Remote," etc.), suggesting the form itself likely
   *had* rendered, just not detected.
4. **Field dump (the actual answer)**: dumping every real
   `input`/`select`/`textarea` element after the click showed 49 real
   fields -- `id="first_name"`, `id="last_name"`, `id="email"`, and so
   on -- with **`name: None` on every single one**, no exceptions.

This is not a click-target problem, not an iframe problem, and not
(only) a timing problem: it is a second, structurally different
Greenhouse frontend implementation, one that never sets a `name`
attribute on any field at all, using `id` exclusively -- confirmed live,
not inferred. `GreenhouseConnector`'s own `_form_is_present()` check
(`input[name="first_name"]`, taken from Greenhouse's own API
documentation in ADR-0021) could never succeed against this variant,
regardless of how long it polled, since the attribute it checks for
simply isn't present on this frontend.

## Decisions

### 1. `_FIRST_NAME_FIELD_SELECTOR` now checks both `name` and `id`

`'input[name="first_name"], input#first_name'` -- a single CSS selector
with both alternatives, rather than two separate checks. Verified
against a direct reproduction of the real `id`-only, no-`name` markup
found live.

### 2. `get_field_detector()` needed no change at all

The generic `PlaywrightFormFieldDetector`'s own `selectorFor()` already
checks `el.id` before `el.name` (an existing, older design choice, not
something added for this fix) -- so it already computes `#first_name`
correctly for this newer frontend variant, with zero changes needed.
This was verified directly, not assumed: a dedicated test confirms
`get_field_detector()` returns correctly-selectored, correctly-labeled
fields (via `aria-label`, since there's no `<label for>` or wrapping
`<label>` in this variant either) against the exact `id`-only structure.

### 3. `ExactFieldMatcher` also needed no change -- verified, not assumed

Given every field's `name` is `None` on this frontend, and the real
email field's `type` attribute is `"text"` (not `"email"`, confirmed in
the live dump) -- neither the structural type check nor a name-based
synonym check could fire for it. Whether the *label*-based synonym
check (`label_slug in _EMAIL_SYNONYMS`) would still succeed via
`aria-label="Email"` was checked directly in the matcher's own source,
then confirmed with a new regression test built from this exact
scenario (`name=None`, `label="Email"`) -- it does. No code change was
required here; this decision is recorded because it was a real
question worth answering with evidence, not an assumption to skip past.

### 4. `first_name`/`last_name` remain correctly unmatched -- a pre-existing, documented limitation, not a new gap

`ExactFieldMatcher`'s own module docstring already states it does not
split `Profile.full_name` into first/last parts, "doing so would itself
be guessing which part maps to which." This was true before this
session and remains true after -- restated here only so it's clear that
fixing the navigation bug does not, and was never expected to, make
Greenhouse's split-name fields auto-fillable. They will correctly appear
in the "needs your manual review" list.

## Alternatives Considered

- **Assuming the click-target diagnostic's inconclusive result meant a
  deeper click-handling bug**, and attempting to fix
  `engine.click("text=Apply")` itself. Rejected once the field dump
  showed the click had, in fact, worked correctly all along -- the
  click was never the problem; the presence-check selector was.
- **Splitting `Profile.full_name` to also fill `first_name`/`last_name`
  as part of this fix.** Rejected; out of scope for this specific bug,
  and already a deliberate, documented non-goal of `ExactFieldMatcher`
  for good reason (ambiguous name-splitting is itself a form of
  guessing this project has consistently avoided).

## Consequences

**Positive:**
- `GreenhouseConnector` now correctly recognizes a second, real,
  structurally different frontend implementation Greenhouse serves
  under the same domain this connector already matched -- found and
  fixed through genuine, iterative, evidence-based debugging against a
  live site, not guesswork.
- Confirmed, not merely hoped, that the generic detector and matcher
  already generalize correctly to this variant with zero changes --
  itself a small piece of evidence that the underlying architecture
  (checking `id` before `name`, matching via label as well as name) was
  designed robustly enough to survive an assumption about the target
  platform turning out to be incomplete.

**Trade-offs:**
- `email` should now genuinely auto-fill on this posting; `first_name`/
  `last_name` will not, by pre-existing design -- worth being explicit
  about so this isn't mistaken for a remaining bug once re-validated.
- It is not yet known whether this `id`-only variant is specific to this
  one company's Greenhouse configuration or represents a broader,
  newer Greenhouse frontend rollout -- only re-validation against
  further real postings would clarify that.

## References

- ADR-0021 -- `GreenhouseConnector`'s original design, based on
  Greenhouse's own documented (older) frontend structure.
- ADR-0028 -- the polling fix from the same overall validation effort,
  confirmed still correct and necessary; this ADR's fix is additive to
  it, not a replacement.
- `application/services/field_matcher.py`'s own module docstring -- the
  pre-existing "does not split full_name" design decision restated
  here for clarity, not newly introduced.
