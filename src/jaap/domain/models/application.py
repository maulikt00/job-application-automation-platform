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


class Application(Entity):
    """A single attempt by a Profile to apply to a JobPosting.

    Only `profile_id` and `job_posting_id` are required to create a Draft;
    `resume_id`, `cover_letter_template_id`, and `answer_ids` are filled in
    progressively as the workflow proceeds. See ADR-0002 for the reasoning.

    `current_status` and `status_history` must only be changed via
    `transition_to()` -- direct assignment to either raises `DomainError`.
    This is enforced structurally (via `__setattr__`), not just by
    convention, because the two fields carry a cross-field invariant
    (`current_status` must always equal the most recent `status_history`
    event) that Pydantic's per-field `validate_assignment` cannot safely
    enforce on its own (see ADR-0003). Other fields (`resume_id`,
    `cover_letter_template_id`, `answer_ids`) carry no such invariant and
    remain freely settable, which is what allows the progressive Draft
    lifecycle described above.
    """

    _PROTECTED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"current_status", "status_history"}
    )

    id: ApplicationId
    profile_id: ProfileId
    job_posting_id: JobPostingId
    resume_id: ResumeId | None = None
    cover_letter_template_id: CoverLetterTemplateId | None = None
    answer_ids: tuple[AnswerId, ...] = Field(default_factory=tuple)
    current_status: ApplicationStatus = ApplicationStatus.DRAFT
    status_history: tuple[ApplicationStatusEvent, ...] = Field(default_factory=tuple)
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
        return self

    def transition_to(
        self,
        new_status: ApplicationStatus,
        *,
        note: str | None = None,
        changed_at: datetime | None = None,
    ) -> None:
        """Move this Application to `new_status`.

        Only enforces that the transition is *structurally* valid (see
        `_ALLOWED_TRANSITIONS`). Whether the transition should currently be
        *permitted* for business reasons (e.g. a resume must be attached
        before moving to SUBMITTED) is the calling use case's job, not this
        method's.

        Raises:
            InvalidStatusTransitionError: if `new_status` is not reachable
                from the current status.
        """
        allowed = _ALLOWED_TRANSITIONS.get(self.current_status, frozenset())
        if new_status not in allowed:
            raise InvalidStatusTransitionError(self.current_status, new_status)

        event = ApplicationStatusEvent(
            status=new_status,
            changed_at=changed_at or datetime.now(timezone.utc),
            note=note,
        )
        # Bypass the __setattr__ guard: this is the one sanctioned code
        # path allowed to update these two fields, and it does so together
        # so the object is never briefly inconsistent between the two.
        object.__setattr__(self, "status_history", (*self.status_history, event))
        object.__setattr__(self, "current_status", new_status)
