"""Answer domain model.

A reusable answer to a common application question (e.g. "Why do you want
to work here?"). Answers are created once per Profile and reused across
many Applications, which is why this is its own aggregate root rather than
a field embedded directly in Application.
"""

from __future__ import annotations

from pydantic import ConfigDict, Field, field_validator

from jaap.domain.models.entity import Entity
from jaap.domain.models.ids import AnswerId, ProfileId
from jaap.utils.slugify import slugify


class Answer(Entity):
    """A reusable answer to a common application question.

    Attributes:
        id: Unique identifier for this answer.
        profile_id: The Profile this answer belongs to.
        question_key: A normalized, slug-like key identifying the question
            this answer addresses (e.g. "why-do-you-want-to-work-here"),
            used to look up a relevant answer for a given form field.
        answer_text: The stored answer text.
        tags: Optional free-form tags for organizing/searching answers.
    """

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    id: AnswerId
    profile_id: ProfileId
    question_key: str = Field(..., min_length=1)
    answer_text: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("question_key")
    @classmethod
    def _normalize_question_key(cls, value: str) -> str:
        slug = slugify(value)
        if not slug:
            raise ValueError("question_key must contain at least one alphanumeric character")
        return slug
