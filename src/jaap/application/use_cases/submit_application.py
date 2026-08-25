"""SubmitApplicationUseCase: move a Draft Application to SUBMITTED.

This is the use case docs/adr/0002-progressive-application-lifecycle.md
pointed to when it deferred "is this ready to submit" out of the domain
model: `Application` allows an incomplete Draft to be perfectly valid,
and readiness is entirely a business-process question this use case
answers, not `Application` itself.

Also builds and records the SubmittedContentSnapshot (Milestone 13,
ADR-0013): durable, immutable evidence of what was actually submitted --
resolved here, at the one moment submission actually happens, from
whichever Resume/Answers/CoverLetterTemplate the Application currently
references (or an ad-hoc `cover_letter_text_override`, for Milestone 16's
AI-generated, possibly never-saved cover letters).
"""

from __future__ import annotations

from jaap.application.exceptions import (
    AnswerNotFoundError,
    ApplicationNotFoundError,
    ApplicationNotReadyForSubmissionError,
    CoverLetterTemplateNotFoundError,
    ResumeNotFoundError,
)
from jaap.application.interfaces.repositories import (
    AnswerRepository,
    ApplicationRepository,
    CoverLetterTemplateRepository,
    ResumeRepository,
)
from jaap.domain.models import (
    Answer,
    Application,
    ApplicationId,
    ApplicationStatus,
    Resume,
)
from jaap.domain.models.application import SubmittedAnswer, SubmittedContentSnapshot


class SubmitApplicationUseCase:
    """Transitions a Draft Application to SUBMITTED.

    Enforces exactly the one readiness rule ADR-0002 named explicitly --
    a resume must be attached -- deliberately not inventing additional
    requirements the ADR didn't state. Structural validity of the
    transition itself (e.g. rejecting a submit on an already-SUBMITTED or
    WITHDRAWN application) is NOT re-checked here: that's `transition_to()`'s
    job as a domain invariant (see ADR-0002/0003), and this use case lets
    `InvalidStatusTransitionError` propagate unmodified rather than
    duplicating that check.

    Depends on ResumeRepository, AnswerRepository, and
    CoverLetterTemplateRepository in addition to ApplicationRepository --
    evaluated explicitly against introducing a new aggregating
    abstraction (see ADR-0013) and rejected: multiple repositories
    injected directly into one use case is already this project's
    established pattern (StartApplicationUseCase, AutofillApplicationUseCase),
    not a new one being introduced here.
    """

    def __init__(
        self,
        application_repository: ApplicationRepository,
        resume_repository: ResumeRepository,
        answer_repository: AnswerRepository,
        cover_letter_template_repository: CoverLetterTemplateRepository,
    ) -> None:
        self._application_repository = application_repository
        self._resume_repository = resume_repository
        self._answer_repository = answer_repository
        self._cover_letter_template_repository = cover_letter_template_repository

    def execute(
        self,
        application_id: ApplicationId,
        cover_letter_text_override: str | None = None,
    ) -> Application:
        application = self._application_repository.get(application_id)
        if application is None:
            raise ApplicationNotFoundError(application_id)

        if application.resume_id is None:
            raise ApplicationNotReadyForSubmissionError(
                application_id, "a resume must be attached before submission"
            )

        resume = self._resume_repository.get(application.resume_id)
        if resume is None:
            raise ResumeNotFoundError(application.resume_id)

        answers = self._resolve_answers(application)
        cover_letter_text = self._resolve_cover_letter_text(
            application, cover_letter_text_override
        )

        snapshot = _build_content_snapshot(
            resume=resume, answers=answers, cover_letter_text=cover_letter_text
        )

        application.transition_to(ApplicationStatus.SUBMITTED, content_snapshot=snapshot)
        self._application_repository.save(application)
        return application

    def _resolve_answers(self, application: Application) -> list[Answer]:
        answers: list[Answer] = []
        for answer_id in application.answer_ids:
            answer = self._answer_repository.get(answer_id)
            if answer is None:
                raise AnswerNotFoundError(answer_id)
            answers.append(answer)
        return answers

    def _resolve_cover_letter_text(
        self, application: Application, cover_letter_text_override: str | None
    ) -> str | None:
        if cover_letter_text_override is not None:
            return cover_letter_text_override
        if application.cover_letter_template_id is None:
            return None
        template = self._cover_letter_template_repository.get(
            application.cover_letter_template_id
        )
        if template is None:
            raise CoverLetterTemplateNotFoundError(application.cover_letter_template_id)
        return template.body_template


def _build_content_snapshot(
    *,
    resume: Resume,
    answers: list[Answer],
    cover_letter_text: str | None,
) -> SubmittedContentSnapshot:
    """Pure transformation: already-loaded domain objects in, an
    immutable SubmittedContentSnapshot out. No repository access, no I/O
    -- deliberately a plain module-level function, not a class or
    Protocol (see ADR-0013): this has exactly one caller and no
    anticipated second implementation, unlike ExactFieldMatcher, which
    earns its Protocol from a real, already-planned future alternative
    (an AI-assisted matcher, Phase 3).
    """
    return SubmittedContentSnapshot(
        resume_label=resume.label,
        resume_file_name=resume.file_path.name,
        cover_letter_text=cover_letter_text,
        answers=tuple(
            SubmittedAnswer(question_key=answer.question_key, answer_text=answer.answer_text)
            for answer in answers
        ),
    )
