# ADR-0013: Submitted Content Snapshot

## Status

Accepted — 2026-07-09

## Context

Since the Milestone 2 architectural review, `Application` has only ever
held *references* to `Resume`, `CoverLetterTemplate`, and `Answer` --
all independently mutable aggregates. ADR-0004 formally deferred fixing
this to "Milestone 6, when `SubmitApplicationUseCase` needs to answer
it." Milestone 6 came and went without resolving it. This gap became
more urgent, not less, heading into Phase 3: `CoverLetterTemplate`'s own
docstring already anticipates that Milestone 16's AI-generated cover
letters may be one-off, per-application content that is never saved as
a reusable template -- meaning there would be nowhere in the domain
model to record what an AI actually wrote and submitted for a given
application.

A pre-implementation review of `Application`'s existing lifecycle
mechanics, ORM models, mapper, and `SubmitApplicationUseCase` also
surfaced a fact that shapes this design directly: `AutofillApplicationUseCase`
and `ReviewApplicationUseCase` never touch `ApplicationRepository` at
all -- autofilling is not currently tied to any specific `Application`
record. The snapshot therefore cannot be built from "whatever the
browser just filled in"; it must be resolved independently, at
submission time, purely from whichever `resume_id`/
`cover_letter_template_id`/`answer_ids` are already set on the
`Application` being submitted.

## Decision

### 1. `SubmittedContentSnapshot` and `SubmittedAnswer`: two new, immutable value objects

```python
class SubmittedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True)
    question_key: str
    answer_text: str

class SubmittedContentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)
    resume_label: str | None = None
    resume_file_name: str | None = None
    cover_letter_text: str | None = None
    answers: tuple[SubmittedAnswer, ...] = Field(default_factory=tuple)
```

Both live in `domain/models/application.py`, alongside
`ApplicationStatusEvent` -- the same established pattern (frozen
`BaseModel`, no `Entity` inheritance, no independent identity), no new
file needed.

### 2. Resume content is represented as identifying metadata, not a file copy -- an explicit, deliberate limitation

`resume_label` + `resume_file_name` answer a narrow, specific question:
**which resume, by name, was selected at submission time** -- not
**what were the exact bytes of that file at that moment.**

This project does not implement file copying, binary versioning, object
storage, or content hashing for resumes, and this design does not
change that. If `Resume.file_path`'s underlying file is later edited or
replaced at the same path, the snapshot will still correctly report
which `Resume` record (by label and filename) was selected, but cannot
detect that the physical file's contents have since changed, and cannot
reconstruct the original bytes that were actually submitted. This is a
deliberate scope boundary, not an oversight -- full byte-level
reproducibility is a meaningfully larger feature (managed file storage
with retention) than "durable evidence of what was submitted," which is
this design's actual goal.

If exact byte-level reproducibility is ever needed, the natural,
lowest-cost next increment would be recording a content hash (e.g.
SHA-256) of the resume file at submission time -- enough to *detect*
whether a file has changed since, without storing or copying the file
itself. That is a real future option, explicitly not part of this design.

### 3. Answers and cover letter content are captured as literal text

`answers` is a tuple of literal `(question_key, answer_text)` pairs,
copied verbatim from each referenced `Answer` at submission time.
`cover_letter_text` is a single literal string, resolved as described
in decision #6 below.

### 4. The snapshot is created at exactly one lifecycle transition: `DRAFT -> SUBMITTED`

`Application.transition_to()` gains an optional `content_snapshot`
parameter, required if and only if `new_status == SUBMITTED`:

```python
def transition_to(self, new_status, *, note=None, changed_at=None, content_snapshot=None) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(self.current_status, frozenset())
    if new_status not in allowed:
        raise InvalidStatusTransitionError(self.current_status, new_status)

    if new_status == ApplicationStatus.SUBMITTED:
        if content_snapshot is None:
            raise ValueError("content_snapshot is required when transitioning to SUBMITTED")
        object.__setattr__(self, "content_snapshot", content_snapshot)
    elif content_snapshot is not None:
        raise ValueError(f"content_snapshot is only accepted when transitioning to SUBMITTED, not {new_status}")

    event = ApplicationStatusEvent(status=new_status, changed_at=changed_at or datetime.now(timezone.utc), note=note)
    object.__setattr__(self, "status_history", (*self.status_history, event))
    object.__setattr__(self, "current_status", new_status)
```

No other transition ever sets or clears it.

### 5. The snapshot is retained through every later lifecycle transition, including a `WITHDRAWN` reachable two different ways

An `Application` can reach `WITHDRAWN` either directly from `DRAFT`
(never submitted -- correctly, *no* snapshot) or from `SUBMITTED`/
`INTERVIEWING`/`OFFER` (already submitted -- correctly, *retains* the
snapshot set at the `SUBMITTED` transition). Since `transition_to()`
only ever *sets* the snapshot on the transition to `SUBMITTED` and never
touches it on any other transition, both cases fall out correctly with
no additional invariant-checking logic -- the snapshot simply stays
whatever it already was for every transition except the one that sets it.

`content_snapshot` joins `Application._PROTECTED_FIELDS` (the same
guard already protecting `current_status`/`status_history`) --
direct reassignment raises `DomainError`. `_ensure_consistent_history()`
gains one additional check closing a construction-time loophole
(constructing an `Application` directly with `current_status=DRAFT` and
a non-`None` snapshot, bypassing `transition_to()` entirely): this
raises `ValueError`.

This is treated as a domain invariant, not a business rule (per
ADR-0002's split): "a snapshot exists if and only if a submission
occurred" is about the object's own internal consistency, not about
*when submission is currently permitted* (`SubmitApplicationUseCase`'s
existing resume-attached readiness check is unchanged and unrelated).

### 6. Milestone 16's AI-generated, possibly-never-saved cover letter: an optional override parameter, not a new `Application` field

`SubmitApplicationUseCase.execute()` gains
`cover_letter_text_override: str | None = None`. If provided, this
literal text becomes the snapshot's `cover_letter_text` directly,
regardless of whether `cover_letter_template_id` is set. If omitted and
`cover_letter_template_id` is set, the use case loads that
`CoverLetterTemplate` and uses its `body_template` (unresolved
placeholders and all -- actual placeholder substitution is Milestone
16's own job). If neither is present, `cover_letter_text` stays `None`
-- a valid state, not every application needs a cover letter. If both
are present, the override silently wins -- not treated as an error,
since there's a reasonable interpretation either way and erroring adds
ceremony for no real safety benefit.

Deliberately not a new `Application` field (e.g. a "pending ad-hoc cover
letter text" staging field): that would mean tracking transient
pre-submission content on a domain object that doesn't otherwise need
it. Passing it through as a use-case parameter at the one moment it
actually matters is smaller.

### 7. `SubmitApplicationUseCase` gains three repository dependencies directly; snapshot construction is a private module-level function, not a new class or Protocol

`SubmitApplicationUseCase` gains `ResumeRepository`, `AnswerRepository`,
and `CoverLetterTemplateRepository` alongside its existing
`ApplicationRepository`. This was evaluated explicitly against
introducing a new abstraction to aggregate the fetching, and rejected:
multiple repositories injected directly into one use case is already
this project's established pattern (`StartApplicationUseCase` already
holds three; `AutofillApplicationUseCase` already holds six), not a new
one being introduced here.

The pure transformation -- given an already-loaded `Resume`, `list[Answer]`,
optional `CoverLetterTemplate`, and optional override string, build a
`SubmittedContentSnapshot` -- is extracted into a private, module-level
function, `_build_content_snapshot()`, in `submit_application.py`. This
is ordinary function decomposition within the one file that needs it,
not a new architectural component. A `Protocol`-based service (matching
`ExactFieldMatcher`'s pattern) was considered and rejected: `ExactFieldMatcher`
earns its `Protocol` because Phase 3 already anticipates a second,
swappable implementation (an AI-assisted matcher); snapshot-building has
no anticipated second implementation and no swappability need, so giving
it one would be inventing an abstraction to justify a package placement.

### 8. Database/ORM/mapping changes: one nullable JSON column, no new table

`ApplicationORM.content_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)`.
No new child table. The snapshot is never partially queried or filtered
at the SQL level -- it's written once and read back as a single unit --
so a JSON blob (the same pattern already used for `Answer.tags` and
`JobPosting.platform_metadata`) is the smallest correct representation.
A new child table mirroring `ApplicationAnswerORM`'s position-tracking
complexity would be solving a querying need this data doesn't have.

Mapper: `to_domain()` calls `SubmittedContentSnapshot.model_validate(orm.content_snapshot)`
if not `None`; `update_orm()` calls `domain.content_snapshot.model_dump(mode="json")`
if not `None`. No reconciliation logic beyond that -- unlike `answer_ids`,
this is write-once, never append-only or independently orderable.
Repository: no changes needed beyond what the mapper already provides.

## Alternatives Considered

- **A new child table for submitted answers**, mirroring
  `ApplicationStatusEventORM`/`ApplicationAnswerORM`. Rejected; see
  decision #8 -- more complexity than the actual querying need justifies.
- **Copying/versioning the resume file itself.** Rejected; see decision
  #2 -- a materially larger feature than this design's goal.
- **A `Protocol`-based `SnapshotBuilder` service.** Rejected; see
  decision #7.
- **A new `Application` field for pending ad-hoc cover letter text.**
  Rejected; see decision #6.
- **Requiring the snapshot as a constructor argument on `Application`
  itself**, rather than an optional `transition_to()` parameter.
  Rejected: would reopen exactly the "all fields required at
  construction" problem ADR-0002 already solved for the Draft lifecycle.

## Consequences

**Positive:**
- `Application` now carries durable, immutable evidence of what was
  actually submitted, closing a gap flagged in Milestone 2 and formally
  deferred (twice) since.
- Milestone 16's AI-generated cover letters have a concrete place to
  land, even when never saved as a reusable template -- resolved before
  that milestone needs it, not discovered as a blocker during it.
- No new architectural component was introduced solely to reduce
  constructor argument count -- `SubmitApplicationUseCase`'s dependency
  list grows the same way every other multi-aggregate use case in this
  project already does.

**Trade-offs:**
- The resume snapshot cannot prove exact file contents at submission
  time, only which resume (by name) was selected -- an explicit,
  documented limitation, not a silent gap.
- `SubmitApplicationUseCase` now depends on four repositories instead of
  one, making it the most-connected use case in the application layer
  after `AutofillApplicationUseCase`. Judged acceptable given it mirrors
  existing precedent rather than introducing a new one.

## References

- ADR-0002 -- the progressive Draft lifecycle and domain-invariant/
  business-rule split this design's transition mechanics extend.
- ADR-0004 -- the original deferral this ADR resolves.
- ADR-0005 -- the repository/mapper separation and JSON-column precedent
  (`Answer.tags`, `JobPosting.platform_metadata`) this design reuses.
- ADR-0010 -- `application/services/`'s scope (Protocol implementations
  with a real swappability need), which this design's private-function
  choice deliberately does not qualify for.
