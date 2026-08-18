"""Tests for SqliteCoverLetterTemplateRepository."""

from __future__ import annotations

import pytest

from jaap.domain.exceptions import ReferentialIntegrityError
from jaap.domain.models import (
    Application,
    CoverLetterTemplate,
    JobPosting,
    Profile,
    new_application_id,
    new_cover_letter_template_id,
    new_job_posting_id,
    new_profile_id,
)
from jaap.infrastructure.database.repositories.sqlite_application_repository import (
    SqliteApplicationRepository,
)
from jaap.infrastructure.database.repositories.sqlite_cover_letter_template_repository import (
    SqliteCoverLetterTemplateRepository,
)
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)
from jaap.infrastructure.database.repositories.sqlite_profile_repository import (
    SqliteProfileRepository,
)


def _make_profile(session_factory) -> Profile:
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    SqliteProfileRepository(session_factory).save(profile)
    return profile


def test_save_then_get_round_trips(session_factory) -> None:
    profile = _make_profile(session_factory)
    repo = SqliteCoverLetterTemplateRepository(session_factory)
    template = CoverLetterTemplate(
        id=new_cover_letter_template_id(), profile_id=profile.id, name="Standard", body_template="Dear team..."
    )

    repo.save(template)
    loaded = repo.get(template.id)

    assert loaded == template


def test_list_by_profile(session_factory) -> None:
    profile = _make_profile(session_factory)
    repo = SqliteCoverLetterTemplateRepository(session_factory)
    repo.save(CoverLetterTemplate(id=new_cover_letter_template_id(), profile_id=profile.id, name="A", body_template="..."))
    repo.save(CoverLetterTemplate(id=new_cover_letter_template_id(), profile_id=profile.id, name="B", body_template="..."))

    result = repo.list_by_profile(profile.id)

    assert sorted(t.name for t in result) == ["A", "B"]


def test_delete_referenced_template_raises_referential_integrity_error(session_factory) -> None:
    profile = _make_profile(session_factory)
    template_repo = SqliteCoverLetterTemplateRepository(session_factory)
    template = CoverLetterTemplate(id=new_cover_letter_template_id(), profile_id=profile.id, name="Standard", body_template="...")
    template_repo.save(template)

    posting = JobPosting(id=new_job_posting_id(), company_name="Acme", title="Eng", url="https://acme.example.com/1")
    SqliteJobPostingRepository(session_factory).save(posting)

    application = Application(
        id=new_application_id(), profile_id=profile.id, job_posting_id=posting.id,
        cover_letter_template_id=template.id,
    )
    SqliteApplicationRepository(session_factory).save(application)

    with pytest.raises(ReferentialIntegrityError):
        template_repo.delete(template.id)
