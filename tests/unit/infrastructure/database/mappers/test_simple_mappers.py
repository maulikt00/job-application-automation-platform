"""Tests for the simple aggregate mappers (Profile, Resume,
CoverLetterTemplate, Answer, JobPosting) -- pure Python round trips, no
database required. Application's mapper is more involved and gets its
own test file (test_application_mapper.py).
"""

from __future__ import annotations

from pathlib import Path

from jaap.domain.models import (
    Answer,
    CoverLetterTemplate,
    JobPosting,
    Profile,
    Resume,
    new_answer_id,
    new_cover_letter_template_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from jaap.infrastructure.database.mappers import (
    answer_mapper,
    cover_letter_template_mapper,
    job_posting_mapper,
    profile_mapper,
    resume_mapper,
)
from jaap.infrastructure.database.models import (
    AnswerORM,
    CoverLetterTemplateORM,
    JobPostingORM,
    ProfileORM,
    ResumeORM,
)


def test_profile_round_trips_through_orm() -> None:
    domain = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com", phone="555-0100")

    orm = ProfileORM(id=domain.id)
    profile_mapper.update_orm(domain, orm)
    result = profile_mapper.to_domain(orm)

    assert result == domain
    assert result.full_name == "Maulik Patel"
    assert result.phone == "555-0100"


def test_resume_round_trips_through_orm_including_path_conversion() -> None:
    domain = Resume(
        id=new_resume_id(), profile_id=new_profile_id(), label="Backend",
        file_path=Path("resumes/backend.pdf"),
    )

    orm = ResumeORM(id=domain.id)
    resume_mapper.update_orm(domain, orm)
    assert orm.file_path == "resumes/backend.pdf"  # stored as plain str

    result = resume_mapper.to_domain(orm)
    assert result == domain
    assert result.file_path == Path("resumes/backend.pdf")


def test_cover_letter_template_round_trips_through_orm() -> None:
    domain = CoverLetterTemplate(
        id=new_cover_letter_template_id(), profile_id=new_profile_id(),
        name="Standard", body_template="Dear {{company_name}}, ...",
    )

    orm = CoverLetterTemplateORM(id=domain.id)
    cover_letter_template_mapper.update_orm(domain, orm)
    result = cover_letter_template_mapper.to_domain(orm)

    assert result == domain
    assert result.body_template == "Dear {{company_name}}, ..."


def test_answer_round_trips_through_orm_including_tags() -> None:
    domain = Answer(
        id=new_answer_id(), profile_id=new_profile_id(),
        question_key="why-us", answer_text="Because...", tags=["common", "behavioral"],
    )

    orm = AnswerORM(id=domain.id)
    answer_mapper.update_orm(domain, orm)
    result = answer_mapper.to_domain(orm)

    assert result == domain
    assert result.tags == ["common", "behavioral"]


def test_job_posting_round_trips_through_orm_including_url_and_metadata() -> None:
    domain = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer",
        url="https://acme.example.com/jobs/1", platform="greenhouse",
        external_id="gh-123", platform_metadata={"board": "acme-eng"},
        description="We are hiring...",
    )

    orm = JobPostingORM(id=domain.id)
    job_posting_mapper.update_orm(domain, orm)
    assert orm.url == "https://acme.example.com/jobs/1"  # stored as plain str

    result = job_posting_mapper.to_domain(orm)
    assert result == domain
    assert str(result.url) == "https://acme.example.com/jobs/1"
    assert result.platform_metadata == {"board": "acme-eng"}
    assert result.external_id == "gh-123"
