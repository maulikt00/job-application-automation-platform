"""GenerateCoverLetterUseCase: draft a cover letter using an AIProvider.

The first real use-case-level consumer of AIProvider (Milestone 13-15) --
the milestone ADR-0014/0015/0016 all pointed to when deferring exception
translation. See domain/exceptions.py's AIProviderError.

A real, honest scope limitation, stated plainly rather than glossed
over: this project has no resume-text-extraction capability (Resume is
just a label + a file path; nothing parses the file's actual content
into text an LLM could reference). The prompt built here therefore works
only from what's explicitly available -- the applicant's name and the
job's company/title, plus an optional existing CoverLetterTemplate as a
style/structure reference -- and is deliberately instructed not to
invent specific work history or achievements it was never given. The
result is a reasonable, adaptable draft, not a deeply personalized
letter referencing the applicant's actual experience; that would need
resume text extraction, a different, unbuilt feature.

Never saves anything and never touches SubmitApplicationUseCase --
returns the generated text for a human to review, matching every prior
milestone's human-review discipline (ADR-0001/0012). The caller (the CLI)
decides whether to save it as a reusable CoverLetterTemplate or use it
as one-off text via SubmitApplicationUseCase's cover_letter_text_override
(ADR-0013) -- both paths already exist; this use case only produces the
draft.
"""

from __future__ import annotations

from jaap.application.exceptions import (
    CoverLetterTemplateNotFoundError,
    JobPostingNotFoundError,
    ProfileNotFoundError,
)
from jaap.application.interfaces.ai_provider import AIProvider
from jaap.application.interfaces.repositories import (
    CoverLetterTemplateRepository,
    JobPostingRepository,
    ProfileRepository,
)
from jaap.domain.models import CoverLetterTemplate, JobPosting, Profile
from jaap.domain.models.ids import CoverLetterTemplateId, JobPostingId, ProfileId

_SYSTEM_PROMPT = (
    "You are helping a job applicant draft a cover letter. Write in first "
    "person, in a professional but natural tone. Keep it to three or four "
    "short paragraphs. Only use the specific facts given to you below (the "
    "applicant's name and the job's company and title) -- do not invent or "
    "assume specific work history, skills, or achievements, since none "
    "were provided in this request. If a sample template is given, follow "
    "its overall structure and tone, but write fresh content specific to "
    "this job rather than reusing its text verbatim."
)


class GenerateCoverLetterUseCase:
    """Composes a prompt from Profile + JobPosting (+ an optional existing
    CoverLetterTemplate) and asks the injected AIProvider to draft a
    cover letter. Returns the generated text as a plain str -- no DTO,
    matching ADR-0006's discipline (no abstraction without a concrete need).
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        profile_repository: ProfileRepository,
        job_posting_repository: JobPostingRepository,
        cover_letter_template_repository: CoverLetterTemplateRepository,
    ) -> None:
        self._ai_provider = ai_provider
        self._profile_repository = profile_repository
        self._job_posting_repository = job_posting_repository
        self._cover_letter_template_repository = cover_letter_template_repository

    def execute(
        self,
        profile_id: ProfileId,
        job_posting_id: JobPostingId,
        template_id: CoverLetterTemplateId | None = None,
    ) -> str:
        profile = self._profile_repository.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)

        posting = self._job_posting_repository.get(job_posting_id)
        if posting is None:
            raise JobPostingNotFoundError(job_posting_id)

        template: CoverLetterTemplate | None = None
        if template_id is not None:
            template = self._cover_letter_template_repository.get(template_id)
            if template is None:
                raise CoverLetterTemplateNotFoundError(template_id)

        prompt = _build_prompt(profile, posting, template)
        return self._ai_provider.generate_text(prompt, system_prompt=_SYSTEM_PROMPT)


def _build_prompt(
    profile: Profile, posting: JobPosting, template: CoverLetterTemplate | None
) -> str:
    """Pure transformation: already-loaded domain objects in, a prompt
    string out. A private module-level function, not a class -- same
    reasoning as SubmitApplicationUseCase's _build_content_snapshot()
    (ADR-0013): one caller, no anticipated second implementation.
    """
    lines = [
        f"Applicant name: {profile.full_name}",
        f"Company: {posting.company_name}",
        f"Job title: {posting.title}",
    ]
    if template is not None:
        lines.append("")
        lines.append("Use this existing template as a style/structure reference:")
        lines.append(template.body_template)
    return "\n".join(lines)
