"""Tests for RecommendResumeUseCase -- the third real use-case-level
consumer of AIProvider. Uses a fake AIProvider (no real API call
anywhere) alongside fake repositories.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jaap.application.exceptions import (
    JobPostingNotFoundError,
    NoResumesAvailableError,
    ProfileNotFoundError,
)
from jaap.application.use_cases.recommend_resume import RecommendResumeUseCase
from jaap.domain.models import (
    JobPosting,
    Profile,
    Resume,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from tests.unit.application.use_cases.fakes import (
    FakeJobPostingRepository,
    FakeProfileRepository,
    FakeResumeRepository,
)


class _FakeAIProvider:
    def __init__(self, response: str = "1\n\nBest fit.") -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        self.calls.append((prompt, system_prompt))
        return self.response


def _make_use_case(ai_provider=None):
    resume_repo = FakeResumeRepository()
    profile_repo = FakeProfileRepository()
    posting_repo = FakeJobPostingRepository()
    use_case = RecommendResumeUseCase(
        ai_provider=ai_provider or _FakeAIProvider(),
        resume_repository=resume_repo,
        profile_repository=profile_repo,
        job_posting_repository=posting_repo,
    )
    return use_case, resume_repo, profile_repo, posting_repo


def _seed_profile_and_posting(profile_repo, posting_repo):
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Senior Backend Engineer",
        url="https://acme.example.com/1",
    )
    posting_repo.save(posting)
    return profile, posting


def test_raises_profile_not_found_for_missing_profile() -> None:
    use_case, _, _, posting_repo = _make_use_case()
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    posting_repo.save(posting)

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(new_profile_id(), posting.id)


def test_raises_job_posting_not_found_for_missing_posting() -> None:
    use_case, _, profile_repo, _ = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    with pytest.raises(JobPostingNotFoundError):
        use_case.execute(profile.id, new_job_posting_id())


def test_raises_no_resumes_available_when_profile_has_none() -> None:
    use_case, _, profile_repo, posting_repo = _make_use_case()
    profile, posting = _seed_profile_and_posting(profile_repo, posting_repo)

    with pytest.raises(NoResumesAvailableError):
        use_case.execute(profile.id, posting.id)


def test_single_resume_is_recommended_without_calling_the_ai() -> None:
    ai_provider = _FakeAIProvider()
    use_case, resume_repo, profile_repo, posting_repo = _make_use_case(ai_provider)
    profile, posting = _seed_profile_and_posting(profile_repo, posting_repo)
    resume = Resume(id=new_resume_id(), profile_id=profile.id, label="Generalist", file_path=Path("r.pdf"))
    resume_repo.save(resume)

    result = use_case.execute(profile.id, posting.id)

    assert result.recommended_resume == resume
    assert result.reasoning == "Only resume available."
    assert ai_provider.calls == []


def test_multiple_resumes_calls_the_ai_and_returns_the_chosen_one() -> None:
    ai_provider = _FakeAIProvider(response="2\n\nThe backend-focused resume fits this role better.")
    use_case, resume_repo, profile_repo, posting_repo = _make_use_case(ai_provider)
    profile, posting = _seed_profile_and_posting(profile_repo, posting_repo)
    frontend = Resume(
        id=new_resume_id(), profile_id=profile.id, label="Frontend-focused", file_path=Path("f.pdf")
    )
    backend = Resume(
        id=new_resume_id(), profile_id=profile.id, label="Backend-focused", file_path=Path("b.pdf")
    )
    resume_repo.save(frontend)
    resume_repo.save(backend)

    result = use_case.execute(profile.id, posting.id)

    assert result.recommended_resume == backend
    assert result.reasoning == "The backend-focused resume fits this role better."
    assert len(ai_provider.calls) == 1


def test_prompt_lists_resume_labels_and_job_details() -> None:
    ai_provider = _FakeAIProvider()
    use_case, resume_repo, profile_repo, posting_repo = _make_use_case(ai_provider)
    profile, posting = _seed_profile_and_posting(profile_repo, posting_repo)
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="A", file_path=Path("a.pdf")))
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="B", file_path=Path("b.pdf")))

    use_case.execute(profile.id, posting.id)

    prompt, system_prompt = ai_provider.calls[0]
    assert "Senior Backend Engineer" in prompt
    assert "Acme" in prompt
    assert "1. A" in prompt
    assert "2. B" in prompt
    assert system_prompt is not None
    assert "cannot see the actual content" in system_prompt


def test_malformed_ai_response_raises_value_error() -> None:
    ai_provider = _FakeAIProvider(response="I think the first one is best.")
    use_case, resume_repo, profile_repo, posting_repo = _make_use_case(ai_provider)
    profile, posting = _seed_profile_and_posting(profile_repo, posting_repo)
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="A", file_path=Path("a.pdf")))
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="B", file_path=Path("b.pdf")))

    with pytest.raises(ValueError, match="Could not parse"):
        use_case.execute(profile.id, posting.id)


def test_out_of_range_choice_raises_value_error() -> None:
    ai_provider = _FakeAIProvider(response="5\n\nreasoning")
    use_case, resume_repo, profile_repo, posting_repo = _make_use_case(ai_provider)
    profile, posting = _seed_profile_and_posting(profile_repo, posting_repo)
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="A", file_path=Path("a.pdf")))
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="B", file_path=Path("b.pdf")))

    with pytest.raises(ValueError, match="outside the valid range"):
        use_case.execute(profile.id, posting.id)


def test_reasoning_falls_back_when_no_blank_line_is_present() -> None:
    ai_provider = _FakeAIProvider(response="1\nJust one line of reasoning, no blank line.")
    use_case, resume_repo, profile_repo, posting_repo = _make_use_case(ai_provider)
    profile, posting = _seed_profile_and_posting(profile_repo, posting_repo)
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="A", file_path=Path("a.pdf")))
    resume_repo.save(Resume(id=new_resume_id(), profile_id=profile.id, label="B", file_path=Path("b.pdf")))

    result = use_case.execute(profile.id, posting.id)

    assert result.reasoning == "Just one line of reasoning, no blank line."
