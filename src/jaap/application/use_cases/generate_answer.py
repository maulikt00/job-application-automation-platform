"""GenerateAnswerUseCase: draft a reusable answer using an AIProvider.

The second real use-case-level consumer of AIProvider (after Milestone
16's GenerateCoverLetterUseCase). Shares the same honest scope
limitation stated there: this project has no resume-text-extraction
capability, so the generated answer works only from the Profile's name,
the question being asked, and the person's own existing saved Answers
(passed as context for tone/consistency) -- it cannot reference specific
work history or achievements it was never given.

Deliberately does NOT take a job_posting_id, unlike GenerateCoverLetterUseCase.
The roadmap calls these "reusable-answer suggestions" -- Answer has been
designed since Milestone 2 for exact-match reuse across many applications
(ExactFieldMatcher, Milestone 10). If this use case tailored an answer to
one specific company (e.g. "I'm excited to work at Acme specifically
because..."), saving that as a reusable Answer would then be actively
wrong the next time it's reused verbatim for a different company. Kept
company-agnostic on purpose, so what gets generated is genuinely
appropriate to save and reuse -- not a one-off answer mislabeled as
reusable.

Never saves anything and never touches SubmitApplicationUseCase, exactly
like GenerateCoverLetterUseCase (ADR-0017) -- the caller decides whether
to save the result via the already-existing `jaap answer save` command.
"""

from __future__ import annotations

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.interfaces.ai_provider import AIProvider
from jaap.application.interfaces.repositories import AnswerRepository, ProfileRepository
from jaap.domain.models import Answer, Profile
from jaap.domain.models.ids import ProfileId

_SYSTEM_PROMPT = (
    "You are helping a job applicant draft a reusable answer to a common "
    "application question. Write in first person, in a professional but "
    "natural tone, in one or two short paragraphs. Only use the facts "
    "given to you below -- do not invent or assume specific work history, "
    "skills, or achievements, since none were provided in this request. "
    "This answer is meant to be reused across many different job "
    "applications, so do NOT mention any specific company, employer, or "
    "job title, even if one is implied by the question -- keep the answer "
    "general enough to apply anywhere. If the applicant's previous "
    "answers are given below, use them only to stay consistent in tone "
    "and substance; do not copy them verbatim, since they answer a "
    "different question."
)


class GenerateAnswerUseCase:
    """Composes a prompt from a Profile, the question being asked, and
    the person's existing saved Answers (for consistency), and asks the
    injected AIProvider to draft a candidate answer. Returns the
    generated text as a plain str -- no DTO, matching
    GenerateCoverLetterUseCase's precedent (ADR-0006's discipline).
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        profile_repository: ProfileRepository,
        answer_repository: AnswerRepository,
    ) -> None:
        self._ai_provider = ai_provider
        self._profile_repository = profile_repository
        self._answer_repository = answer_repository

    def execute(self, profile_id: ProfileId, question: str) -> str:
        profile = self._profile_repository.get(profile_id)
        if profile is None:
            raise ProfileNotFoundError(profile_id)

        existing_answers = self._answer_repository.list_by_profile(profile_id)
        prompt = _build_prompt(profile, question, existing_answers)
        return self._ai_provider.generate_text(prompt, system_prompt=_SYSTEM_PROMPT)


def _build_prompt(profile: Profile, question: str, existing_answers: list[Answer]) -> str:
    """Pure transformation: already-loaded domain objects in, a prompt
    string out. A private module-level function, matching
    GenerateCoverLetterUseCase's _build_prompt() and
    SubmitApplicationUseCase's _build_content_snapshot() (ADR-0013/0017):
    one caller, no anticipated second implementation.
    """
    lines = [
        f"Applicant name: {profile.full_name}",
        f"Question to answer: {question}",
    ]
    if existing_answers:
        lines.append("")
        lines.append("This applicant's previous answers to other questions (for consistency only):")
        for answer in existing_answers:
            lines.append(f"- Q: {answer.question_key} / A: {answer.answer_text}")
    return "\n".join(lines)
