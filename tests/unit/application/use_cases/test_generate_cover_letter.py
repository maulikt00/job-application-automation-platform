"""Tests for GenerateCoverLetterUseCase -- the first real use-case-level
consumer of AIProvider. Uses a fake AIProvider (no real API call anywhere)
alongside fake repositories, matching the established fakes.py pattern.
"""

from __future__ import annotations

import pytest

from jaap.application.exceptions import (
    CoverLetterTemplateNotFoundError,
    JobPostingNotFoundError,
    ProfileNotFoundError,
)
from jaap.application.use_cases.generate_cover_letter import GenerateCoverLetterUseCase
from jaap.domain.models import (
    CoverLetterTemplate,
    JobPosting,
    Profile,
    new_cover_letter_template_id,
    new_job_posting_id,
    new_profile_id,
)
from tests.unit.application.use_cases.fakes import (
    FakeCoverLetterTemplateRepository,
    FakeJobPostingRepository,
    FakeProfileRepository,
)


class _FakeAIProvider:
    """Records every call it receives and returns a fixed response --
    a simple, purpose-built fake, not a mock, matching this project's
    established preference (repositories/engines/detectors are all
    hand-written fakes, not unittest.mock objects, except where a
    third-party SDK's real response shape needs to be matched exactly).
    """

    def __init__(self, response: str = "Generated cover letter text.") -> None:
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        self.calls.append((prompt, system_prompt))
        return self.response


def _make_use_case(ai_provider=None):
    profile_repo = FakeProfileRepository()
    posting_repo = FakeJobPostingRepository()
    template_repo = FakeCoverLetterTemplateRepository()
    use_case = GenerateCoverLetterUseCase(
        ai_provider=ai_provider or _FakeAIProvider(),
        profile_repository=profile_repo,
        job_posting_repository=posting_repo,
        cover_letter_template_repository=template_repo,
    )
    return use_case, profile_repo, posting_repo, template_repo


def test_returns_the_ai_providers_generated_text() -> None:
    ai_provider = _FakeAIProvider(response="Dear Acme, I am excited to apply.")
    use_case, profile_repo, posting_repo, _ = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")
    profile_repo.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    posting_repo.save(posting)

    result = use_case.execute(profile.id, posting.id)

    assert result == "Dear Acme, I am excited to apply."


def test_prompt_includes_applicant_name_and_company_and_title() -> None:
    ai_provider = _FakeAIProvider()
    use_case, profile_repo, posting_repo, _ = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="Maulik Patel", email="m@example.com")
    profile_repo.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme Corp", title="Senior Engineer",
        url="https://acme.example.com/1",
    )
    posting_repo.save(posting)

    use_case.execute(profile.id, posting.id)

    prompt, system_prompt = ai_provider.calls[0]
    assert "Maulik Patel" in prompt
    assert "Acme Corp" in prompt
    assert "Senior Engineer" in prompt
    assert system_prompt is not None
    assert "do not invent" in system_prompt.lower()


def test_prompt_includes_the_template_body_when_a_template_id_is_given() -> None:
    ai_provider = _FakeAIProvider()
    use_case, profile_repo, posting_repo, template_repo = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    posting_repo.save(posting)
    template = CoverLetterTemplate(
        id=new_cover_letter_template_id(), profile_id=profile.id,
        name="Standard", body_template="Dear team, I bring strong communication skills...",
    )
    template_repo.save(template)

    use_case.execute(profile.id, posting.id, template_id=template.id)

    prompt, _ = ai_provider.calls[0]
    assert "strong communication skills" in prompt


def test_prompt_has_no_template_reference_when_template_id_is_omitted() -> None:
    ai_provider = _FakeAIProvider()
    use_case, profile_repo, posting_repo, _ = _make_use_case(ai_provider)
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    posting_repo.save(posting)

    use_case.execute(profile.id, posting.id)

    prompt, _ = ai_provider.calls[0]
    assert "template" not in prompt.lower()


def test_raises_profile_not_found_for_missing_profile() -> None:
    use_case, _, posting_repo, _ = _make_use_case()
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    posting_repo.save(posting)

    with pytest.raises(ProfileNotFoundError):
        use_case.execute(new_profile_id(), posting.id)


def test_raises_job_posting_not_found_for_missing_posting() -> None:
    use_case, profile_repo, _, _ = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)

    with pytest.raises(JobPostingNotFoundError):
        use_case.execute(profile.id, new_job_posting_id())


def test_raises_cover_letter_template_not_found_when_template_id_does_not_resolve() -> None:
    use_case, profile_repo, posting_repo, _ = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    posting_repo.save(posting)

    with pytest.raises(CoverLetterTemplateNotFoundError):
        use_case.execute(profile.id, posting.id, template_id=new_cover_letter_template_id())


def test_never_saves_anything_itself() -> None:
    # The core human-review guarantee: this use case must not persist the
    # generated text anywhere on its own -- the caller decides.
    use_case, profile_repo, posting_repo, template_repo = _make_use_case()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    profile_repo.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    posting_repo.save(posting)

    use_case.execute(profile.id, posting.id)

    assert template_repo.list_by_profile(profile.id) == []
