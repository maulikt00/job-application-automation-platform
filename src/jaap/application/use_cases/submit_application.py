"""SubmitApplicationUseCase: move a Draft Application to SUBMITTED.

This is the use case docs/adr/0002-progressive-application-lifecycle.md
pointed to when it deferred "is this ready to submit" out of the domain
model: `Application` allows an incomplete Draft to be perfectly valid,
and readiness is entirely a business-process question this use case
answers, not `Application` itself.
"""

from __future__ import annotations

from jaap.application.exceptions import (
    ApplicationNotFoundError,
    ApplicationNotReadyForSubmissionError,
)
from jaap.application.interfaces.repositories import ApplicationRepository
from jaap.domain.models import Application, ApplicationId, ApplicationStatus


class SubmitApplicationUseCase:
    """Transitions a Draft Application to SUBMITTED.

    Enforces exactly the one readiness rule ADR-0002 named explicitly --
    a resume must be attached -- deliberately not inventing additional
    requirements the ADR didn't state. Structural validity of the
    transition itself (e.g. rejecting a submit on an already-SUBMITTED or
    WITHDRAWN application) is NOT re-checked here: that's `transition_to()`'s
    job as a domain invariant (see ADR-0002/0003), and this use case lets
    `InvalidStatusTransitionError` propagate unmodified rather than
    duplicating that check.
    """

    def __init__(self, application_repository: ApplicationRepository) -> None:
        self._application_repository = application_repository

    def execute(self, application_id: ApplicationId) -> Application:
        application = self._application_repository.get(application_id)
        if application is None:
            raise ApplicationNotFoundError(application_id)

        if application.resume_id is None:
            raise ApplicationNotReadyForSubmissionError(
                application_id, "a resume must be attached before submission"
            )

        application.transition_to(ApplicationStatus.SUBMITTED)
        self._application_repository.save(application)
        return application
