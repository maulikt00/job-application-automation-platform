"""Tests for CreateProfileUseCase/UpdateProfileUseCase."""

from __future__ import annotations

import pytest

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.use_cases.manage_profile import (
    CreateProfileUseCase,
    UpdateProfileUseCase,
)
from jaap.domain.models import ProfileId, new_profile_id
from tests.unit.application.use_cases.fakes import FakeProfileRepository


def test_creates_and_saves_a_profile() -> None:
    repo = FakeProfileRepository()
    use_case = CreateProfileUseCase(repo)

    profile = use_case.execute(full_name="Maulik Patel", email="m@example.com", phone="555-0100")

    assert profile.full_name == "Maulik Patel"
    assert repo.get(profile.id) == profile


def test_phone_is_optional() -> None:
    repo = FakeProfileRepository()
    use_case = CreateProfileUseCase(repo)

    profile = use_case.execute(full_name="Maulik Patel", email="m@example.com")

    assert profile.phone is None


def test_address_fields_are_optional_and_default_to_none() -> None:
    repo = FakeProfileRepository()
    use_case = CreateProfileUseCase(repo)

    profile = use_case.execute(full_name="Maulik Patel", email="m@example.com")

    assert profile.address_line1 is None
    assert profile.address_line2 is None
    assert profile.city is None
    assert profile.state is None
    assert profile.postal_code is None
    assert profile.country is None


def test_address_fields_are_saved_when_provided() -> None:
    repo = FakeProfileRepository()
    use_case = CreateProfileUseCase(repo)

    profile = use_case.execute(
        full_name="Maulik Patel",
        email="m@example.com",
        address_line1="123 Main St",
        address_line2="Apt 4",
        city="Santa Clara",
        state="CA",
        postal_code="95050",
        country="USA",
    )

    saved = repo.get(profile.id)
    assert saved is not None
    assert saved.address_line1 == "123 Main St"
    assert saved.address_line2 == "Apt 4"
    assert saved.city == "Santa Clara"
    assert saved.state == "CA"
    assert saved.postal_code == "95050"
    assert saved.country == "USA"


# --- UpdateProfileUseCase ---


def test_update_raises_when_profile_does_not_exist() -> None:
    repo = FakeProfileRepository()
    use_case = UpdateProfileUseCase(repo)

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(profile_id=ProfileId(new_profile_id()), city="Santa Clara")


def test_update_sets_a_previously_unset_field() -> None:
    repo = FakeProfileRepository()
    profile = CreateProfileUseCase(repo).execute(full_name="Maulik Patel", email="m@example.com")
    assert profile.address_line1 is None

    updated = UpdateProfileUseCase(repo).execute(
        profile_id=profile.id, address_line1="123 Main St", city="Santa Clara"
    )

    assert updated.address_line1 == "123 Main St"
    assert updated.city == "Santa Clara"


def test_update_persists_the_change() -> None:
    repo = FakeProfileRepository()
    profile = CreateProfileUseCase(repo).execute(full_name="Maulik Patel", email="m@example.com")

    UpdateProfileUseCase(repo).execute(profile_id=profile.id, city="Santa Clara")

    assert repo.get(profile.id).city == "Santa Clara"  # type: ignore[union-attr]


def test_update_leaves_omitted_fields_unchanged() -> None:
    repo = FakeProfileRepository()
    profile = CreateProfileUseCase(repo).execute(
        full_name="Maulik Patel", email="m@example.com", phone="555-0100", city="Santa Clara"
    )

    updated = UpdateProfileUseCase(repo).execute(profile_id=profile.id, state="CA")

    # state is now set, but phone/city (not passed this call) are unchanged.
    assert updated.state == "CA"
    assert updated.phone == "555-0100"
    assert updated.city == "Santa Clara"


def test_update_can_change_multiple_fields_at_once() -> None:
    repo = FakeProfileRepository()
    profile = CreateProfileUseCase(repo).execute(full_name="Maulik Patel", email="m@example.com")

    updated = UpdateProfileUseCase(repo).execute(
        profile_id=profile.id,
        address_line1="123 Main St",
        city="Santa Clara",
        state="CA",
        postal_code="95050",
        country="USA",
    )

    assert updated.address_line1 == "123 Main St"
    assert updated.city == "Santa Clara"
    assert updated.state == "CA"
    assert updated.postal_code == "95050"
    assert updated.country == "USA"


def test_update_with_no_fields_passed_changes_nothing() -> None:
    repo = FakeProfileRepository()
    profile = CreateProfileUseCase(repo).execute(
        full_name="Maulik Patel", email="m@example.com", city="Santa Clara"
    )

    updated = UpdateProfileUseCase(repo).execute(profile_id=profile.id)

    assert updated.full_name == "Maulik Patel"
    assert updated.city == "Santa Clara"
