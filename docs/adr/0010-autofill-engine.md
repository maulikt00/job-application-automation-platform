# ADR-0010: Autofill Engine — Conservative Matching, No Separate Engine Class, Exception Translation Resolved

## Status

Accepted — 2026-07-09

## Context

Milestone 10 needed to turn Milestone 9's `DetectedField`s into actual
filled-in form values, given a `Profile` and reusable `Answer`s. This
milestone also carried two decisions deferred from earlier ones:
`BrowserAutomationEngine`'s exception translation (deferred in
ADR-0008/0009 pending a real use-case consumer) and, discovered only
while designing the matcher, a real gap in `DetectedField` itself --
nothing computed a reliable way to actually target a detected element
for filling.

## Decisions

### 1. Matching is conservative/exact only -- no fuzzy/similarity scoring

`ExactFieldMatcher` matches only on structural signals (the HTML input
`type` attribute) and exact, normalized string equality (a field's
name/label against a small, explicit synonym set, or a field's label
against an existing `Answer.question_key`). No `difflib`-based
similarity threshold or any other fuzzy scoring. Per
`PROJECT_ROADMAP.md`'s own stated philosophy for this milestone
("unmatched fields surfaced to the user rather than guessed"), a
similarity threshold is itself a form of guessing, just a quantified
one. Anything not confidently, exactly matched is left unmatched.

`Profile.full_name` is never split into first/last parts for forms with
separate name fields -- doing so would itself be guessing which part is
which.

### 2. `DetectedField` gains a `selector` field; fields without one are never matched

`#<id>` if the element has an id (preferred, ids are meant to be
unique), else `[name="..."]` if it has a name, else `None`. A field with
`selector is None` is never matched by `ExactFieldMatcher`, regardless
of how confidently its label would otherwise match -- there would be no
reliable way to act on it safely. This is enforced as the very first
check in `ExactFieldMatcher._match_one()`, before any other matching
logic runs, and verified by a test asserting a field with a
structurally-matchable type (`email`) but no selector is still left
unmatched.

### 3. `BrowserAutomationEngine` gains three action primitives: `fill()`, `check()`, `select_option()`

Still generic -- any web automation needs "fill a field" or "check a
box," not just job applications -- following the same reasoning as
`evaluate()` (ADR-0009). No dedicated "autofill" method on the engine;
these are the same category of generic primitive as `navigate()`.

### 4. Exception translation, deferred twice, resolved now

Every operational method on `PlaywrightBrowserEngine` (`launch`,
`navigate`, `evaluate`, `fill`, `check`, `select_option`, `screenshot`,
`close`) now catches Playwright's own `Error` and re-raises a new
`jaap.domain.exceptions.BrowserAutomationError`, preserving the original
via exception chaining (`raise ... from exc`) -- verified directly by
asserting `exc_info.value.__cause__ is not None` in tests, not just that
the wrapping exception's type is correct. This is exactly the same
pattern as `ReferentialIntegrityError` (ADR-0005): the application layer
(`AutofillApplicationUseCase`, the first real consumer) never needs to
import `playwright.sync_api`. The `RuntimeError` raised by
`_require_page()` (calling an operation before `launch()`/after
`close()`) remains separate and untranslated -- it was never a
Playwright-raised error, it's this project's own programmer-error guard.

**A practical finding worth recording:** testing this exposed that
"element not found" failures (Playwright's default auto-wait behavior)
take the full default 30-second timeout to fail -- far too slow for an
automated test suite. Fast, reliable triggers for a genuine Playwright
error were found instead: invalid JavaScript syntax (fails immediately
on parse, for `evaluate()`) and calling an operation on an element that
exists but is the wrong kind for it (e.g. `check()` on a text input,
`select_option()` on a non-`<select>` element) -- both fail immediately
since Playwright doesn't need to wait for actionability, it can reject
the operation on inspection. Every exception-translation test in this
milestone uses one of these fast triggers, none rely on a timeout.

### 5. No separate "AutofillEngine" class

The dispatch logic deciding `fill()` vs. `check()` vs. `select_option()`
based on a matched field's type is a small, inline `if`/`elif` inside
`AutofillApplicationUseCase._apply_fill()`. Giving this its own
Protocol/implementation pair (mirroring `FormFieldDetector`) was
considered and rejected: unlike form detection (real JavaScript logic
worth isolating and independently testing) or field matching (real
decision logic, and a genuine future extension point for AI), the
fill-dispatch is a three-way type check with no independent complexity
or reuse value to justify the abstraction.

### 6. `FieldMatcher` is a `Protocol`, with a concrete implementation in a new `application/services/` package

`FieldMatcher` follows the same `Protocol` pattern as every other
interface in this project (ADR-0005/0008/0009) -- specifically so a
future AI-assisted matcher (Phase 3's "question answering" capability,
already named in the original project charter) can implement the same
interface without any change to `AutofillApplicationUseCase`.

`ExactFieldMatcher`, the concrete implementation, does not live in
`infrastructure/`. It depends only on domain models and
`application/interfaces/` types -- no database, no browser, no
third-party SDK. `infrastructure/` is specifically for adapters wrapping
external systems (`ARCHITECTURE.md`'s own description); a pure-logic
implementation of an application-layer interface doesn't belong there
just because it happens to implement a `Protocol`. `application/services/`
is a new package for exactly this category: concrete implementations of
application-layer interfaces that have no external dependency.

### 7. `slugify()` extracted to `utils/slugify.py`, shared by `Answer` and `ExactFieldMatcher`

`Answer.question_key`'s normalization regex (Milestone 2) and the
normalization `ExactFieldMatcher` needs for comparing a field's label
against an existing `question_key` are the exact same operation.
Duplicating the regex in two places would risk them silently drifting
apart, breaking "does this field's label match this answer" in a
hard-to-diagnose way. Extracted once, `Answer` now delegates to it --
verified by re-running `Answer`'s existing tests unchanged after the
refactor, confirming no behavior change.

### 8. `AutofillApplicationUseCase` does not depend on `ResumeRepository` or `ApplicationRepository`

Nothing in this milestone's matching rules reads `Resume` data --
resume file upload is Milestone 11's separate concern. Autofilling is
not tied to a specific `Application` record; it operates on the
currently loaded page for a given `Profile`. Adding either dependency
now would be unused surface area, not something this milestone's actual
behavior needs.

### 9. Never submits

There is no code path in `AutofillApplicationUseCase` that could
click a submit button -- it calls `fill`/`check`/`select_option` on
matched fields and returns. Submission remains Milestone 12's human
review gate, unconditionally.

## Alternatives Considered

- **Fuzzy/similarity-based matching** (e.g. `difflib.SequenceMatcher`
  with a threshold). Rejected; see decision #1.
- **A dedicated `AutofillEngine` Protocol/implementation pair**,
  mirroring `FormFieldDetector`. Rejected; see decision #5.
- **Reporting a checkbox's HTML `value` attribute** as its fillable
  value (carried over consideration from ADR-0009, reaffirmed here):
  still rejected, `current_value`/fill target for checkboxes is
  `.checked` state, not the `value` attribute.
- **Letting `ResumeRepository`/`ApplicationRepository` be constructor
  dependencies "for future flexibility."** Rejected; see decision #8 --
  unused dependencies are scope creep, not flexibility.

## Consequences

**Positive:**
- `AutofillApplicationUseCase` never needs to import `playwright.sync_api`
  or `sqlalchemy.exc` -- every dependency it has is a `Protocol`.
- A future AI-assisted `FieldMatcher` implementation is a drop-in
  replacement with zero changes to `AutofillApplicationUseCase`.
- The end-to-end test (`test_autofill_end_to_end.py`) verifies success by
  reading back actual DOM state via a separate `evaluate()` call after
  autofill runs, not by trusting the use case's own report of what it did.

**Trade-offs:**
- The synonym sets (`_FULL_NAME_SYNONYMS`, `_EMAIL_SYNONYMS`,
  `_PHONE_SYNONYMS`) are small and explicitly not exhaustive -- real
  forms will have field names/labels this milestone doesn't recognize,
  by design. Expanding them is safe and additive whenever a real gap is
  found; this is a deliberate "narrow but correct" starting point, not
  a claim of completeness.
- `application/services/` is a new top-level distinction
  (external-dependency-free vs. infrastructure adapter) that didn't
  exist before this milestone -- future contributors need to understand
  this split to know where a new `Protocol` implementation belongs.

## References

- ADR-0005 -- the repository/mapper split and exception-translation
  pattern this milestone's engine/matcher split and
  `BrowserAutomationError` both mirror.
- ADR-0008/0009 -- where exception translation and `DetectedField`'s
  design were left open, resolved here.
- ADR-0006 -- the "don't build an abstraction without a concrete
  consumer" discipline, now demonstrated a third time.
