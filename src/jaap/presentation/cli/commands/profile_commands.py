"""CLI commands for Profile: `jaap profile create`, `jaap profile update`."""

from __future__ import annotations

import argparse
import uuid
from typing import TYPE_CHECKING

from jaap.application.use_cases.manage_profile import (
    CreateProfileUseCase,
    UpdateProfileUseCase,
)
from jaap.domain.models import ProfileId

if TYPE_CHECKING:
    from jaap.presentation.cli.main import Context


def register(subparsers: argparse._SubParsersAction) -> None:
    profile_parser = subparsers.add_parser("profile", help="Manage profiles")
    profile_subparsers = profile_parser.add_subparsers(dest="action", required=True)

    create_parser = profile_subparsers.add_parser("create", help="Create a new profile")
    create_parser.add_argument("--name", required=True, dest="full_name")
    create_parser.add_argument("--email", required=True)
    create_parser.add_argument("--phone", default=None)
    _add_address_arguments(create_parser)
    create_parser.set_defaults(handler=_handle_create)

    update_parser = profile_subparsers.add_parser(
        "update", help="Update an existing profile (only the fields you pass are changed)"
    )
    update_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    update_parser.add_argument("--name", dest="full_name", default=None)
    update_parser.add_argument("--email", default=None)
    update_parser.add_argument("--phone", default=None)
    _add_address_arguments(update_parser)
    update_parser.set_defaults(handler=_handle_update)


def _add_address_arguments(parser: argparse.ArgumentParser) -> None:
    # Shared between create and update -- address fields were added
    # after real-world validation confirmed real application forms
    # (Workday's, ADR-0038) commonly ask for one. All optional, matching
    # --phone's existing pattern.
    parser.add_argument("--address-line1", default=None)
    parser.add_argument("--address-line2", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--postal-code", default=None)
    parser.add_argument("--country", default=None)


def _handle_create(args: argparse.Namespace, context: Context) -> int:
    use_case = CreateProfileUseCase(context.profile_repository)
    profile = use_case.execute(
        full_name=args.full_name,
        email=args.email,
        phone=args.phone,
        address_line1=args.address_line1,
        address_line2=args.address_line2,
        city=args.city,
        state=args.state,
        postal_code=args.postal_code,
        country=args.country,
    )
    print(f"Created profile {profile.id} ({profile.full_name})")
    return 0


def _handle_update(args: argparse.Namespace, context: Context) -> int:
    use_case = UpdateProfileUseCase(context.profile_repository)
    profile = use_case.execute(
        profile_id=ProfileId(args.profile_id),
        full_name=args.full_name,
        email=args.email,
        phone=args.phone,
        address_line1=args.address_line1,
        address_line2=args.address_line2,
        city=args.city,
        state=args.state,
        postal_code=args.postal_code,
        country=args.country,
    )
    print(f"Updated profile {profile.id} ({profile.full_name})")
    return 0
