"""RecommendResumeUseCase: suggest which stored Resume best fits a
JobPosting.

The third real use-case-level consumer of AIProvider, and the sharpest
version yet of a limitation named honestly since Milestone 16: this
project has no resume-text-extraction capability. Resume is just a
`label` plus a file path -- nothing parses a resume file's actual
content into text an LLM could read. This use case therefore CANNOT
compare what's actually in each resume against the job posting; all it
can compare is each Resume's `label` (a short, human-chosen name, e.g.
"Backend-focused") against the job's title and company. The
recommendation is genuinely useful for that narrow comparison -- an LLM
is good at judging whether "Backend-focused" fits "Senior Backend
Engineer" better than "Frontend-focused" does -- but it is not, and
cannot be, a judgment about the resume's actual content or
qualifications. The reasoning returned alongside the recommendation
makes this visible to the human reviewing it, not hidden.

Zero and one-resume cases never call the AI at all -- there's no
genuine choice to make, and spending an API call on a forced answer
would be wasteful. The AI is only consulted when there are at least two
resumes to choose between.

AIProvider's interface is exactly one primitive, generate_text() -> str
(ADR-0014) -- there is no structured-output method. To reliably extract
which specific resume was chosen from free text, the prompt asks for a
strict, minimal response format (the chosen option's number, then a
blank line, then reasoning) and the response is parsed accordingly. A
response that doesn't follow this format raises ValueError, matching
the existing precedent for this project's own parsing-failure exceptions
(e.g. BrowserAutomationEngine.evaluate()'s JSON round-trip check).
"""

from __future__ import annotations

from pydantic import BaseModel

from jaap.application.exceptions import (
    JobPostingNotFoundError,
    NoResumesAvailableError,
    ProfileNotFoundError,
)
from jaap.application.interfaces.ai_provider import AIProvider
from jaap.application.interfaces.repositories import (
    JobPostingRepository,
    ProfileRepository,
    ResumeRepository,
)
from jaap.domain.models import JobPosting, Resume
from jaap.domain.models.ids import JobPostingId, ProfileId

_SYSTEM_PROMPT = (
    "You are helping a job applicant choose which of their saved resumes "
    "best fits a job posting. You can only see each resume's short label "
    "(e.g. 'Backend-focused') and the job's title and company -- you "
    "cannot see the actual content of any resume. Base your recommendation "
    "only on how well each label's implied focus matches the job's title. "
    "Respond in EXACTLY this format and nothing else: the number of your "
    "chosen resume alone on the first line, then a blank line, then one "
    "or two sentences of reasoning on the following line(s)."
)


class ResumeRecommendation(BaseModel):
    """A suggested Resume plus the reasoning behind it, so a human can
    evaluate the suggestion rather than accept it blindly -- especially
    important here given how little the recommendation is actually based
    on (see this module's docstring)."""

    recommended_resume: Resume
    reasoning: str


class RecommendResumeUseCase:
    def __init__(
        self,
        ai_provider: AIProvider,
        resume_repository: ResumeRepository,
        profile_repository: ProfileRepository,
        job_posting_repository: JobPostingRepository,
    ) -> None:
        self._ai_provider = ai_provider
        self._resume_repository = resume_repository
        self._profile_repository = profile_repository
        self._job_posting_repository = job_posting_repository

    def execute(self, profile_id: ProfileId, job_posting_id: JobPostingId) -> ResumeRecommendation:
        if self._profile_repository.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)

        posting = self._job_posting_repository.get(job_posting_id)
        if posting is None:
            raise JobPostingNotFoundError(job_posting_id)

        resumes = self._resume_repository.list_by_profile(profile_id)
        if not resumes:
            raise NoResumesAvailableError(profile_id)
        if len(resumes) == 1:
            return ResumeRecommendation(
                recommended_resume=resumes[0], reasoning="Only resume available."
            )

        prompt = _build_prompt(resumes, posting)
        response = self._ai_provider.generate_text(prompt, system_prompt=_SYSTEM_PROMPT)
        chosen_index = _parse_choice(response, len(resumes))
        return ResumeRecommendation(
            recommended_resume=resumes[chosen_index], reasoning=_parse_reasoning(response)
        )


def _build_prompt(resumes: list[Resume], posting: JobPosting) -> str:
    """Pure transformation: already-loaded domain objects in, a prompt
    string out. A private module-level function, matching the precedent
    from every prior AIProvider-consuming use case (ADR-0013/0017/0018):
    one caller, no anticipated second implementation.
    """
    lines = [
        f"Job title: {posting.title}",
        f"Company: {posting.company_name}",
        "",
        "Available resumes:",
    ]
    for index, resume in enumerate(resumes, start=1):
        lines.append(f"{index}. {resume.label}")
    return "\n".join(lines)


def _parse_choice(response: str, option_count: int) -> int:
    """Returns a 0-based index into the original resumes list, parsed
    from the AI's response's first line (a 1-based option number, per
    the system prompt's required format)."""
    first_line = response.strip().splitlines()[0].strip()
    try:
        choice = int(first_line)
    except ValueError as exc:
        raise ValueError(
            f"Could not parse a resume choice from the AI's response: {response!r}"
        ) from exc
    if not (1 <= choice <= option_count):
        raise ValueError(
            f"AI chose option {choice}, outside the valid range 1-{option_count}: {response!r}"
        )
    return choice - 1


def _parse_reasoning(response: str) -> str:
    """Everything after the first blank line, per the system prompt's
    required format; falls back to the whole response (minus the first
    line) if no blank line is present, rather than raising -- reasoning
    text is explanatory, not load-bearing the way the choice number is,
    so a lenient fallback here is reasonable."""
    lines = response.strip().splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "" and i + 1 < len(lines):
            return "\n".join(lines[i + 1 :]).strip()
    return "\n".join(lines[1:]).strip()
