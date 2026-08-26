"""CLI commands for Resume: `jaap resume add|recommend`.

`recommend` (Milestone 18) supports `--provider claude|ollama` (default
claude) via the shared ai_provider_factory, same composition-root-style
pattern as `cover-letter generate`/`answer generate`. Its recommendation
is based only on each resume's short label compared against the job's
title/company -- it cannot see any resume's actual content (this project
has no resume-text-extraction capability) -- see
docs/adr/0019-resume-recommendation.md.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from jaap.application.use_cases.manage_resumes import AddResumeUseCase
from jaap.application.use_cases.recommend_resume import RecommendResumeUseCase
from jaap.domain.models import JobPostingId, ProfileId
from jaap.presentation.cli.ai_provider_factory import build_ai_provider

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

    recommend_parser = resume_subparsers.add_parser(
        "recommend",
        help=(
            "Suggest which saved resume best fits a job posting, based on "
            "resume labels only -- not actual resume content."
        ),
    )
    recommend_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    recommend_parser.add_argument("--job-posting-id", required=True, type=uuid.UUID)
    recommend_parser.add_argument(
        "--provider", choices=["claude", "ollama"], default="claude",
        help="Which AI provider to use (default: claude).",
    )
    recommend_parser.set_defaults(handler=_handle_recommend)


def _handle_add(args: argparse.Namespace, context: Context) -> int:
    use_case = AddResumeUseCase(context.resume_repository, context.profile_repository)
    resume = use_case.execute(
        profile_id=ProfileId(args.profile_id), label=args.label, file_path=args.file_path
    )
    print(f"Added resume {resume.id} ({resume.label}) to profile {resume.profile_id}")
    return 0


def _handle_recommend(args: argparse.Namespace, context: Context) -> int:
    ai_provider = build_ai_provider(args.provider, context.settings)
    use_case = RecommendResumeUseCase(
        ai_provider=ai_provider,
        resume_repository=context.resume_repository,
        profile_repository=context.profile_repository,
        job_posting_repository=context.job_posting_repository,
    )
    recommendation = use_case.execute(
        profile_id=ProfileId(args.profile_id), job_posting_id=JobPostingId(args.job_posting_id)
    )
    resume = recommendation.recommended_resume
    print(f"Recommended resume: {resume.id} ({resume.label!r})")
    print(f"Reasoning: {recommendation.reasoning}")
    print()
    print(
        "This is a suggestion based on resume labels only, not resume "
        "content -- review before using it with `jaap application attach-resume`."
    )
    return 0
