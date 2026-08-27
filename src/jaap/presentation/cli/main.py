"""CLI composition root and entry point.

The only file in the codebase allowed to import both a repository
interface (implicitly, via Context) and its concrete SQLite
implementation together -- see ARCHITECTURE.md's Composition Root
section. Constructs Settings -> engine -> session factory ->
repositories, bundles them into a Context, parses arguments, and
dispatches to whichever command the user invoked. Use cases themselves
are constructed inside each command handler (see
presentation/cli/commands/), not here -- this module only wires up what
every command shares.

Invocation (no packaging/console_scripts entry point yet -- see
CHANGELOG for why):
    python -m jaap.presentation.cli.main profile create --name "..." --email "..."
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from jaap.application.exceptions import UseCaseError
from jaap.application.interfaces.repositories import (
    AnswerRepository,
    ApplicationRepository,
    CoverLetterTemplateRepository,
    JobPostingRepository,
    ProfileRepository,
    ResumeRepository,
)
from jaap.domain.exceptions import DomainError
from jaap.infrastructure.config.logging_config import configure_logging
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.repositories.sqlite_answer_repository import (
    SqliteAnswerRepository,
)
from jaap.infrastructure.database.repositories.sqlite_application_repository import (
    SqliteApplicationRepository,
)
from jaap.infrastructure.database.repositories.sqlite_cover_letter_template_repository import (
    SqliteCoverLetterTemplateRepository,
)
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)
from jaap.infrastructure.database.repositories.sqlite_profile_repository import (
    SqliteProfileRepository,
)
from jaap.infrastructure.database.repositories.sqlite_resume_repository import (
    SqliteResumeRepository,
)
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
)
from jaap.presentation.cli.commands import (
    answer_commands,
    application_commands,
    cover_letter_commands,
    profile_commands,
    resume_commands,
)


@dataclass
class Context:
    """Bundles the repository interfaces every command handler needs,
    plus Settings.

    A plain dataclass of Protocol-typed fields (repositories) -- command
    handlers depend on these interfaces, never on the concrete
    SqliteXRepository classes directly, so the same handler code is
    testable with fakes (see tests/unit/presentation/cli/) with zero
    changes.

    `settings` (added Milestone 12) is here so command handlers that need
    a browser (currently just `application review`) can construct a
    PlaywrightBrowserEngine on demand, inside their own handler --
    deliberately NOT constructed eagerly in build_context() for every
    invocation, since launching a real browser is comparatively slow and
    most commands (profile create, resume add, ...) never need one.
    """

    profile_repository: ProfileRepository
    resume_repository: ResumeRepository
    job_posting_repository: JobPostingRepository
    application_repository: ApplicationRepository
    answer_repository: AnswerRepository
    cover_letter_template_repository: CoverLetterTemplateRepository
    settings: Settings


def build_context(settings: Settings) -> Context:
    """Constructs the real, SQLite-backed Context for actual CLI use.

    Calls Base.metadata.create_all() unconditionally -- idempotent and
    harmless if tables already exist, which avoids a separate "did you
    forget to run init first?" step for what's currently a single-user,
    development-stage CLI.

    This is NOT a migration strategy and shouldn't be read as one:
    create_all() only creates tables that don't exist yet -- it never
    alters an existing table's columns, indexes, or constraints. If a
    future milestone changes models.py's schema (e.g. adds a column to
    an existing table), this call will silently do nothing for that
    table, and a real migration tool (e.g. Alembic) or an explicit
    migration script will be needed. Revisit when that need arises,
    likely around Phase 5's multi-user/deployment work.
    """
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    return Context(
        profile_repository=SqliteProfileRepository(session_factory),
        resume_repository=SqliteResumeRepository(session_factory),
        job_posting_repository=SqliteJobPostingRepository(session_factory),
        application_repository=SqliteApplicationRepository(session_factory),
        answer_repository=SqliteAnswerRepository(session_factory),
        cover_letter_template_repository=SqliteCoverLetterTemplateRepository(session_factory),
        settings=settings,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jaap", description="Job Application Automation Platform CLI"
    )
    subparsers = parser.add_subparsers(dest="entity", required=True)

    profile_commands.register(subparsers)
    resume_commands.register(subparsers)
    application_commands.register(subparsers)
    answer_commands.register(subparsers)
    cover_letter_commands.register(subparsers)

    return parser


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    """CLI entry point.

    `argv`/`settings` are overridable so tests can invoke this exact
    function end-to-end (real argument parsing, real composition root)
    against a temp/in-memory database, rather than only testing command
    handlers in isolation.
    """
    settings = settings or Settings()
    configure_logging(settings)
    context = build_context(settings)

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args, context)
    except (UseCaseError, DomainError, ValueError) as exc:
        # ValueError added in Milestone 23: WebsiteConnector implementations
        # (and BrowserAutomationEngine.evaluate()'s own JSON-validation
        # check) raise plain ValueError for their own expected failure
        # modes -- a real gap found while wiring connectors into the CLI,
        # since neither was previously caught here, meaning either would
        # have produced a raw traceback instead of a clean message.
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
