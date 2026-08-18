"""Tests for SqliteResumeRepository, including the ReferentialIntegrityError
translation on a RESTRICTed delete."""

from __future__ import annotations

from pathlib import Path

import pytest

from jaap.domain.exceptions import ReferentialIntegrityError
from jaap.domain.models import (
    Application,
    JobPosting,
    Profile,
    Resume,
    new_application_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from jaap.infrastructure.database.repositories.sqlite_application_repository import (
    SqliteApplicationRepository,
)
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)
from jaap.infrastructure.database.repositories.sqlite_profile_repository import (
    SqliteProfileRepository,
)
from jaap.infrastructure.database.repositories.sqlite_resume_repository import (
    SqliteResumeRepository,
)


def _make_profile(session_factory) -> Profile:
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    SqliteProfileRepository(session_factory).save(profile)
    return profile


def test_save_then_get_round_trips(session_factory) -> None:
    profile = _make_profile(session_factory)
    repo = SqliteResumeRepository(session_factory)
    resume = Resume(id=new_resume_id(), profile_id=profile.id, label="Backend", file_path=Path("r.pdf"))

    repo.save(resume)
    loaded = repo.get(resume.id)

    assert loaded == resume
    assert loaded.file_path == Path("r.pdf")


def test_list_by_profile_returns_only_that_profiles_resumes(session_factory) -> None:
    profile_a = _make_profile(session_factory)
    profile_b = _make_profile(session_factory)
    repo = SqliteResumeRepository(session_factory)
    repo.save(Resume(id=new_resume_id(), profile_id=profile_a.id, label="A1", file_path=Path("a1.pdf")))
    repo.save(Resume(id=new_resume_id(), profile_id=profile_a.id, label="A2", file_path=Path("a2.pdf")))
    repo.save(Resume(id=new_resume_id(), profile_id=profile_b.id, label="B1", file_path=Path("b1.pdf")))

    result = repo.list_by_profile(profile_a.id)

    assert sorted(r.label for r in result) == ["A1", "A2"]


def test_delete_referenced_resume_raises_referential_integrity_error(session_factory) -> None:
    profile = _make_profile(session_factory)
    resume_repo = SqliteResumeRepository(session_factory)
    resume = Resume(id=new_resume_id(), profile_id=profile.id, label="R", file_path=Path("r.pdf"))
    resume_repo.save(resume)

    posting = JobPosting(id=new_job_posting_id(), company_name="Acme", title="Eng", url="https://acme.example.com/1")
    SqliteJobPostingRepository(session_factory).save(posting)

    application = Application(
        id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id, resume_id=resume.id
    )
    SqliteApplicationRepository(session_factory).save(application)

    with pytest.raises(ReferentialIntegrityError):
        resume_repo.delete(resume.id)

    # The resume must still exist -- the delete should not have partially applied.
    assert resume_repo.get(resume.id) is not None


def test_delete_unreferenced_resume_succeeds(session_factory) -> None:
    profile = _make_profile(session_factory)
    repo = SqliteResumeRepository(session_factory)
    resume = Resume(id=new_resume_id(), profile_id=profile.id, label="R", file_path=Path("r.pdf"))
    repo.save(resume)

    repo.delete(resume.id)

    assert repo.get(resume.id) is None
