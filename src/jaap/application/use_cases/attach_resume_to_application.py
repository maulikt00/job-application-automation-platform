"""AttachResumeToApplicationUseCase: attach a Resume to a Draft Application.

This is the concrete resolution of ADR-0006's deferred "SelectResumeUseCase"
decision: setting Application.resume_id carries no domain invariant
(ADR-0002/0003 -- it's freely settable, unlike current_status), but a
use case still needs to exist for it to actually happen through a
CLI command. Caught as a real gap during Milestone 7's own end-to-end
smoke test: without this, a Draft application created via
StartApplicationUseCase could never satisfy SubmitApplicationUseCase's
"a resume must be attached" precondition.
"""

from __future__ import annotations

from jaap.application.exceptions import ApplicationNotFoundError, ResumeNotFoundError
from jaap.application.interfaces.repositories import (
    ApplicationRepository,
    ResumeRepository,
)
from jaap.domain.models import Application, ApplicationId, ResumeId


class AttachResumeToApplicationUseCase:
    """Attaches a Resume to an existing Application.

    Verifies both the Application and the Resume exist first -- same
    reasoning as StartApplicationUseCase checking Profile/JobPosting:
    neither check is a domain invariant, so both are this use case's job.
    """

    def __init__(
        self,
        application_repository: ApplicationRepository,
        resume_repository: ResumeRepository,
    ) -> None:
        self._application_repository = application_repository
        self._resume_repository = resume_repository

    def execute(self, application_id: ApplicationId, resume_id: ResumeId) -> Application:
        application = self._application_repository.get(application_id)
        if application is None:
            raise ApplicationNotFoundError(application_id)
        if self._resume_repository.get(resume_id) is None:
            raise ResumeNotFoundError(resume_id)

        application.resume_id = resume_id
        self._application_repository.save(application)
        return application
