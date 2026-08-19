"""Application-layer exceptions: business-rule and process violations,
raised by use cases -- distinct from domain/exceptions.py's invariant
violations, which are raised by domain models themselves. See
docs/adr/0002-progressive-application-lifecycle.md for the reasoning
behind this split.

Named `UseCaseError`, not `ApplicationLayerError`: "Application" already
means two different things in this codebase (the Clean Architecture
layer, and the domain's `Application` aggregate) -- `UseCaseError` avoids
stacking a third meaning onto an already-overloaded word.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jaap.domain.models import ApplicationId, JobPostingId, ProfileId


class UseCaseError(Exception):
    """Base class for all application-layer (use case) errors.

    Catching `UseCaseError` lets calling code (eventually the CLI, later
    FastAPI) handle "a business rule or process precondition wasn't met"
    as a category, without needing to know about every specific
    application-layer exception that exists.
    """


class ProfileNotFoundError(UseCaseError):
    """Raised when a use case is given a ProfileId that doesn't resolve
    to an existing Profile."""

    def __init__(self, profile_id: ProfileId) -> None:
        self.profile_id = profile_id
        super().__init__(f"No Profile found with id {profile_id}.")


class JobPostingNotFoundError(UseCaseError):
    """Raised when a use case is given a JobPostingId that doesn't
    resolve to an existing JobPosting."""

    def __init__(self, job_posting_id: JobPostingId) -> None:
        self.job_posting_id = job_posting_id
        super().__init__(f"No JobPosting found with id {job_posting_id}.")


class ApplicationNotFoundError(UseCaseError):
    """Raised when a use case is given an ApplicationId that doesn't
    resolve to an existing Application."""

    def __init__(self, application_id: ApplicationId) -> None:
        self.application_id = application_id
        super().__init__(f"No Application found with id {application_id}.")


class ApplicationNotReadyForSubmissionError(UseCaseError):
    """Raised by SubmitApplicationUseCase when a business-rule submission
    precondition isn't met (e.g. no resume attached).

    This is deliberately NOT a domain invariant (see ADR-0002):
    Application itself allows an incomplete Draft to be perfectly valid.
    Readiness is entirely a business-process question the use case
    decides, which is why this exception lives here, not in
    domain/exceptions.py.
    """

    def __init__(self, application_id: ApplicationId, reason: str) -> None:
        self.application_id = application_id
        self.reason = reason
        super().__init__(f"Application {application_id} is not ready for submission: {reason}")
