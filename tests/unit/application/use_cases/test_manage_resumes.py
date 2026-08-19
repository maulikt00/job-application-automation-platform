"""Tests for AddResumeUseCase."""

from __future__ import annotations

from pathlib import Path

import pytest

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.use_cases.manage_resumes import AddResumeUseCase
from jaap.domain.models import Profile, new_profile_id
from tests.unit.application.use_cases.fakes import (
    FakeProfileRepository,
    FakeResumeRepository,
)


def _make_use_case() -> tuple[AddResumeUseCase, FakeResumeRepository, FakeProfileRepository]:
    resume_repo = FakeResumeRepository()
    profile_repo = FakeProfileRepository()
    return AddResumeUseCase(resume_repo, profile_repo), resume_repo, profile_repo


def test_adds_a_resume_for_an_existing_profile() -> None:
    use_case, resume_repo, profile_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    resume = use_case.execute(profile_id=profile.id, label="Backend", file_path=Path("r.pdf"))

    assert resume.profile_id == profile.id
    assert resume_repo.get(resume.id) == resume


def test_raises_profile_not_found_when_profile_does_not_exist() -> None:
    use_case, _, _ = _make_use_case()

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(profile_id=new_profile_id(), label="Backend", file_path=Path("r.pdf"))
