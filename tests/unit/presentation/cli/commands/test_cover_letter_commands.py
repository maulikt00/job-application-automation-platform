"""Tests for cover_letter_commands."""

from __future__ import annotations

import argparse

import pytest

from jaap.application.exceptions import JobPostingNotFoundError, ProfileNotFoundError
from jaap.domain.models import (
    Profile,
    new_cover_letter_template_id,
    new_job_posting_id,
    new_profile_id,
)
from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.commands.cover_letter_commands import (
    _handle_generate,
    _handle_list,
    _handle_save,
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


def test_handle_save_creates_a_template_for_an_existing_profile(capsys) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    args = argparse.Namespace(
        profile_id=profile.id, name="Standard", body_template="Dear team...", template_id=None
    )

    exit_code = _handle_save(args, context)

    assert exit_code == 0
    assert "Standard" in capsys.readouterr().out


def test_handle_save_raises_for_missing_profile() -> None:
    context = _make_context()
    args = argparse.Namespace(
        profile_id=new_profile_id(), name="Standard", body_template="Dear team...",
        template_id=None,
    )

    with pytest.raises(ProfileNotFoundError):
        _handle_save(args, context)


def test_handle_save_updates_an_existing_template_when_template_id_is_given() -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    existing_id = new_cover_letter_template_id()
    create_args = argparse.Namespace(
        profile_id=profile.id, name="Standard", body_template="original",
        template_id=existing_id,
    )
    _handle_save(create_args, context)

    update_args = argparse.Namespace(
        profile_id=profile.id, name="Standard", body_template="updated",
        template_id=existing_id,
    )
    _handle_save(update_args, context)

    saved = context.cover_letter_template_repository.get(existing_id)
    assert saved.body_template == "updated"


def test_handle_list_prints_no_templates_when_none_exist(capsys) -> None:
    context = _make_context()
    args = argparse.Namespace(profile_id=new_profile_id())

    exit_code = _handle_list(args, context)

    assert exit_code == 0
    assert "No cover letter templates found." in capsys.readouterr().out


def test_handle_list_prints_each_saved_template(capsys) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    save_args = argparse.Namespace(
        profile_id=profile.id, name="Standard", body_template="Dear team...", template_id=None
    )
    _handle_save(save_args, context)

    list_args = argparse.Namespace(profile_id=profile.id)
    exit_code = _handle_list(list_args, context)

    assert exit_code == 0
    assert "Standard" in capsys.readouterr().out


def test_handle_generate_raises_profile_not_found_before_calling_claude() -> None:
    # _handle_generate constructs a real ClaudeProvider internally (it's
    # composition-root-style code, like _handle_review's real
    # PlaywrightBrowserEngine), so it can't be fully unit-tested with
    # fakes -- but the profile/posting/template lookups all happen
    # BEFORE any AI call, so these specific paths are fast and
    # fake-testable, matching test_handle_review's equivalent pattern.
    context = _make_context()
    args = argparse.Namespace(
        profile_id=new_profile_id(),
        job_posting_id=new_job_posting_id(),
        template_id=None,
        save_as=None,
    )

    with pytest.raises(ProfileNotFoundError):
        _handle_generate(args, context)


def test_handle_generate_raises_job_posting_not_found_before_calling_claude() -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    args = argparse.Namespace(
        profile_id=profile.id,
        job_posting_id=new_job_posting_id(),
        template_id=None,
        save_as=None,
    )

    with pytest.raises(JobPostingNotFoundError):
        _handle_generate(args, context)
