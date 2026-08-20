"""CLI commands for Profile: `jaap profile create`."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from jaap.application.use_cases.manage_profile import CreateProfileUseCase

if TYPE_CHECKING:
    from jaap.presentation.cli.main import Context


def register(subparsers: argparse._SubParsersAction) -> None:
    profile_parser = subparsers.add_parser("profile", help="Manage profiles")
    profile_subparsers = profile_parser.add_subparsers(dest="action", required=True)

    create_parser = profile_subparsers.add_parser("create", help="Create a new profile")
    create_parser.add_argument("--name", required=True, dest="full_name")
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--phone", default=None)
    create_parser.set_defaults(handler=_handle_create)


def _handle_create(args: argparse.Namespace, context: Context) -> int:
    use_case = CreateProfileUseCase(context.profile_repository)
    profile = use_case.execute(full_name=args.full_name, email=args.email, phone=args.phone)
    print(f"Created profile {profile.id} ({profile.full_name})")
    return 0
