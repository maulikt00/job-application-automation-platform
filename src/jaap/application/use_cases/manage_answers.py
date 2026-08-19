"""SaveAnswerUseCase: upsert a reusable Answer for a Profile."""

from __future__ import annotations

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.interfaces.repositories import AnswerRepository, ProfileRepository
from jaap.domain.models import Answer, AnswerId, ProfileId, new_answer_id


class SaveAnswerUseCase:
    """Creates or updates a reusable Answer.

    Verifies the Profile exists first, same reasoning as AddResumeUseCase
    and SaveCoverLetterTemplateUseCase. Pass `answer_id` to update an
    existing answer; omit it to create a new one.
    """

    def __init__(
        self,
        answer_repository: AnswerRepository,
        profile_repository: ProfileRepository,
    ) -> None:
        self._answer_repository = answer_repository
        self._profile_repository = profile_repository

    def execute(
        self,
        profile_id: ProfileId,
        question_key: str,
        answer_text: str,
        tags: list[str] | None = None,
        answer_id: AnswerId | None = None,
    ) -> Answer:
        if self._profile_repository.get(profile_id) is None:
            raise ProfileNotFoundError(profile_id)

        answer = Answer(
            id=answer_id or new_answer_id(),
            profile_id=profile_id,
            question_key=question_key,
            answer_text=answer_text,
            tags=tags or [],
        )
        self._answer_repository.save(answer)
        return answer
