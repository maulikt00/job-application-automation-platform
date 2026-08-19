"""Tests for SaveCoverLetterTemplateUseCase."""

from __future__ import annotations

import pytest

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.use_cases.manage_cover_letter_templates import (
    SaveCoverLetterTemplateUseCase,
)
from jaap.domain.models import Profile, new_profile_id
from tests.unit.application.use_cases.fakes import (
    FakeCoverLetterTemplateRepository,
    FakeProfileRepository,
)


def _make_use_case():
    template_repo = FakeCoverLetterTemplateRepository()
    profile_repo = FakeProfileRepository()
    return SaveCoverLetterTemplateUseCase(template_repo, profile_repo), template_repo, profile_repo


def test_creates_a_template_for_an_existing_profile() -> None:
    use_case, template_repo, profile_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    template = use_case.execute(profile_id=profile.id, name="Standard", body_template="Dear team...")

    assert template.profile_id == profile.id
    assert template_repo.get(template.id) == template


def test_passing_template_id_updates_the_existing_template() -> None:
    use_case, template_repo, profile_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    original = use_case.execute(profile_id=profile.id, name="Standard", body_template="v1")

    updated = use_case.execute(
        profile_id=profile.id, name="Standard", body_template="v2", template_id=original.id
    )

    assert updated.id == original.id
    assert template_repo.get(original.id).body_template == "v2"


def test_raises_profile_not_found_when_profile_does_not_exist() -> None:
    use_case, _, _ = _make_use_case()

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(profile_id=new_profile_id(), name="Standard", body_template="...")
