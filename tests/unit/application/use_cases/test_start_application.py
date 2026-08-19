"""Tests for StartApplicationUseCase."""

from __future__ import annotations

import pytest

from jaap.application.exceptions import JobPostingNotFoundError, ProfileNotFoundError
from jaap.application.use_cases.start_application import StartApplicationUseCase
from jaap.domain.models import (
    ApplicationStatus,
    JobPosting,
    Profile,
    new_job_posting_id,
    new_profile_id,
)
from tests.unit.application.use_cases.fakes import (
    FakeApplicationRepository,
    FakeJobPostingRepository,
    FakeProfileRepository,
)


def _make_use_case():
    application_repo = FakeApplicationRepository()
    profile_repo = FakeProfileRepository()
    job_posting_repo = FakeJobPostingRepository()
    use_case = StartApplicationUseCase(application_repo, profile_repo, job_posting_repo)
    return use_case, application_repo, profile_repo, job_posting_repo


def test_starts_a_draft_application_when_both_profile_and_posting_exist() -> None:
    use_case, application_repo, profile_repo, job_posting_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    posting = JobPosting(id=new_job_posting_id(), company_name="Acme", title="Eng", url="https://acme.example.com/1")
    job_posting_repo.save(posting)

    application = use_case.execute(profile_id=profile.id, job_posting_id=posting.id)

    assert application.current_status == ApplicationStatus.DRAFT
    assert application.profile_id == profile.id
    assert application.job_posting_id == posting.id
    assert application_repo.get(application.id) == application


def test_raises_profile_not_found_when_profile_does_not_exist() -> None:
    use_case, _, _, job_posting_repo = _make_use_case()
    posting = JobPosting(id=new_job_posting_id(), company_name="Acme", title="Eng", url="https://acme.example.com/1")
    job_posting_repo.save(posting)

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(profile_id=new_profile_id(), job_posting_id=posting.id)


def test_raises_job_posting_not_found_when_posting_does_not_exist() -> None:
    use_case, _, profile_repo, _ = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    with pytest.raises(JobPostingNotFoundError):
        use_case.execute(profile_id=profile.id, job_posting_id=new_job_posting_id())


def test_profile_is_checked_before_job_posting() -> None:
    # When both are missing, ProfileNotFoundError should surface first --
    # locks in a specific, predictable check order rather than leaving it
    # to whichever repository happens to be checked first by accident.
    use_case, _, _, _ = _make_use_case()

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(profile_id=new_profile_id(), job_posting_id=new_job_posting_id())
