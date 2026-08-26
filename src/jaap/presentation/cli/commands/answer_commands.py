"""CLI commands for Answer: `jaap answer save|list`.

Added after a real gap was noticed (not part of any milestone's original
scope): SaveAnswerUseCase has existed since Milestone 6, but nothing in
the CLI ever exposed it -- the only way to create a reusable Answer was
calling the use case directly in Python. `list` is included alongside
`save`, not just requested: seeing what's already been saved is directly
useful before relying on ExactFieldMatcher's exact question_key matching
to autofill anything.
"""

from __future__ import annotations

import argparse
import uuid
from typing import TYPE_CHECKING

from jaap.application.use_cases.manage_answers import SaveAnswerUseCase
from jaap.domain.models import AnswerId, ProfileId

if TYPE_CHECKING:
    from jaap.presentation.cli.main import Context


def register(subparsers: argparse._SubParsersAction) -> None:
    answer_parser = subparsers.add_parser("answer", help="Manage reusable answers")
    answer_subparsers = answer_parser.add_subparsers(dest="action", required=True)

    save_parser = answer_subparsers.add_parser(
        "save", help="Create or update a reusable answer"
    )
    save_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    save_parser.add_argument(
        "--question",
        required=True,
        dest="question_key",
        help=(
            "The question text or key this answer addresses -- normalized "
            "into a slug (see utils/slugify.py). Must match a detected "
            "field's normalized label exactly for ExactFieldMatcher to "
            "find it (Milestone 10); no fuzzy matching."
        ),
    )
    save_parser.add_argument("--text", required=True, dest="answer_text")
    save_parser.add_argument(
        "--tag", action="append", dest="tags", default=None,
        help="Optional tag; repeat --tag to add more than one.",
    )
    save_parser.add_argument("--answer-id", type=uuid.UUID, default=None)
    save_parser.set_defaults(handler=_handle_save)

    list_parser = answer_subparsers.add_parser("list", help="List saved answers for a profile")
    list_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    list_parser.set_defaults(handler=_handle_list)


def _handle_save(args: argparse.Namespace, context: Context) -> int:
    use_case = SaveAnswerUseCase(context.answer_repository, context.profile_repository)
    answer = use_case.execute(
        profile_id=ProfileId(args.profile_id),
        question_key=args.question_key,
        answer_text=args.answer_text,
        tags=args.tags,
        answer_id=AnswerId(args.answer_id) if args.answer_id else None,
    )
    print(f"Saved answer {answer.id} (question_key={answer.question_key!r})")
    return 0


def _handle_list(args: argparse.Namespace, context: Context) -> int:
    # Deliberately calls the repository directly rather than through a
    # use case: listing carries no business rule to enforce, matching
    # `jaap application list`'s own reasoning (see application_commands.py).
    answers = context.answer_repository.list_by_profile(ProfileId(args.profile_id))
    if not answers:
        print("No answers found.")
        return 0
    for answer in answers:
        preview = answer.answer_text if len(answer.answer_text) <= 60 else (
            answer.answer_text[:57] + "..."
        )
        print(f"{answer.id}  question_key={answer.question_key!r}  text={preview!r}")
    return 0
