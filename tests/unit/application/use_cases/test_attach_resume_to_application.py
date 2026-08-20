"""Tests for AttachResumeToApplicationUseCase."""

from __future__ import annotations

from pathlib import Path

import pytest

from jaap.application.exceptions import ApplicationNotFoundError, ResumeNotFoundError
from jaap.application.use_cases.attach_resume_to_application import (
    AttachResumeToApplicationUseCase,
)
from jaap.domain.models import (
    Application,
    Resume,
    new_application_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from tests.unit.application.use_cases.fakes import (
    FakeApplicationRepository,
    FakeResumeRepository,
)


def _make_use_case():
    application_repo = FakeApplicationRepository()
    resume_repo = FakeResumeRepository()
    return (
        AttachResumeToApplicationUseCase(application_repo, resume_repo),
        application_repo,
        resume_repo,
    )


def test_attaches_an_existing_resume_to_an_existing_application() -> None:
    use_case, application_repo, resume_repo = _make_use_case()
    profile_id = new_profile_id()
    application = Application(
        id=new_application_id(), profile_id=profile_id, job_posting_id=new_job_posting_id()
    )
    application_repo.save(application)
    resume = Resume(id=new_resume_id(), profile_id=profile_id, label="Backend", file_path=Path("r.pdf"))
    resume_repo.save(resume)

    result = use_case.execute(application_id=application.id, resume_id=resume.id)

    assert result.resume_id == resume.id
    assert application_repo.get(application.id).resume_id == resume.id


def test_raises_application_not_found_for_missing_application() -> None:
    use_case, _, resume_repo = _make_use_case()
    resume = Resume(id=new_resume_id(), profile_id=new_profile_id(), label="R", file_path=Path("r.pdf"))
    resume_repo.save(resume)

    with pytest.raises(ApplicationNotFoundError):
        use_case.execute(application_id=new_application_id(), resume_id=resume.id)


def test_raises_resume_not_found_for_missing_resume() -> None:
    use_case, application_repo, _ = _make_use_case()
    application = Application(
        id=new_application_id(), profile_id=new_profile_id(), job_posting_id=new_job_posting_id()
    )
    application_repo.save(application)

    with pytest.raises(ResumeNotFoundError):
        use_case.execute(application_id=application.id, resume_id=new_resume_id())
