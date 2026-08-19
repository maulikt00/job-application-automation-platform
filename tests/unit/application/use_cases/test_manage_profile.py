"""Tests for CreateProfileUseCase."""

from __future__ import annotations

from jaap.application.use_cases.manage_profile import CreateProfileUseCase
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
