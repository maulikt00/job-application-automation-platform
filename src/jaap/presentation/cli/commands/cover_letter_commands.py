"""CLI commands for CoverLetterTemplate: `jaap cover-letter save|list`.

Added alongside answer_commands.py, for the same reason: SaveCoverLetterTemplateUseCase
has existed since Milestone 6 with no CLI exposure until now. Named
"cover-letter" in the CLI (not "cover-letter-template") for brevity at
the command line; the underlying domain concept remains CoverLetterTemplate.
"""

from __future__ import annotations

import argparse
import uuid
from typing import TYPE_CHECKING

from jaap.application.use_cases.manage_cover_letter_templates import (
    SaveCoverLetterTemplateUseCase,
)
from jaap.domain.models import CoverLetterTemplateId, ProfileId

if TYPE_CHECKING:
    from jaap.presentation.cli.main import Context


def register(subparsers: argparse._SubParsersAction) -> None:
    cover_letter_parser = subparsers.add_parser(
        "cover-letter", help="Manage reusable cover letter templates"
    )
    cover_letter_subparsers = cover_letter_parser.add_subparsers(dest="action", required=True)

    save_parser = cover_letter_subparsers.add_parser(
        "save", help="Create or update a cover letter template"
    )
    save_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    save_parser.add_argument("--name", required=True)
    save_parser.add_argument(
        "--body",
        required=True,
        dest="body_template",
        help='The template body, which may include placeholders (e.g. "{{company_name}}").',
    )
    save_parser.add_argument("--template-id", type=uuid.UUID, default=None)
    save_parser.set_defaults(handler=_handle_save)

    list_parser = cover_letter_subparsers.add_parser(
        "list", help="List saved cover letter templates for a profile"
    )
    list_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    list_parser.set_defaults(handler=_handle_list)


def _handle_save(args: argparse.Namespace, context: Context) -> int:
    use_case = SaveCoverLetterTemplateUseCase(
        context.cover_letter_template_repository, context.profile_repository
    )
    template = use_case.execute(
        profile_id=ProfileId(args.profile_id),
        name=args.name,
        body_template=args.body_template,
        template_id=CoverLetterTemplateId(args.template_id) if args.template_id else None,
    )
    print(f"Saved cover letter template {template.id} ({template.name!r})")
    return 0


def _handle_list(args: argparse.Namespace, context: Context) -> int:
    templates = context.cover_letter_template_repository.list_by_profile(
        ProfileId(args.profile_id)
    )
    if not templates:
        print("No cover letter templates found.")
        return 0
    for template in templates:
        print(f"{template.id}  name={template.name!r}")
    return 0
