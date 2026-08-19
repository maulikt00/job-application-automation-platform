"""Tests for SaveAnswerUseCase."""

from __future__ import annotations

import pytest

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.use_cases.manage_answers import SaveAnswerUseCase
from jaap.domain.models import Profile, new_profile_id
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeProfileRepository,
)


def _make_use_case():
    answer_repo = FakeAnswerRepository()
    profile_repo = FakeProfileRepository()
    return SaveAnswerUseCase(answer_repo, profile_repo), answer_repo, profile_repo


def test_creates_an_answer_for_an_existing_profile() -> None:
    use_case, answer_repo, profile_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    answer = use_case.execute(
        profile_id=profile.id, question_key="why us", answer_text="Because...", tags=["common"]
    )

    assert answer.profile_id == profile.id
    assert answer.question_key == "why-us"  # normalized by the domain model
    assert answer_repo.get(answer.id) == answer


def test_passing_answer_id_updates_the_existing_answer() -> None:
    use_case, answer_repo, profile_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    original = use_case.execute(profile_id=profile.id, question_key="why-us", answer_text="v1")

    updated = use_case.execute(
        profile_id=profile.id, question_key="why-us", answer_text="v2", answer_id=original.id
    )

    assert updated.id == original.id
    assert answer_repo.get(original.id).answer_text == "v2"


def test_tags_default_to_empty_list() -> None:
    use_case, _, profile_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    answer = use_case.execute(profile_id=profile.id, question_key="why-us", answer_text="...")

    assert answer.tags == []


def test_raises_profile_not_found_when_profile_does_not_exist() -> None:
    use_case, _, _ = _make_use_case()

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(profile_id=new_profile_id(), question_key="why-us", answer_text="...")
