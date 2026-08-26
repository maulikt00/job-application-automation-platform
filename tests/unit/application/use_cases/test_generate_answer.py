"""Tests for GenerateAnswerUseCase -- the second real use-case-level
consumer of AIProvider. Uses a fake AIProvider (no real API call
anywhere) alongside fake repositories, matching
test_generate_cover_letter.py's established pattern.
"""

from __future__ import annotations

import pytest

from jaap.application.exceptions import ProfileNotFoundError
from jaap.application.use_cases.generate_answer import GenerateAnswerUseCase
from jaap.domain.models import Answer, Profile, new_answer_id, new_profile_id
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeProfileRepository,
)


class _FakeAIProvider:
    def __init__(self, response: str = "Generated answer text.") -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        self.calls.append((prompt, system_prompt))
        return self.response


def _make_use_case(ai_provider=None):
    profile_repo = FakeProfileRepository()
    answer_repo = FakeAnswerRepository()
    use_case = GenerateAnswerUseCase(
        ai_provider=ai_provider or _FakeAIProvider(),
        profile_repository=profile_repo,
        answer_repository=answer_repo,
    )
    return use_case, profile_repo, answer_repo


def test_returns_the_ai_providers_generated_text() -> None:
    ai_provider = _FakeAIProvider(response="I value collaborative, mission-driven teams.")
    use_case, profile_repo, _ = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")
    profile_repo.save(profile)

    result = use_case.execute(profile.id, question="Why do you want to work here?")

    assert result == "I value collaborative, mission-driven teams."


def test_prompt_includes_applicant_name_and_question() -> None:
    ai_provider = _FakeAIProvider()
    use_case, profile_repo, _ = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id, question="What are your greatest strengths?")

    prompt, system_prompt = ai_provider.calls[0]
    assert "Maulik Patel" in prompt
    assert "What are your greatest strengths?" in prompt
    assert system_prompt is not None


def test_system_prompt_forbids_mentioning_a_specific_company() -> None:
    # The core design decision this milestone made deliberately (see
    # ADR-0018): unlike GenerateCoverLetterUseCase, this use case has no
    # job_posting_id at all, and the system prompt must actively instruct
    # against naming any employer, so what gets generated stays safe to
    # reuse across different applications.
    ai_provider = _FakeAIProvider()
    use_case, profile_repo, _ = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id, question="Why do you want to work here?")

    _, system_prompt = ai_provider.calls[0]
    assert "do not mention" in system_prompt.lower() or "not mention" in system_prompt.lower()


def test_prompt_includes_existing_answers_as_context_when_present() -> None:
    ai_provider = _FakeAIProvider()
    use_case, profile_repo, answer_repo = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    existing = Answer(
        id=new_answer_id(), profile_id=profile.id,
        question_key="why-do-you-want-to-work-here",
        answer_text="I value mission-driven teams and continuous learning.",
    )
    answer_repo.save(existing)

    use_case.execute(profile.id, question="What are your greatest strengths?")

    prompt, _ = ai_provider.calls[0]
    assert "mission-driven teams and continuous learning" in prompt


def test_prompt_has_no_previous_answers_section_when_none_exist() -> None:
    ai_provider = _FakeAIProvider()
    use_case, profile_repo, _ = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id, question="What are your greatest strengths?")

    prompt, _ = ai_provider.calls[0]
    assert "previous answers" not in prompt.lower()


def test_raises_profile_not_found_for_missing_profile() -> None:
    use_case, _, _ = _make_use_case()

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(new_profile_id(), question="Why do you want to work here?")


def test_never_saves_anything_itself() -> None:
    use_case, profile_repo, answer_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    use_case.execute(profile.id, question="Why do you want to work here?")

    assert answer_repo.list_by_profile(profile.id) == []
