"""End-to-end test for the CLI entry point: real argument parsing, real
composition root, real (temp-file) SQLite -- proving the full wiring
actually works, not just each piece in isolation (that's covered by
tests/unit/presentation/cli/commands/ and the use case tests, which use
fakes and never touch main() or a database at all).
"""

from __future__ import annotations

import re
from pathlib import Path

from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.main import main


def _settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'jaap.db'}")


def _extract_id(output: str) -> str:
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", output)
    assert match is not None, f"No UUID found in output: {output!r}"
    return match.group(0)


def test_full_lifecycle_through_the_real_cli_entry_point(tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path)

    # Seed a job posting the same way the seed script does, directly
    # through a repository -- there's no CLI command for this (see
    # scripts/seed_job_posting.py's docstring for why).
    from jaap.domain.models import JobPosting, new_job_posting_id
    from jaap.infrastructure.database.base import Base
    from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
        SqliteJobPostingRepository,
    )
    from jaap.infrastructure.database.session import (
        create_engine_from_settings,
        create_session_factory,
    )

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url="https://acme.example.com/1"
    )
    SqliteJobPostingRepository(session_factory).save(posting)

    exit_code = main(
        ["profile", "create", "--name", "Maulik Patel", "--email", "m@example.com"], settings
    )
    assert exit_code == 0
    profile_id = _extract_id(capsys.readouterr().out)

    exit_code = main(
        ["resume", "add", "--profile-id", profile_id, "--label", "Backend", "--file-path", "r.pdf"],
        settings,
    )
    assert exit_code == 0
    resume_id = _extract_id(capsys.readouterr().out)

    exit_code = main(
        ["application", "start", "--profile-id", profile_id, "--job-posting-id", str(posting.id)],
        settings,
    )
    assert exit_code == 0
    application_id = _extract_id(capsys.readouterr().out)

    exit_code = main(
        [
            "application", "attach-resume",
            "--application-id", application_id, "--resume-id", resume_id,
        ],
        settings,
    )
    assert exit_code == 0
    capsys.readouterr()

    exit_code = main(["application", "submit", "--application-id", application_id], settings)
    assert exit_code == 0
    assert "submitted" in capsys.readouterr().out

    exit_code = main(["application", "list", "--profile-id", profile_id], settings)
    assert exit_code == 0
    assert "status=submitted" in capsys.readouterr().out


def test_error_produces_clean_message_and_nonzero_exit(tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path)

    exit_code = main(
        [
            "resume", "add",
            "--profile-id", "00000000-0000-0000-0000-000000000000",
            "--label", "X", "--file-path", "x.pdf",
        ],
        settings,
    )

    assert exit_code == 1
    assert "Error: No Profile found" in capsys.readouterr().err
