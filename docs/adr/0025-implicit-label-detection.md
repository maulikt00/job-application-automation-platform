# ADR-0025: Implicit Label Detection — the First Fix Driven by a Real, Live Site

## Status

Accepted — 2026-08-27

## Context

Following the post-Phase-4 checkpoint review, real-world validation
against a live Lever demo posting (`jobs.lever.co/leverdemo`) began.
This is worth stating plainly: every prior connector decision in this
project (Milestones 20-23) was grounded in each platform's own published
documentation, API examples, or general automation-community knowledge
-- verified against real sources, but never against an actual, live,
rendered application form. This ADR is the first fix in the project's
history driven by touching a real site directly.

The `jaap application review` run against a real Lever posting worked
correctly at the mechanical level -- the connector was detected
(`"Detected platform: lever"`), navigation to `/apply` succeeded, and
`name`/`email` were correctly autofilled from the profile. But the
review report showed `label: None` for nearly every other field,
including ones with clearly visible labels in the real page
("Full name", "Pronouns", "Email"). Diagnosing this required pulling
the actual rendered HTML from the live form, not guessing at it.

## Decisions

### 1. `PlaywrightFormFieldDetector`'s label detection gained a fourth priority level: implicit `<label>` wrapping

The real HTML captured from Lever's live form:

```html
<label><div class="application-label">Full name<span class="required">✱</span></div>
  <div class="application-field"><input name="name" ...></div></label>
```

The input is wrapped *inside* the `<label>` element -- a standard,
valid HTML pattern (implicit association), distinct from the
`<label for="id">` pattern (explicit association) the detector already
checked. The detector previously checked only `label[for=id]`,
`aria-label`, and `placeholder`, in that order -- missing implicit
wrapping entirely, which is why "Full name"/"Email"/each pronoun
checkbox's answer text all came back `None`. `labelFor()` now also
checks `el.closest("label")` (after the explicit check, before
`aria-label`), covering both real HTML association mechanisms rather
than just one.

This is not a Lever-specific fix -- it is a correction to a real,
general gap in the generic detector's understanding of standard HTML,
found via one real platform but applicable to any site using the
equally common implicit pattern.

### 2. Label text extraction strips nested form controls before reading `textContent`

A `<label>` can wrap not just text but the field itself (as Lever's
markup does), or, in general, a `<select>` with many `<option>`
children whose text would otherwise leak into the label. A shared
helper, `textExcludingNestedControls()`, clones the label element,
removes any nested `input`/`select`/`textarea`/`button` descendants,
and reads `textContent` from what remains -- used for both the explicit
and implicit label paths, not duplicated per path.

### 3. A trailing "required" marker glyph (`*` or `✱`) is stripped from the resulting label

Lever renders a `✱` character directly inside the label text for every
required field (confirmed in the real markup above); without stripping
it, labels would read "Full name✱" instead of "Full name". Implemented
as a plain string check (`endsWith` + `slice`), not a regex -- see
decision #5 for why.

### 4. Two genuine bugs were caught while doing this, both from actually running the JS against a real browser rather than only reading the source

- The JS embedded in `_DETECTION_SCRIPT` used `\s` inside a **non-raw**
  Python triple-quoted string, producing a `SyntaxWarning: invalid
  escape sequence` -- harmless at runtime (Python left the sequence as
  literal backslash+s, which happened to still be valid for the intended
  JS regex), but a real code-quality defect. Fixed by declaring
  `_DETECTION_SCRIPT = r"""..."""`, and the full suite was re-run with
  `-W error::SyntaxWarning` to confirm the fix, not just visually inspected.
- An early manual test embedded the `✱` character directly into a
  `data:text/html,...` URL and got back visibly corrupted text
  (`"Full nameâœ±"`) -- not a bug in the detector, but `data:` URLs
  defaulting to a non-UTF-8 interpretation without an explicit charset
  declaration. This is the same underlying category of problem as
  Milestone 20's `data:` URL `#`-fragment trap (ADR-0021 decision #5) --
  a second, different way the same kind of test-harness shortcut can
  silently corrupt results. Resolved by writing the regression tests
  against a real temporary file (`tmp_path`, `<meta charset="utf-8">`)
  instead of a `data:` URL, consistent with every connector test suite's
  established practice since Milestone 21.

### 5. The required-marker stripping is a plain string check, not a regex

An initial implementation used a regex (`/[*✱]\s*$/`). Given decision
#4's `\s`-escaping confusion had just been found and fixed in the same
file, a plain `endsWith`/`slice` check was used instead for this new,
narrow case -- avoiding a second opportunity for the same class of
Python-string/JS-regex escaping mistake to recur, for a check simple
enough not to need a regex at all.

## What remains open, named rather than worked around

The same live Lever form's `eeo[gender]` field (a `<select>`) has **no**
label association at all -- no `label[for]`, no wrapping `<label>`, no
`aria-label`. Its "Gender" text (visible on the real page) is rendered
as a sibling element outside the container this investigation captured.
Fixing this would require a "nearest meaningful preceding sibling text"
heuristic -- a genuinely more fragile pattern than implicit/explicit
label association, with real risk of false positives on other sites.
Not attempted in this fix; left as a stated, open gap rather than a
rushed guess. Also worth noting: EEO self-identification fields
arguably should remain unmatched/requiring human attention regardless of
whether a label can be found for them, given their sensitivity -- a
separate consideration from the pure detection question.

## Alternatives Considered

- **A Lever-specific detector**, mirroring `WorkdayFormFieldDetector`'s
  precedent of a platform-specific detection layer. Rejected: implicit
  label wrapping is a general HTML pattern, not Lever-specific --
  fixing it in the generic detector benefits every connector and any
  future one, not just Lever.
- **Guessing at the `eeo[gender]` sibling-label pattern without further
  evidence.** Rejected; see "What remains open" above.

## Consequences

**Positive:**
- The generic detector now correctly recognizes both standard HTML
  label-association mechanisms, not just one -- a real, general
  improvement surfaced by, but not limited to, Lever.
- Two genuine, unrelated bugs (a Python `SyntaxWarning`, a `data:` URL
  encoding trap) were caught and fixed as a direct result of actually
  running this against rendered output, not just reading source.
- This is now the concrete demonstration that the "stop building new
  architecture, validate against reality" recommendation from the
  post-Phase-4 checkpoint was correct: a single real-site run
  surfaced a real, non-obvious, generally-applicable gap that no amount
  of further speculative design work would have found.

**Trade-offs:**
- The `eeo[gender]`-style fully-unlabeled field remains a real, open gap.
- This fix was validated against one real platform (Lever); Greenhouse
  and Workday's live sites have not yet been checked and may reveal
  their own, different gaps.

## References

- ADR-0009 -- the generic detector's original label-priority design,
  now extended here with a fourth level.
- ADR-0021 -- the `data:` URL `#`-fragment trap this ADR's encoding
  issue is the same underlying category as.
- The post-Phase-4 checkpoint review that recommended real-world
  validation as the top priority before any further Phase 5 work.
