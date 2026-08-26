# ADR-0019: Resume Recommendation — Label Comparison, Not Content Comparison

## Status

Accepted — 2026-07-09

## Context

Milestone 18, closing out Phase 3, builds `RecommendResumeUseCase`: the
third real use-case-level consumer of `AIProvider`, and the sharpest
version yet of a limitation named honestly since Milestone 16. `Resume`
is a `label` plus a file path — this project has no resume-text-
extraction capability, so there is no parsed resume content anywhere an
LLM could read. Recommending "which resume best fits" therefore cannot
mean "which resume's actual qualifications best fit" — it can only mean
"which resume's short, human-chosen label best matches this job's title
and company." This ADR names that precisely rather than let the
feature's name imply more than it delivers.

A second, unrelated design question needed resolving too:
`AIProvider`'s interface is exactly one primitive, `generate_text() -> str`
(ADR-0014) — there is no structured-output method. Reliably extracting
*which specific resume* an AI response is recommending from free text
needed a concrete parsing strategy, not just "read the text and hope."

## Decisions

### 1. The recommendation compares resume labels against job title/company only — stated in the use case's own docstring and system prompt

`RecommendResumeUseCase`'s module docstring states this limitation
directly, and the system prompt sent to the AI states it too ("You can
only see each resume's short label... you cannot see the actual content
of any resume"), so the limitation is visible both to whoever reads the
code and, implicitly, to what the AI itself is told about its own task.
`ResumeRecommendation` (the return type) always includes the AI's
reasoning alongside the chosen resume, so a human reviewing the
suggestion can see *why* -- especially important here given how little
the recommendation is actually based on.

### 2. Zero and one-resume cases never call the AI

If a `Profile` has no saved resumes, `NoResumesAvailableError` (a new
exception, distinct from `ResumeNotFoundError`'s "specific ID doesn't
resolve" scoping) is raised immediately. If exactly one resume exists,
it's returned directly with reasoning `"Only resume available."` -- no
AI call, since there's no genuine choice to make. The AI is consulted
only when there are at least two resumes to choose between. This
avoids spending an API call (cost, latency) on a forced answer with only
one possible outcome.

### 3. A strict, minimal response format, parsed deterministically

The system prompt requires the AI's response to be exactly: the chosen
option's number alone on the first line, a blank line, then reasoning.
`_parse_choice()` parses only the first line as an integer and validates
it falls within the actual number of resumes offered; anything else
raises `ValueError` with the full response included in the message, so
a malformed response is diagnosable rather than silently
misinterpreted. `_parse_reasoning()` is deliberately more lenient
(falls back to "everything after the first line" if no blank line is
found) since reasoning text is explanatory, not load-bearing the way the
choice number is -- a minor formatting deviation there shouldn't fail
the whole recommendation.

`ValueError` was chosen for parsing failures, not a new exception class,
matching the existing precedent for this exact category of failure in
this codebase (`BrowserAutomationEngine.evaluate()`'s JSON round-trip
check already raises plain `ValueError` for "the data I got back doesn't
parse the way I need it to").

### 4. `ResumeRecommendation` is a small, justified Pydantic model, not a bare tuple or bare string

`recommended_resume: Resume` + `reasoning: str`. Unlike
`GenerateCoverLetterUseCase`/`GenerateAnswerUseCase` (which return a
plain `str`, per ADR-0006/0017/0018's "no DTO without a concrete need"),
this use case's output is genuinely two related pieces of information a
caller needs together -- which resume, and why -- so a small structured
type is the smallest correct representation here, not an unnecessary
abstraction.

### 5. CLI: `jaap resume recommend`, read-only, no `--save-as`-style flag

Unlike `cover-letter generate`/`answer generate`, there is nothing to
save here -- the "recommendation" doesn't create new data, it points at
an existing `Resume`. The CLI prints the recommended resume, the
reasoning, and an explicit reminder that this is label-based, not
content-based, before suggesting the existing
`jaap application attach-resume` command as the next step if the human
agrees.

## Alternatives Considered

- **Asking the AI to respond with the resume's label** (a string) rather
  than a number, then matching by substring. Rejected: label text could
  plausibly be a substring of another label (e.g. "Backend" vs "Backend
  Senior"), making this a genuinely more fragile parse than a bounded
  integer index into a list this project fully controls.
- **A new dedicated exception for parsing failures** (e.g.
  `AIResponseParsingError`). Rejected; see decision #3 -- `ValueError`
  already covers this exact category of failure elsewhere in this
  project.
- **Always calling the AI, even for 0/1 resumes**, for implementation
  uniformity. Rejected; see decision #2 -- there's no reason to spend an
  API call on a forced or impossible answer.
- **Pulling resume file content via some ad-hoc text extraction** just
  for this milestone, to make the recommendation genuinely
  content-aware. Rejected as out of scope: real resume-text-extraction
  (handling PDF/DOCX parsing robustly) is a meaningfully larger feature
  than "recommend a resume," and this project has never built it.

## Consequences

**Positive:**
- The recommendation is honestly scoped to what it can actually deliver,
  both in code comments and in what the AI itself is told, rather than
  implying a deeper qualifications match that doesn't exist.
- Zero wasted API calls for the two cases (no resumes, one resume) where
  there's no real decision to make.
- Parsing failures are diagnosable (the full response is included in the
  raised error) rather than silently producing a wrong recommendation.

**Trade-offs:**
- The feature's real value is genuinely limited by how descriptive a
  user's resume labels happen to be -- a resume labeled "Resume 2" gives
  the AI nothing useful to compare against a job title, and no amount of
  prompt engineering fixes that. This is inherent to the label-only
  design, not a bug to fix later without also building real resume-text
  extraction.

## References

- ADR-0016/0017/0018 — the running theme of naming this project's lack
  of resume-text-extraction honestly, continued here in its sharpest form.
- ADR-0014 — `AIProvider`'s single-primitive interface, which is what
  necessitated this milestone's strict-format parsing strategy in the
  first place.
- ADR-0006 — the "no DTO without a concrete need" discipline `ResumeRecommendation`
  is weighed against and found to genuinely warrant, unlike the plain
  `str` returns of Milestones 16/17.
