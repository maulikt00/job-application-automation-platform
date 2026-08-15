"""Domain models: plain data objects describing what the business
concepts are (a Profile, a Resume, a JobPosting, an Application),
independent of how they are stored or displayed.

Re-exported here so callers can write:
    from jaap.domain.models import Profile, Application, new_profile_id
instead of reaching into individual submodules.
"""

from jaap.domain.models.answer import Answer
from jaap.domain.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusEvent,
)
from jaap.domain.models.cover_letter_template import CoverLetterTemplate
from jaap.domain.models.entity import Entity
from jaap.domain.models.ids import (
    AnswerId,
    ApplicationId,
    CoverLetterTemplateId,
    JobPostingId,
    ProfileId,
    ResumeId,
    new_answer_id,
    new_application_id,
    new_cover_letter_template_id,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from jaap.domain.models.job_posting import JobPlatform, JobPosting
from jaap.domain.models.profile import Profile
from jaap.domain.models.resume import Resume

__all__ = [
    "Answer",
    "AnswerId",
    "Application",
    "ApplicationId",
    "ApplicationStatus",
    "ApplicationStatusEvent",
    "CoverLetterTemplate",
    "CoverLetterTemplateId",
    "Entity",
    "JobPlatform",
    "JobPosting",
    "JobPostingId",
    "Profile",
    "ProfileId",
    "Resume",
    "ResumeId",
    "new_answer_id",
    "new_application_id",
    "new_cover_letter_template_id",
    "new_job_posting_id",
    "new_profile_id",
    "new_resume_id",
]
