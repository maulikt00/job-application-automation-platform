"""CreateProfileUseCase/UpdateProfileUseCase: create, and partially
update, a persisted Profile.
"""

from __future__ import annotations

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.interfaces.repositories import ProfileRepository
from jaap.domain.models import Profile, ProfileId, new_profile_id


class CreateProfileUseCase:
    """Creates a new Profile and saves it.

    Depends only on ProfileRepository -- no cross-aggregate validation is
    needed here, since a Profile is the root of "who is applying" and
    doesn't reference anything else.
    """

    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(
        self,
        full_name: str,
        email: str,
        phone: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
    ) -> Profile:
        profile = Profile(
            id=new_profile_id(),
            full_name=full_name,
            email=email,
            phone=phone,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
        )
        self._profile_repository.save(profile)
        return profile


class UpdateProfileUseCase:
    """Partially updates an existing Profile: only the fields explicitly
    passed (non-None) are changed; anything omitted (left None) keeps
    its current, already-saved value.

    Added alongside address-field support (ADR-0038): there was
    previously no way to add or change data on an existing Profile at
    all (a real, already-identified CLI-completeness gap -- the
    post-Phase-4 checkpoint review noted "Profile has only create").
    Building this now, rather than address-only support with no update
    path, was a deliberate choice: an address-only update command would
    have been an oddly narrow, one-off mechanism when a general partial
    update costs no more to build and is a genuinely more complete,
    reusable capability.

    "None means don't change this field" is a different convention from
    CreateProfileUseCase's `phone: str | None = None` (where None
    genuinely means "no phone"). This is deliberate: an update call
    needs a way to say "leave this alone," and the CLI's own argparse
    defaults are already None for any flag the person didn't pass, so a
    shared "None means unset" convention between the CLI layer and this
    use case is the natural fit. There is currently no way to explicitly
    clear an already-set field back to None through this use case -- not
    needed yet, and deliberately not built ahead of a real need for it.
    """

    def __init__(self, profile_repository: ProfileRepository) -> None:
        self._profile_repository = profile_repository

    def execute(
        self,
        profile_id: ProfileId,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
    ) -> Profile:
        profile = self._profile_repository.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)

        if full_name is not None:
            profile.full_name = full_name
        if email is not None:
            profile.email = email
        if phone is not None:
            profile.phone = phone
        if address_line1 is not None:
            profile.address_line1 = address_line1
        if address_line2 is not None:
            profile.address_line2 = address_line2
        if city is not None:
            profile.city = city
        if state is not None:
            profile.state = state
        if postal_code is not None:
            profile.postal_code = postal_code
        if country is not None:
            profile.country = country

        self._profile_repository.save(profile)
        return profile
