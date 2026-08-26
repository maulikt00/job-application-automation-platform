"""Tests for resume_commands."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from jaap.application.exceptions import JobPostingNotFoundError, ProfileNotFoundError
from jaap.domain.models import Profile, new_job_posting_id, new_profile_id
from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.commands.resume_commands import (
    _handle_add,
    _handle_recommend,
)
from jaap.presentation.cli.main import Context
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeApplicationRepository,
    FakeCoverLetterTemplateRepository,
    FakeJobPostingRepository,
    FakeProfileRepository,
    FakeResumeRepository,
)


def _make_context() -> Context:
    return Context(
        profile_repository=FakeProfileRepository(),
        resume_repository=FakeResumeRepository(),
        job_posting_repository=FakeJobPostingRepository(),
        application_repository=FakeApplicationRepository(),
        answer_repository=FakeAnswerRepository(),
        cover_letter_template_repository=FakeCoverLetterTemplateRepository(),
        settings=Settings(_env_file=None),
    )


def test_handle_add_adds_a_resume_for_an_existing_profile(capsys) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    args = argparse.Namespace(profile_id=profile.id, label="Backend", file_path=Path("r.pdf"))

    exit_code = _handle_add(args, context)

    assert exit_code == 0
    assert "Backend" in capsys.readouterr().out


def test_handle_add_raises_for_missing_profile() -> None:
    context = _make_context()
    args = argparse.Namespace(profile_id=new_profile_id(), label="Backend", file_path=Path("r.pdf"))

    with pytest.raises(ProfileNotFoundError):
        _handle_add(args, context)


def test_handle_recommend_raises_profile_not_found_before_calling_claude() -> None:
    # _handle_recommend constructs a real ClaudeProvider internally (same
    # composition-root-style pattern as the other AI-backed CLI
    # commands), so it can't be fully unit-tested with fakes -- but the
    # profile/posting lookups happen BEFORE any AI call, so these
    # specific paths are fast and fake-testable.
    context = _make_context()
    args = argparse.Namespace(
        profile_id=new_profile_id(), job_posting_id=new_job_posting_id(), provider="claude"
    )

    with pytest.raises(ProfileNotFoundError):
        _handle_recommend(args, context)


def test_handle_recommend_raises_job_posting_not_found_before_calling_claude() -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    args = argparse.Namespace(
        profile_id=profile.id, job_posting_id=new_job_posting_id(), provider="claude"
    )

    with pytest.raises(JobPostingNotFoundError):
        _handle_recommend(args, context)
