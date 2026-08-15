"""Strongly-typed identifiers for each aggregate root.

Using ``typing.NewType`` over a shared ``UUID`` base gives each aggregate
a distinct type for static analysis -- mypy will flag passing a
``ResumeId`` where a ``ProfileId`` is expected -- with zero runtime
overhead. At runtime these are still plain ``uuid.UUID`` values.
"""

from __future__ import annotations

from typing import NewType
from uuid import UUID, uuid4

ProfileId = NewType("ProfileId", UUID)
ResumeId = NewType("ResumeId", UUID)
CoverLetterTemplateId = NewType("CoverLetterTemplateId", UUID)
AnswerId = NewType("AnswerId", UUID)
JobPostingId = NewType("JobPostingId", UUID)
ApplicationId = NewType("ApplicationId", UUID)


def new_profile_id() -> ProfileId:
    """Generate a new, unique ProfileId."""
    return ProfileId(uuid4())


def new_resume_id() -> ResumeId:
    """Generate a new, unique ResumeId."""
    return ResumeId(uuid4())


def new_cover_letter_template_id() -> CoverLetterTemplateId:
    """Generate a new, unique CoverLetterTemplateId."""
    return CoverLetterTemplateId(uuid4())


def new_answer_id() -> AnswerId:
    """Generate a new, unique AnswerId."""
    return AnswerId(uuid4())


def new_job_posting_id() -> JobPostingId:
    """Generate a new, unique JobPostingId."""
    return JobPostingId(uuid4())


def new_application_id() -> ApplicationId:
    """Generate a new, unique ApplicationId."""
    return ApplicationId(uuid4())
