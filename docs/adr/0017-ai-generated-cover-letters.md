# ADR-0017: AI-Generated Cover Letters — Exception Translation Resolved, First Real `AIProvider` Consumer

## Status

Accepted — 2026-07-09

## Context

Milestone 16 builds `GenerateCoverLetterUseCase`, the first real
use-case-level consumer of `AIProvider`. This is the exact milestone
ADR-0014/0015/0016 all pointed to when deferring exception translation
for `ClaudeProvider`/`OllamaProvider` -- resolving it here means going
back and modifying already-built Milestone 14/15 code, not just adding
new code, mirroring the identical precedent already set once for
`BrowserAutomationEngine` (built without translation in Milestone 8,
translation added in Milestone 10 once `AutofillApplicationUseCase`
existed).

## Decisions

### 1. `AIProviderError(DomainError)`, added to `domain/exceptions.py`

Same shape as `BrowserAutomationError`. Both `ClaudeProvider` and
`OllamaProvider` now catch their own SDK's exceptions and re-raise this
via exception chaining (`raise ... from exc`), so
`GenerateCoverLetterUseCase` (and any future `AIProvider` consumer)
never needs to know or care whether it's calling Claude or Ollama
underneath just to handle errors correctly -- exactly the property the
interface existed to provide.

### 2. A real, verified asymmetry: the two SDKs needed different translation code

Inspecting both installed SDKs directly (not assumed) found:
Anthropic's SDK shares one common base, `anthropic.AnthropicError`, so
`ClaudeProvider` catches exactly that one class. Ollama's
`RequestError`/`ResponseError` share **no common base beyond bare
`Exception`** -- `OllamaProvider` catches both explicitly as a tuple.
Both providers' test suites were extended with regression tests that
assert the real `__cause__` chain (not just the outer exception type),
confirming genuine translation rather than a superficial wrapper.

### 3. `GenerateCoverLetterUseCase` builds its own prompt and system prompt internally, returns a plain `str`

No DTO (ADR-0006's discipline: no abstraction without a concrete need).
Composes `ProfileRepository`, `JobPostingRepository`, and
`CoverLetterTemplateRepository` (to optionally use an existing template
as a style/structure reference) with the injected `AIProvider`. The
prompt-building logic (`_build_prompt()`) is a private module-level
function, following the exact same reasoning as
`SubmitApplicationUseCase`'s `_build_content_snapshot()` (ADR-0013): one
caller, no anticipated second implementation, no justification for a
class or `Protocol`.

### 4. A real, stated scope limitation: no resume-text-extraction exists in this project

`Resume` is a label plus a file path -- nothing in this codebase parses
a resume file's actual content into text an LLM could reference. The
prompt therefore works only from what's genuinely available (the
applicant's name, the job's company and title, and an optional
existing template), and the system prompt explicitly instructs the
model not to invent specific work history or achievements it was never
given. This is stated plainly in the use case's own module docstring
rather than left as a silent gap discovered later: the result is a
reasonable, adaptable draft, not a deeply personalized letter
referencing the applicant's actual experience -- that would require
resume text extraction, a different, unbuilt feature.

### 5. Never saves anything; the caller decides

`GenerateCoverLetterUseCase` never touches `CoverLetterTemplateRepository.save()`
or `SubmitApplicationUseCase`. It returns generated text for a human to
review, matching the human-review discipline established since
ADR-0001 and made structural in ADR-0012. Verified directly by a test
asserting the template repository remains empty after `execute()` runs.

### 6. CLI: `jaap cover-letter generate` supports `--save-as`, shown-then-optionally-saved in one command

Per explicit confirmation: the generated text is always printed first,
in the same command's output, before any save happens. `--save-as` is
optional -- if given, the same invocation saves the text as a new
`CoverLetterTemplate` via the already-existing `SaveCoverLetterTemplateUseCase`.
This was judged lower-stakes than Milestone 12's "never auto-submit"
boundary: a saved `CoverLetterTemplate` is trivially editable or
deletable afterward, unlike a submitted application.

### 7. A second real gap found and fixed while writing this milestone's CLI guidance

`_handle_generate`'s "not saved" message needed to tell the user how to
use the draft for a one-off submission -- but `jaap application submit`
had no `--cover-letter-text-override` flag at all, despite
`SubmitApplicationUseCase.execute()` supporting that parameter since
ADR-0013. Rather than print guidance referencing a flag that didn't
exist, `--cover-letter-text-override` was added to the `submit` command.
Verified genuinely end-to-end: a real CLI invocation
(`profile create` → `resume add` → seed a `JobPosting` → `application
start` → `attach-resume` → `application submit
--cover-letter-text-override "..."`) followed by querying the resulting
database directly confirmed the override text landed correctly in the
`SubmittedContentSnapshot`.

## Alternatives Considered

- **Pulling Resume file content or existing Answers into the prompt** to
  make the draft more personalized. Rejected for this milestone: no
  resume-text-extraction capability exists, and pulling in `Answer`s
  would broaden this milestone's scope beyond cover letters into
  answer-reuse (Milestone 17's actual territory). Documented as a
  limitation, not silently worked around.
- **A DTO wrapping the generated text** (e.g., with metadata like model
  used, token counts). Rejected; a plain `str` is sufficient for what
  a human reviewing a draft actually needs right now.
- **`generate` only printing, with a mandatory separate `save` command.**
  Rejected per explicit confirmation; see decision #6.
- **Leaving the CLI guidance message referencing a nonexistent flag**,
  planning to add it in a later milestone. Rejected -- a command's own
  help text should never point at something that doesn't work yet.

## Consequences

**Positive:**
- `AIProvider`'s exception-handling story is now complete and uniform:
  any future consumer (Milestone 17/18, or a future third provider) can
  catch exactly one exception type regardless of which provider is
  configured.
- The full generate → review → save-or-override → submit loop was
  proven to work through the real CLI end to end, not just at the unit
  level.
- The resume-text-extraction limitation is now documented precisely
  where a future maintainer would look (the use case's own docstring),
  rather than being an implicit, undiscovered gap.

**Trade-offs:**
- Cover letters generated by this milestone will read as competent but
  somewhat generic, since they cannot reference the applicant's actual
  work history. Improving this meaningfully requires a real, separate
  feature (resume text extraction) not currently planned on the roadmap.

## References

- ADR-0014/0015/0016 — the deferred exception-translation decision this
  milestone resolves.
- ADR-0010 — the original `BrowserAutomationError` precedent
  (Milestone 8→10) this milestone's `AIProviderError` (Milestone 13-15→16)
  directly mirrors.
- ADR-0013 — `cover_letter_text_override`, the mechanism this milestone's
  generated drafts flow into for one-off use.
- ADR-0001/0012 — the human-review discipline `GenerateCoverLetterUseCase`
  follows by never saving anything itself.
