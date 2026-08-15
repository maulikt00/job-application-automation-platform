"""Tests for the Answer domain model."""

import pytest
from pydantic import ValidationError

from jaap.domain.models import Answer, new_answer_id, new_profile_id


def test_valid_answer_is_created() -> None:
    answer = Answer(
        id=new_answer_id(),
        profile_id=new_profile_id(),
        question_key="Why do you want to work here?",
        answer_text="Because of the mission and the team.",
    )
    assert answer.question_key == "why-do-you-want-to-work-here"
    assert answer.tags == []


def test_question_key_is_normalized_to_a_slug() -> None:
    answer = Answer(
        id=new_answer_id(),
        profile_id=new_profile_id(),
        question_key="  What's Your Greatest Strength?!  ",
        answer_text="Attention to detail.",
    )
    assert answer.question_key == "what-s-your-greatest-strength"


def test_question_key_with_no_alphanumerics_raises() -> None:
    with pytest.raises(ValidationError):
        Answer(
            id=new_answer_id(),
            profile_id=new_profile_id(),
            question_key="???",
            answer_text="N/A",
        )


def test_empty_answer_text_raises() -> None:
    with pytest.raises(ValidationError):
        Answer(
            id=new_answer_id(),
            profile_id=new_profile_id(),
            question_key="why-us",
            answer_text="",
        )


def test_tags_default_to_empty_and_can_be_set() -> None:
    answer = Answer(
        id=new_answer_id(),
        profile_id=new_profile_id(),
        question_key="why-us",
        answer_text="Because...",
        tags=["common", "behavioral"],
    )
    assert answer.tags == ["common", "behavioral"]


def test_reassigning_question_key_after_creation_is_renormalized() -> None:
    # validate_assignment=True (ADR-0003) means the slugify validator
    # re-runs on assignment, not just at construction.
    answer = Answer(
        id=new_answer_id(),
        profile_id=new_profile_id(),
        question_key="why-us",
        answer_text="Because...",
    )

    answer.question_key = "  A Whole New Question?!  "
    assert answer.question_key == "a-whole-new-question"
