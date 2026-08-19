"""StartApplicationUseCase: create a new Draft Application."""

from __future__ import annotations

from jaap.application.exceptions import JobPostingNotFoundError, ProfileNotFoundError
from jaap.application.interfaces.repositories import (
    ApplicationRepository,
    JobPostingRepository,
    ProfileRepository,
)
from jaap.domain.models import Application, JobPostingId, ProfileId, new_application_id


class StartApplicationUseCase:
    """Creates a new Draft Application for a Profile applying to a JobPosting.

    Verifies both referenced aggregates exist before creating the
    Application -- neither check is a domain invariant (Application's
    constructor happily accepts any ProfileId/JobPostingId, per ADR-0002's
    progressive Draft lifecycle), so both live here as business rules.
    Checking both, not just JobPosting, is deliberate: a Draft
    referencing a nonexistent Profile is a more confusing failure to
    debug later than catching it here at creation time.
    """

    def __init__(
        self,
        application_repository: ApplicationRepository,
        profile_repository: ProfileRepository,
        job_posting_repository: JobPostingRepository,
    ) -> None:
        self._application_repository = application_repository
        self._profile_repository = profile_repository
        self._job_posting_repository = job_posting_repository

    def execute(self, profile_id: ProfileId, job_posting_id: JobPostingId) -> Application:
        if self._profile_repository.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)
        if self._job_posting_repository.get(job_posting_id) is None:
            raise JobPostingNotFoundError(job_posting_id)

        application = Application(
            id=new_application_id(), profile_id=profile_id, job_posting_id=job_posting_id
        )
        self._application_repository.save(application)
        return application
