"""AddResumeUseCase: create and persist a new Resume for a Profile."""

from __future__ import annotations

from pathlib import Path

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.interfaces.repositories import ProfileRepository, ResumeRepository
from jaap.domain.models import ProfileId, Resume, new_resume_id


class AddResumeUseCase:
    """Adds a new Resume to an existing Profile.

    Verifies the Profile exists before creating the Resume -- a business
    rule, not a domain invariant (Resume.profile_id is just a UUID as far
    as the domain model is concerned; nothing stops a Resume from being
    constructed with a ProfileId that doesn't correspond to anything).
    Catching that here means a Resume referencing a nonexistent Profile
    is caught at creation time, not discovered later as a confusing bug.
    """

    def __init__(
        self,
        resume_repository: ResumeRepository,
        profile_repository: ProfileRepository,
    ) -> None:
        self._resume_repository = resume_repository
        self._profile_repository = profile_repository

    def execute(self, profile_id: ProfileId, label: str, file_path: Path) -> Resume:
        if self._profile_repository.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)

        resume = Resume(id=new_resume_id(), profile_id=profile_id, label=label, file_path=file_path)
        self._resume_repository.save(resume)
        return resume
