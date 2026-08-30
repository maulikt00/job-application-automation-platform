"""Tests for profile_commands: calls the handler function directly with
a Context built from fakes -- no database, no subprocess, no argparse
parsing involved (that's covered separately by the end-to-end test in
test_main.py).
"""

from __future__ import annotations

import argparse
import uuid

from jaap.domain.models import ProfileId
from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.commands.profile_commands import (
    _handle_create,
    _handle_update,
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


def _create_args(**overrides) -> argparse.Namespace:
    defaults = {
        "full_name": "Maulik Patel",
        "email": "m@example.com",
        "phone": None,
        "address_line1": None,
        "address_line2": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _update_args(**overrides) -> argparse.Namespace:
    defaults = {
        "profile_id": None,
        "full_name": None,
        "email": None,
        "phone": None,
        "address_line1": None,
        "address_line2": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_handle_create_creates_and_prints_a_profile(capsys) -> None:
    context = _make_context()
    args = _create_args()

    exit_code = _handle_create(args, context)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Maulik Patel" in output

    # Extract the printed id to confirm it was actually persisted via
    # the public repository interface, not by reaching into fake internals --
    # mirrors how a real user would grab the id from output for the next command.
    printed_id = output.split()[2]
    saved = context.profile_repository.get(ProfileId(uuid.UUID(printed_id)))
    assert saved is not None
    assert saved.full_name == "Maulik Patel"


def test_handle_create_saves_address_fields_when_provided(capsys) -> None:
    context = _make_context()
    args = _create_args(address_line1="123 Main St", city="Santa Clara", state="CA")

    exit_code = _handle_create(args, context)

    assert exit_code == 0
    printed_id = capsys.readouterr().out.split()[2]
    saved = context.profile_repository.get(ProfileId(uuid.UUID(printed_id)))
    assert saved is not None
    assert saved.address_line1 == "123 Main St"
    assert saved.city == "Santa Clara"
    assert saved.state == "CA"


def test_handle_update_changes_only_the_fields_passed(capsys) -> None:
    context = _make_context()
    create_exit_code = _handle_create(
        _create_args(phone="555-0100", city="Santa Clara"), context
    )
    assert create_exit_code == 0
    profile_id = capsys.readouterr().out.split()[2]

    exit_code = _handle_update(
        _update_args(profile_id=uuid.UUID(profile_id), state="CA"), context
    )

    assert exit_code == 0
    saved = context.profile_repository.get(ProfileId(uuid.UUID(profile_id)))
    assert saved is not None
    assert saved.state == "CA"
    assert saved.phone == "555-0100"  # unchanged, not passed to update
    assert saved.city == "Santa Clara"  # unchanged, not passed to update
