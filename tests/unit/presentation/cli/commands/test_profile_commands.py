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
from jaap.presentation.cli.commands.profile_commands import _handle_create
from jaap.presentation.cli.main import Context
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeApplicationRepository,
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
        settings=Settings(_env_file=None),
    )


def test_handle_create_creates_and_prints_a_profile(capsys) -> None:
    context = _make_context()
    args = argparse.Namespace(full_name="Maulik Patel", email="m@example.com", phone=None)

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
