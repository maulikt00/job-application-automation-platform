"""CLI commands for Answer: `jaap answer save|list|generate`.

Added after a real gap was noticed (not part of any milestone's original
scope): SaveAnswerUseCase has existed since Milestone 6, but nothing in
the CLI ever exposed it -- the only way to create a reusable Answer was
calling the use case directly in Python. `list` is included alongside
`save`, not just requested: seeing what's already been saved is directly
useful before relying on ExactFieldMatcher's exact question_key matching
to autofill anything.

`generate` (Milestone 17) mirrors `cover-letter generate`'s shape exactly
(supports `--provider claude|ollama` via the shared ai_provider_factory,
always shown for review, `--save-as` optionally saves in the same command)
-- see docs/adr/0018-ai-generated-answers.md.
"""

from __future__ import annotations

import argparse
import uuid
from typing import TYPE_CHECKING

from jaap.application.use_cases.generate_answer import GenerateAnswerUseCase
from jaap.application.use_cases.manage_answers import SaveAnswerUseCase
from jaap.domain.models import AnswerId, ProfileId
from jaap.presentation.cli.ai_provider_factory import build_ai_provider

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

    generate_parser = answer_subparsers.add_parser(
        "generate",
        help=(
            "Draft a reusable answer with Claude. Always shown for review; "
            "--save-as optionally saves it as a new answer in the same command. "
            "Deliberately company-agnostic -- see ADR-0018 for why."
        ),
    )
    generate_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    generate_parser.add_argument(
        "--question", required=True, help="The application question to draft an answer for."
    )
    generate_parser.add_argument(
        "--save-as",
        default=None,
        help=(
            "Question key to save under if provided. Pass the same text as "
            "--question to save under its auto-normalized slug (see "
            "Answer.question_key's own validator)."
        ),
    )
    generate_parser.add_argument(
        "--provider", choices=["claude", "ollama"], default="claude",
        help="Which AI provider to use (default: claude).",
    )
    generate_parser.set_defaults(handler=_handle_generate)


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


def _handle_generate(args: argparse.Namespace, context: Context) -> int:
    ai_provider = build_ai_provider(args.provider, context.settings)
    use_case = GenerateAnswerUseCase(
        ai_provider=ai_provider,
        profile_repository=context.profile_repository,
        answer_repository=context.answer_repository,
    )
    generated_text = use_case.execute(
        profile_id=ProfileId(args.profile_id), question=args.question
    )

    print("Generated answer (review before use):")
    print()
    print(generated_text)
    print()

    if args.save_as:
        save_use_case = SaveAnswerUseCase(context.answer_repository, context.profile_repository)
        answer = save_use_case.execute(
            profile_id=ProfileId(args.profile_id),
            question_key=args.save_as,
            answer_text=generated_text,
        )
        print(f"Saved as answer {answer.id} (question_key={answer.question_key!r}).")
    else:
        print(
            "Not saved. Re-run with --save-as <question> to save it as a reusable "
            "answer (pass the same text as --question to key it consistently)."
        )
    return 0
