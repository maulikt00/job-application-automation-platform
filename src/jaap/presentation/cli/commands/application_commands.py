"""CLI commands for Application: `jaap application start|submit|list`."""

from __future__ import annotations

import argparse
import uuid
from typing import TYPE_CHECKING

from jaap.application.use_cases.attach_resume_to_application import (
    AttachResumeToApplicationUseCase,
)
from jaap.application.use_cases.start_application import StartApplicationUseCase
from jaap.application.use_cases.submit_application import SubmitApplicationUseCase
from jaap.domain.models import ApplicationId, JobPostingId, ProfileId, ResumeId

if TYPE_CHECKING:
    from jaap.presentation.cli.main import Context


def register(subparsers: argparse._SubParsersAction) -> None:
    application_parser = subparsers.add_parser("application", help="Manage applications")
    application_subparsers = application_parser.add_subparsers(dest="action", required=True)

    start_parser = application_subparsers.add_parser("start", help="Start a new draft application")
    start_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    start_parser.add_argument("--job-posting-id", required=True, type=uuid.UUID)
    start_parser.set_defaults(handler=_handle_start)

    attach_resume_parser = application_subparsers.add_parser(
        "attach-resume", help="Attach a resume to a draft application"
    )
    attach_resume_parser.add_argument("--application-id", required=True, type=uuid.UUID)
    attach_resume_parser.add_argument("--resume-id", required=True, type=uuid.UUID)
    attach_resume_parser.set_defaults(handler=_handle_attach_resume)

    submit_parser = application_subparsers.add_parser("submit", help="Submit a draft application")
    submit_parser.add_argument("--application-id", required=True, type=uuid.UUID)
    submit_parser.set_defaults(handler=_handle_submit)

    list_parser = application_subparsers.add_parser(
        "list", help="List applications for a profile"
    )
    list_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    list_parser.set_defaults(handler=_handle_list)


def _handle_start(args: argparse.Namespace, context: Context) -> int:
    use_case = StartApplicationUseCase(
        context.application_repository, context.profile_repository, context.job_posting_repository
    )
    application = use_case.execute(
        profile_id=ProfileId(args.profile_id), job_posting_id=JobPostingId(args.job_posting_id)
    )
    print(f"Started application {application.id} (status: {application.current_status.value})")
    return 0


def _handle_attach_resume(args: argparse.Namespace, context: Context) -> int:
    use_case = AttachResumeToApplicationUseCase(
        context.application_repository, context.resume_repository
    )
    application = use_case.execute(
        application_id=ApplicationId(args.application_id), resume_id=ResumeId(args.resume_id)
    )
    print(f"Attached resume {args.resume_id} to application {application.id}")
    return 0


def _handle_submit(args: argparse.Namespace, context: Context) -> int:
    use_case = SubmitApplicationUseCase(context.application_repository)
    application = use_case.execute(ApplicationId(args.application_id))
    print(f"Submitted application {application.id} (status: {application.current_status.value})")
    return 0


def _handle_list(args: argparse.Namespace, context: Context) -> int:
    # Deliberately calls the repository directly rather than through a
    # use case: listing carries no business rule to enforce (unlike
    # start/submit), so a dedicated use case would add ceremony without
    # adding behavior. This is still dependency-rule-clean -- `context`
    # only exposes Protocol interfaces (application layer), never a
    # concrete SqliteApplicationRepository -- it's just skipping the
    # use-case layer for a trivial read, not skipping the abstraction.
    applications = context.application_repository.list_by_profile(ProfileId(args.profile_id))
    if not applications:
        print("No applications found.")
        return 0
    for application in applications:
        print(
            f"{application.id}  status={application.current_status.value}  "
            f"job_posting={application.job_posting_id}"
        )
    return 0
