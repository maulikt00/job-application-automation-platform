"""CLI commands for Resume: `jaap resume add`."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from jaap.application.use_cases.manage_resumes import AddResumeUseCase
from jaap.domain.models import ProfileId

if TYPE_CHECKING:
    from jaap.presentation.cli.main import Context


def register(subparsers: argparse._SubParsersAction) -> None:
    resume_parser = subparsers.add_parser("resume", help="Manage resumes")
    resume_subparsers = resume_parser.add_subparsers(dest="action", required=True)

    add_parser = resume_subparsers.add_parser("add", help="Add a resume to a profile")
    add_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    add_parser.add_argument("--label", required=True)
    add_parser.add_argument("--file-path", required=True, type=Path)
    add_parser.set_defaults(handler=_handle_add)


def _handle_add(args: argparse.Namespace, context: Context) -> int:
    use_case = AddResumeUseCase(context.resume_repository, context.profile_repository)
    resume = use_case.execute(
        profile_id=ProfileId(args.profile_id), label=args.label, file_path=args.file_path
    )
    print(f"Added resume {resume.id} ({resume.label}) to profile {resume.profile_id}")
    return 0
