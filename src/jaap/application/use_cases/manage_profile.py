"""CreateProfileUseCase: create and persist a new Profile."""

from __future__ import annotations

from jaap.application.interfaces.repositories import ProfileRepository
from jaap.domain.models import Profile, new_profile_id


class CreateProfileUseCase:
    """Creates a new Profile and saves it.

    Depends only on ProfileRepository -- no cross-aggregate validation is
    needed here, since a Profile is the root of "who is applying" and
    doesn't reference anything else.
    """

    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(self, full_name: str, email: str, phone: str | None = None) -> Profile:
        profile = Profile(id=new_profile_id(), full_name=full_name, email=email, phone=phone)
        self._profile_repository.save(profile)
        return profile
