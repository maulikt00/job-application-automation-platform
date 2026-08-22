# ADR-0009: FormFieldDetector as a Separate, Composed Component

## Status

Accepted — 2026-07-09

## Context

Milestone 9 needed to add form-field detection capability on top of
Milestone 8's `BrowserAutomationEngine`. The original framing (stated in
ADR-0008 itself, in a forward-looking note) assumed this would arrive as
a new method directly on `BrowserAutomationEngine`. Actually sitting
down to design the method signature surfaced a real problem with that
plan before any code was written: `BrowserAutomationEngine`'s own
docstring already states it "knows nothing about job applications
specifically" -- it's meant to be a generic automation toolkit. Adding
a forms-aware method (one that has opinions about what a "field" is,
how to guess a label, which input types to skip) directly onto that
interface would have coupled a supposedly generic component to
forms-specific domain knowledge, undermining the very genericness
`ARCHITECTURE.md` describes.

## Decisions

### 1. `BrowserAutomationEngine` gains exactly one new primitive: `evaluate(script: str) -> Any`

Not a forms-aware method. `evaluate()` runs arbitrary JavaScript against
the current, live, rendered page and returns its result. This stays at
the same generic level as `navigate()`/`screenshot()` -- it has no
knowledge of forms, fields, or job applications. Running against the
live DOM (not a static HTML snapshot) matters because real application
forms are often JS-rendered SPAs; a static parser would miss content
that only exists after client-side rendering.

The result must be JSON-compatible (`str`, `int`, `float`, `bool`,
`None`, `list`, or `dict`). `PlaywrightBrowserEngine.evaluate()` enforces
this with a JSON round-trip (`json.dumps(result, allow_nan=False)`).
Testing this against a real browser surfaced two things worth recording
precisely, since the obvious assumption about what this check catches
turned out to be only half right:

- Playwright's own serialization already converts genuinely
  non-serializable JS values (DOM node references, functions) into safe
  string placeholders (e.g. `"ref: <Node>"`) before they ever reach
  Python. The round-trip check does not need to guard against a live DOM
  handle leaking out -- Playwright already prevents that at a lower
  layer.
- What the round-trip check actually catches: Python's `json.dumps()`
  permits `NaN`/`Infinity`/`-Infinity` by default (non-standard JSON),
  so a script evaluating to `NaN` would silently pass a naive
  `json.dumps(result)` check. `allow_nan=False` is required to make the
  guard genuinely enforce "JSON-compatible," not just "doesn't raise
  Python's default json.dumps."

### 2. `FormFieldDetector` is a new, separate Protocol, composed with `BrowserAutomationEngine` via constructor injection

Lives in `application/interfaces/form_field_detector.py` alongside
`DetectedField`, the Pydantic model it returns. The concrete
implementation, `PlaywrightFormFieldDetector`
(`infrastructure/browser/form_field_detector.py`), takes a
`BrowserAutomationEngine` in its constructor and only ever calls
`engine.evaluate()` -- it is not a subclass of `PlaywrightBrowserEngine`
and does not import Playwright directly. This mirrors how mappers were
split out from repositories in ADR-0005: a focused, single-responsibility
component composed with a lower-level primitive, not folded into it.

### 3. `DetectedField` is not a domain model

It lives in `application/interfaces/`, not `domain/models/`: it isn't a
persisted business concept, it's structured data flowing from the
browser layer toward a future autofill use case (Milestone 10) -- the
first concrete DTO-shaped consumer since ADR-0006 deferred building DTOs
without one.

### 4. Label priority and exclusions, as designed

Label-guessing priority: an associated `<label for="...">` element's
text, then `aria-label`, then `placeholder`, then `None`. Excluded from
detection entirely: `type="hidden"`, `disabled` elements, and
button-like input types (`submit`, `button`, `reset`, `image`) -- none
of these are user-fillable fields, and a submit button appearing in
"fields to fill" would be actively wrong, not just noise.

### 5. Checkbox/radio `current_value` is `"true"`/`"false"` reflecting `.checked`, not the HTML `value` attribute

A checkbox's HTML `value` attribute is unrelated to whether it's
checked (it's the value submitted *if* checked, often left as the
browser default `"on"`) -- reporting that as `current_value` would be
actively misleading for an autofill engine that needs to know the
field's actual current state.

## Alternatives Considered

- **Adding form-field detection as a new `BrowserAutomationEngine`
  method.** This was the original plan, stated in ADR-0008, and
  rejected once actually designing the method signature made the
  coupling problem concrete. Recorded here specifically because it's a
  real course-correction, not a hypothetical alternative -- worth being
  honest that the plan changed between milestones rather than silently
  building something different from what was previously documented.
- **A static HTML parser** (e.g. BeautifulSoup against `page.content()`)
  instead of live-DOM JavaScript evaluation. Rejected: real application
  forms are frequently JS-rendered SPAs, and a static snapshot would
  miss fields that only exist after client-side rendering.
- **Reporting a checkbox's HTML `value` attribute** as `current_value`.
  Rejected; see decision #5.

## Consequences

**Positive:**
- `BrowserAutomationEngine` remains genuinely generic -- verified by the
  fact that `PlaywrightFormFieldDetector` never imports Playwright and
  would work unmodified against any other conforming engine
  implementation.
- Tests run against a real, constructed HTML test page in real Chromium,
  covering every field type, both exclusion categories, all three label
  priority levels plus the no-label case, required state, and
  `current_value` extraction for text/checkbox/select/textarea --
  substantially stronger verification than mocking `evaluate()`'s return
  value would have provided, since the actual risk in this milestone is
  the JavaScript detection logic itself.
- The `NaN`/`allow_nan` finding is now documented precisely rather than
  left as an unexamined assumption about what the JSON round-trip
  guarantees.

**Trade-offs:**
- Every `FormFieldDetector` test launches its own real Chromium instance
  (no shared browser fixture across tests), adding meaningful wall-clock
  time (~20s for this milestone's tests alone) compared to mocking.
  Judged worth it given what real-browser testing catches that mocking
  cannot; revisit if test suite runtime becomes a real constraint later.

## References

- ADR-0008 -- `BrowserAutomationEngine`'s original design and the
  forward-looking note this ADR corrects.
- ADR-0005 -- the mapper/repository split this milestone's
  detector/engine split directly mirrors.
- ADR-0006 -- the "don't build an abstraction without a concrete
  consumer" discipline `DetectedField`'s placement follows.
