# ADR-0011: Resume Upload — Synonym-Gated File Matching, Fast Failure on Missing Files

## Status

Accepted — 2026-07-09

## Context

Milestone 11 needed to attach a selected `Resume`'s file to a detected
file-upload field, extending Milestone 10's autofill engine. Two things
needed real, not assumed, answers: how Playwright actually behaves when
asked to upload a nonexistent file, and how to avoid the correctness bug
of blindly uploading a resume into any file input a page happens to have
(cover letter, portfolio, transcript uploads all use the same HTML
element).

## Decisions

### 1. `BrowserAutomationEngine.upload_file(selector, file_path)`, validated before calling into Playwright

Named for this project's own vocabulary, not Playwright's
(`set_input_files`) -- consistent with how `check()` already diverges
from Playwright's separate `check`/`uncheck` methods (ADR-0010).

Tested directly against a real browser before deciding how to handle a
missing file: Playwright's `set_input_files()` does not fail fast for a
nonexistent path -- it waits the full default 30-second timeout, and the
resulting error message doesn't mention the file at all
(`"Timeout 30000ms exceeded... waiting for locator"`, even though the
locator itself resolved successfully many times over). This is actively
misleading, not just slow. `PlaywrightBrowserEngine.upload_file()`
therefore checks `file_path.exists()` itself, before calling into
Playwright, and raises `BrowserAutomationError` immediately with a clear
message if the file is missing.

### 2. File-upload fields are matched ONLY by an explicit resume synonym on the field's name or label -- never by `field_type == "file"` alone

A real application form can have file uploads for a cover letter,
portfolio, or transcript in addition to (or instead of) a resume.
Matching any `type="file"` input unconditionally to the selected resume
would be a correctness bug -- silently uploading a resume into a cover
letter field -- not merely an over-eager match. `ExactFieldMatcher`
therefore requires the field's normalized name or label to be in a
small, explicit `_RESUME_SYNONYMS` set (`resume`, `cv`,
`resume-upload`, etc.) before it will match a file input at all,
regardless of whether a resume is available. This is verified directly
by a test asserting a field labeled "Cover Letter" is left unmatched
even when a resume is present and even though it's also a file input --
the critical case this decision exists to prevent.

### 3. `FieldMatcher.match()`'s signature gains a `resume: Resume | None = None` parameter

Resume-matching is conceptually the same responsibility as matching
full_name/email/phone against detected fields -- just a different data
source (a file path) and a different target action (`upload_file()`
instead of `fill()`) -- so it belongs in the same `match()` call rather
than a second mechanism a caller has to remember to invoke separately.
This is a breaking change to `FieldMatcher`, an interface introduced in
Milestone 10; flagged explicitly since `ExactFieldMatcher` was, at the
time, its only implementation and consumer, making this a safe and
inexpensive point to make the change.

### 4. `AutofillApplicationUseCase` gains `ResumeRepository` and an optional `resume_id` parameter on `execute()`

Directly reverses ADR-0010's decision #8 ("does not depend on
ResumeRepository"), which explicitly named this as Milestone 11's
separate concern -- arriving on schedule, not a contradiction. If
`resume_id` is provided but doesn't resolve, raises the existing
`ResumeNotFoundError` (introduced in Milestone 7 for
`AttachResumeToApplicationUseCase`, reused here rather than duplicated).
If `resume_id` is omitted, any file-upload fields present are simply
left unmatched -- correct, expected behavior, not an error, since not
every autofill run necessarily has a resume to offer.

## Alternatives Considered

- **Matching any `type="file"` input to the resume unconditionally.**
  Rejected outright; see decision #2 -- this is the specific
  correctness bug this milestone's design exists to avoid.
- **A separate method/mechanism for resume-matching**, kept out of
  `FieldMatcher.match()`. Rejected; see decision #3 -- it's the same
  kind of decision as the other matching rules, just with a different
  data source and action.
- **Letting Playwright's own timeout/error surface for a missing file**,
  treating the 30-second wait as acceptable. Rejected; see decision #1
  -- both the delay and the misleading message were judged unacceptable
  once actually observed against a real browser.

## Consequences

**Positive:**
- A resume can never be silently uploaded into the wrong file-upload
  field, even on forms with multiple file inputs -- verified end-to-end
  against a real page with both a resume field and a cover-letter field
  present simultaneously.
- A missing resume file fails in under a second with a message that
  actually says what's wrong, instead of a 30-second wait ending in a
  misleading timeout.
- `AutofillApplicationUseCase.execute()`'s `resume_id` parameter being
  optional means callers with no resume to offer (or forms with no file
  upload at all) don't need special-case handling -- it's simply `None`.

**Trade-offs:**
- `_RESUME_SYNONYMS` is small and explicitly not exhaustive, the same
  trade-off already accepted for the other synonym sets in
  `ExactFieldMatcher` (ADR-0010) -- a real form using an unrecognized
  label (e.g. "Attachment" with no further context) will leave its
  resume field unmatched, correctly conservative but requiring the
  synonym set to grow as real gaps are found.

## References

- ADR-0010 -- `ExactFieldMatcher`'s conservative matching philosophy and
  decision #8 (deferring `ResumeRepository`), both directly extended here.
- ADR-0008/0009 -- the exception-translation and generic-engine-primitive
  patterns `upload_file()` follows.
