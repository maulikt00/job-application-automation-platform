"""Tests for answer_commands."""

from __future__ import annotations

import argparse

import pytest

from jaap.application.exceptions import ProfileNotFoundError
from jaap.domain.models import Profile, new_answer_id, new_profile_id
from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.commands.answer_commands import (
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


def test_handle_save_creates_an_answer_for_an_existing_profile(capsys) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    args = argparse.Namespace(
        profile_id=profile.id,
        question_key="Why do you want to work here?",
        answer_text="Because of the mission.",
        tags=None,
        answer_id=None,
    )

    exit_code = _handle_save(args, context)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "why-do-you-want-to-work-here" in output


def test_handle_save_raises_for_missing_profile() -> None:
    context = _make_context()
    args = argparse.Namespace(
        profile_id=new_profile_id(), question_key="q", answer_text="a", tags=None, answer_id=None
    )

    with pytest.raises(ProfileNotFoundError):
        _handle_save(args, context)


def test_handle_save_updates_an_existing_answer_when_answer_id_is_given(capsys) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    existing_id = new_answer_id()
    create_args = argparse.Namespace(
        profile_id=profile.id, question_key="q1", answer_text="original",
        tags=None, answer_id=existing_id,
    )
    _handle_save(create_args, context)

    update_args = argparse.Namespace(
        profile_id=profile.id, question_key="q1", answer_text="updated",
        tags=None, answer_id=existing_id,
    )
    _handle_save(update_args, context)

    saved = context.answer_repository.get(existing_id)
    assert saved.answer_text == "updated"


def test_handle_list_prints_no_answers_when_none_exist(capsys) -> None:
    context = _make_context()
    args = argparse.Namespace(profile_id=new_profile_id())

    exit_code = _handle_list(args, context)

    assert exit_code == 0
    assert "No answers found." in capsys.readouterr().out


def test_handle_list_prints_each_saved_answer(capsys) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    save_args = argparse.Namespace(
        profile_id=profile.id, question_key="Why us?", answer_text="Because.",
        tags=None, answer_id=None,
    )
    _handle_save(save_args, context)

    list_args = argparse.Namespace(profile_id=profile.id)
    exit_code = _handle_list(list_args, context)

    assert exit_code == 0
    assert "why-us" in capsys.readouterr().out


def test_handle_list_truncates_long_answer_text_for_display(capsys) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    long_text = "x" * 100
    save_args = argparse.Namespace(
        profile_id=profile.id, question_key="q", answer_text=long_text,
        tags=None, answer_id=None,
    )
    _handle_save(save_args, context)

    list_args = argparse.Namespace(profile_id=profile.id)
    _handle_list(list_args, context)

    output = capsys.readouterr().out
    assert "..." in output
    assert long_text not in output


def test_handle_generate_raises_profile_not_found_before_calling_claude() -> None:
    # _handle_generate constructs a real ClaudeProvider internally (same
    # composition-root-style pattern as _handle_review/_handle_generate
    # in cover_letter_commands.py), so it can't be fully unit-tested with
    # fakes -- but the profile lookup happens BEFORE any AI call, so this
    # specific path is fast and fake-testable.
    context = _make_context()
    args = argparse.Namespace(
        profile_id=new_profile_id(), question="Why do you want to work here?", save_as=None
    )

    with pytest.raises(ProfileNotFoundError):
        _handle_generate(args, context)
