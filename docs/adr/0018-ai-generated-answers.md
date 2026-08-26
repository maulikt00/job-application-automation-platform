# ADR-0018: AI-Generated Application Answers — Company-Agnostic by Design

## Status

Accepted — 2026-07-09

## Context

Milestone 17 builds `GenerateAnswerUseCase`, the second real
use-case-level consumer of `AIProvider` (after Milestone 16's
`GenerateCoverLetterUseCase`). Before writing any code, a real design
tension needed resolving: the roadmap calls these "reusable-answer
suggestions," and `Answer` has been designed since Milestone 2
specifically for exact-match reuse across many applications
(`ExactFieldMatcher`, Milestone 10) — but `GenerateCoverLetterUseCase`'s
own design takes an optional `job_posting_id` to tailor its output to a
specific employer. Naively copying that pattern here would risk
producing an answer that names a specific company, which would then be
actively wrong the next time that same saved `Answer` gets reused
verbatim for a different one.

## Decisions

### 1. `GenerateAnswerUseCase` takes no `job_posting_id` at all

Unlike `GenerateCoverLetterUseCase`. This is deliberate, not an
oversight: the whole point of this milestone's output is that it's safe
to save and reuse. The system prompt actively instructs the model not
to mention any specific company, employer, or job title, "even if one
is implied by the question" — verified by a test asserting this
instruction is actually present in what gets sent to the provider.

### 2. The Profile's existing saved `Answer`s are passed as context, for consistency only

`AnswerRepository.list_by_profile()` supplies every answer already
saved for this profile, included in the prompt as reference material.
The system prompt is explicit that these are for tone/substance
consistency, not something to copy verbatim, since they answer a
different question. This is new relative to
`GenerateCoverLetterUseCase`, which does not pull in existing content
this way -- a cover letter is a single, whole document; an answer bank
benefits from staying internally consistent across many small, separate
answers.

### 3. Same honest scope limitation as Milestone 16, restated here rather than assumed carried over

No resume-text-extraction capability exists in this project. The
generated answer works only from the Profile's name, the question, and
existing saved answers -- it cannot reference specific, un-stated work
history or achievements. Stated directly in the system prompt and the
use case's own module docstring.

### 4. Same shape as `GenerateCoverLetterUseCase` everywhere else

Plain `str` return, no DTO (ADR-0006). Never saves anything itself,
verified directly by a test asserting the answer repository stays empty
after `execute()` runs (ADR-0001/0012's human-review discipline). No new
exception handling needed -- `AIProviderError` was already resolved for
every `AIProvider` consumer in Milestone 16 (ADR-0017); this use case
simply lets it propagate. Prompt-building is a private module-level
function (`_build_prompt()`), matching the precedent from
`SubmitApplicationUseCase`/`GenerateCoverLetterUseCase` (ADR-0013/0017):
one caller, no anticipated second implementation.

### 5. CLI: `jaap answer generate --save-as <question>` mirrors `cover-letter generate` exactly, with one added detail

`--save-as` takes the literal question text (not a pre-slugified key)
so that passing the same text for both `--question` and `--save-as`
produces a `question_key` that will exactly match what
`ExactFieldMatcher` computes from a real detected field's label later --
verified directly by a smoke test asserting `slugify()`'s output matches
the saved `Answer.question_key` for the same input text. No special
auto-slugify logic was needed in the CLI itself: `Answer.question_key`'s
own field validator (Milestone 2) already normalizes any input string
into the same slug form.

## Alternatives Considered

- **Taking an optional `job_posting_id`**, matching
  `GenerateCoverLetterUseCase`. Rejected; see decision #1 -- this is the
  central design question this ADR exists to resolve.
- **Not passing existing answers as context at all**, keeping the
  design maximally simple. Rejected; see decision #2 -- the consistency
  benefit across a person's growing answer bank was judged worth the
  small added complexity, especially since `list_by_profile()` already
  existed and needed no new repository work.
- **A separate `--save-as-question-key` flag distinct from `--question`**,
  requiring the user to type the question twice in different forms.
  Rejected in favor of decision #5's simpler approach: reusing the same
  literal text for both flags, relying on `Answer.question_key`'s
  existing normalization to make them consistent automatically.

## Consequences

**Positive:**
- Generated answers are genuinely safe to save and reuse across
  different companies, the property the roadmap's own "reusable-answer
  suggestions" wording asked for.
- A person's answer bank can grow more consistent in tone over time, as
  each new generated answer is informed by what's already been saved.
- No new exception-handling work was needed for this milestone --
  Milestone 16 already resolved that fully for every current and future
  `AIProvider` consumer.

**Trade-offs:**
- An answer to a question that genuinely requires a company-specific
  response (rare, but possible -- e.g. "what do you know about our
  specific product line?") is out of scope for this use case by design;
  such a question would need to be answered manually, or via
  `GenerateCoverLetterUseCase`'s tailored approach if the content were a
  cover letter rather than a short-answer question.

## References

- ADR-0017 — `GenerateCoverLetterUseCase`'s design and the resolved
  `AIProviderError` this milestone relies on without further change.
- ADR-0010 — `ExactFieldMatcher`'s exact-slug matching, the mechanism
  decision #5's `--save-as` design is built to stay consistent with.
- ADR-0006 — the "no DTO without a concrete need" discipline this
  milestone's plain `str` return follows.
