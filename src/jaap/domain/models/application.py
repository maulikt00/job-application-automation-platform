"""Application domain model.

An Application is the central record tying a Profile's attempt to apply
to a JobPosting together with the Resume, CoverLetterTemplate, and Answers
used, plus its submission lifecycle/status history.

See docs/adr/0002-progressive-application-lifecycle.md for why this model
allows an incomplete Draft to be perfectly valid, and why "is this ready
to submit" is deliberately NOT checked here -- that lives in
SubmitApplicationUseCase (application layer, Milestone 6).

See docs/adr/0003-entity-identity-and-connector-extensibility.md for why
`current_status`/`status_history` are guarded against direct assignment
while the other fields remain freely settable.

See docs/adr/0013-submitted-content-snapshot.md for `SubmittedContentSnapshot`/
`SubmittedAnswer` and `content_snapshot`: durable, immutable evidence of
what was actually submitted, set exactly once at the DRAFT -> SUBMITTED
transition, closing a gap flagged as far back as the Milestone 2 review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jaap.domain.exceptions import DomainError, InvalidStatusTransitionError
from jaap.domain.models.entity import Entity
from jaap.domain.models.ids import (
    AnswerId,
    ApplicationId,
    CoverLetterTemplateId,
    JobPostingId,
    ProfileId,
    ResumeId,
)


class ApplicationStatus(str, Enum):
    """The lifecycle stages an Application can move through."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


# Structurally valid transitions -- what "makes sense" for the object
# itself (you can't be interviewing before you've submitted). This says
# nothing about whether a *specific* transition is currently permitted for
# business reasons (e.g. missing a resume); that check belongs to the
# use case, not the domain model.
_ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.DRAFT: frozenset(
        {ApplicationStatus.SUBMITTED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.SUBMITTED: frozenset(
        {ApplicationStatus.INTERVIEWING, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.INTERVIEWING: frozenset(
        {ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.OFFER: frozenset(
        {ApplicationStatus.WITHDRAWN, ApplicationStatus.REJECTED}
    ),
    ApplicationStatus.REJECTED: frozenset(),
    ApplicationStatus.WITHDRAWN: frozenset(),
}


class ApplicationStatusEvent(BaseModel):
    """An immutable record of a single status change.

    A value object: no identity of its own, never persisted or fetched
    independent of the Application it belongs to. Deliberately does NOT
    inherit from Entity -- its equality should remain structural.
    """

    model_config = ConfigDict(frozen=True)

    status: ApplicationStatus
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    note: str | None = None


class SubmittedAnswer(BaseModel):
    """One literal question/answer pair as it was actually submitted.

    A value object, copied verbatim from an Answer at submission time --
    deliberately disconnected from that Answer afterward (see
    SubmittedContentSnapshot's docstring for why).
    """

    model_config = ConfigDict(frozen=True)

    question_key: str
    answer_text: str


class SubmittedContentSnapshot(BaseModel):
    """Immutable, durable evidence of what was actually submitted with an
    Application -- captured once, at the DRAFT -> SUBMITTED transition
    (see Application.transition_to()).

    Exists because Resume/CoverLetterTemplate/Answer are all independently
    mutable, and (per Milestone 16's design) a cover letter may be
    AI-generated, one-off content never saved as a reusable
    CoverLetterTemplate at all. Without this snapshot, editing an Answer's
    text next month would retroactively change what a past Application
    appears to have said, and a never-saved cover letter would leave no
    trace anywhere. See docs/adr/0013-submitted-content-snapshot.md.

    `resume_label`/`resume_file_name` are identifying metadata, NOT a copy
    of the resume file's bytes -- this project does not implement file
    copying, binary versioning, or content hashing for resumes, and this
    snapshot does not change that. If the underlying file at
    Resume.file_path is later edited or replaced, this snapshot still
    correctly reports which Resume (by label and filename) was selected,
    but cannot detect that the file's contents have since changed and
    cannot reconstruct the original bytes submitted. This is a deliberate,
    documented scope boundary (see ADR-0013), not an oversight.
    """

    model_config = ConfigDict(frozen=True)

    resume_label: str | None = None
    resume_file_name: str | None = None
    cover_letter_text: str | None = None
    answers: tuple[SubmittedAnswer, ...] = Field(default_factory=tuple)


class Application(Entity):
    """A single attempt by a Profile to apply to a JobPosting.

    Only `profile_id` and `job_posting_id` are required to create a Draft;
    `resume_id`, `cover_letter_template_id`, and `answer_ids` are filled in
    progressively as the workflow proceeds. See ADR-0002 for the reasoning.

    `current_status`, `status_history`, and `content_snapshot` must only
    be changed via `transition_to()` -- direct assignment to any of them
    raises `DomainError`. This is enforced structurally (via `__setattr__`),
    not just by convention, because these fields carry cross-field
    invariants (`current_status` must always equal the most recent
    `status_history` event; `content_snapshot` must be present if and only
    if a submission has occurred) that Pydantic's per-field
    `validate_assignment` cannot safely enforce on its own (see ADR-0003).
    Other fields (`resume_id`, `cover_letter_template_id`, `answer_ids`)
    carry no such invariant and remain freely settable, which is what
    allows the progressive Draft lifecycle described above.
    """

    _PROTECTED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"current_status", "status_history", "content_snapshot"}
    )

    id: ApplicationId
    profile_id: ProfileId
    job_posting_id: JobPostingId
    resume_id: ResumeId | None = None
    cover_letter_template_id: CoverLetterTemplateId | None = None
    answer_ids: tuple[AnswerId, ...] = Field(default_factory=tuple)
    current_status: ApplicationStatus = ApplicationStatus.DRAFT
    status_history: tuple[ApplicationStatusEvent, ...] = Field(default_factory=tuple)
    content_snapshot: SubmittedContentSnapshot | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self._PROTECTED_FIELDS:
            raise DomainError(
                f"'{name}' is managed exclusively by transition_to() and cannot "
                "be set directly."
            )
        super().__setattr__(name, value)

    @model_validator(mode="after")
    def _ensure_consistent_history(self) -> Application:
        if not self.status_history:
            # Bypass the __setattr__ guard: this is the class's own
            # sanctioned initialization of status_history, not an
            # external attempt to mutate it directly.
            object.__setattr__(
                self,
                "status_history",
                (ApplicationStatusEvent(status=self.current_status, changed_at=self.created_at),),
            )
        if self.status_history[-1].status != self.current_status:
            raise ValueError(
                "current_status must match the most recent status_history event; "
                "use transition_to() to change status instead of setting fields directly."
            )
        # Closes a construction-time loophole: constructing an Application
        # directly with current_status=DRAFT and a non-None content_snapshot
        # bypasses transition_to() entirely (Pydantic's own __init__ sets
        # fields without going through our __setattr__ guard). A snapshot
        # must only ever exist as evidence that a submission occurred.
        if self.current_status == ApplicationStatus.DRAFT and self.content_snapshot is not None:
            raise ValueError("content_snapshot must not be set while current_status is DRAFT")
        return self

    def transition_to(
        self,
        new_status: ApplicationStatus,
        *,
        note: str | None = None,
        changed_at: datetime | None = None,
        content_snapshot: SubmittedContentSnapshot | None = None,
    ) -> None:
        """Move this Application to `new_status`.

        Only enforces that the transition is *structurally* valid (see
        `_ALLOWED_TRANSITIONS`). Whether the transition should currently be
        *permitted* for business reasons (e.g. a resume must be attached
        before moving to SUBMITTED) is the calling use case's job, not this
        method's.

        `content_snapshot` is required when `new_status` is SUBMITTED (see
        ADR-0013) and rejected for every other transition -- once set, it
        is never touched again by any subsequent transition, which is what
        lets it correctly survive a later move to INTERVIEWING/OFFER/
        WITHDRAWN without this method needing to re-check or re-supply it.

        Raises:
            InvalidStatusTransitionError: if `new_status` is not reachable
                from the current status.
            ValueError: if `content_snapshot` is missing when transitioning
                to SUBMITTED, or provided for any other transition.
        """
        allowed = _ALLOWED_TRANSITIONS.get(self.current_status, frozenset())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(self.current_status, new_status)

        if new_status == ApplicationStatus.SUBMITTED:
            if content_snapshot is None:
                raise ValueError(
                    "content_snapshot is required when transitioning to SUBMITTED"
                )
            object.__setattr__(self, "content_snapshot", content_snapshot)
        elif content_snapshot is not None:
            raise ValueError(
                f"content_snapshot is only accepted when transitioning to SUBMITTED, "
                f"not {new_status.value}"
            )

        event = ApplicationStatusEvent(
            status=new_status,
            changed_at=changed_at or datetime.now(timezone.utc),
            note=note,
        )
        # Bypass the __setattr__ guard: this is the one sanctioned code
        # path allowed to update these fields, and it does so together so
        # the object is never briefly inconsistent between them.
        object.__setattr__(self, "status_history", (*self.status_history, event))
        object.__setattr__(self, "current_status", new_status)
