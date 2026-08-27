"""The comprehensive end-to-end test for Milestone 23's stated scope:
profile + resume + AI-generated cover letter + connector + human
review, tied together in one real flow -- "exercised against a real
(test) posting", per the roadmap's own wording.

Individual pieces already have their own thorough test coverage
elsewhere (GenerateCoverLetterUseCase: Milestone 16; each connector's
own matches()/navigate/detect logic: Milestones 20-22; the CLI actually
consulting a connector: test_review_connector_wiring_end_to_end.py).
This test's job is different: proving all of them compose correctly
together in a single, realistic sequence, through the real CLI entry
point wherever possible.

The AI cover letter step calls GenerateCoverLetterUseCase directly with
a fake AIProvider, not through the CLI -- `jaap cover-letter generate`
constructs a real ClaudeProvider, and there is no real Claude API access
in this test environment (nor should a test suite depend on one: cost,
determinism, credentials). This mirrors exactly how
test_generate_cover_letter.py already tests this use case.
"""

from __future__ import annotations

import re
import threading
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

import pytest

from jaap.application.use_cases.generate_cover_letter import GenerateCoverLetterUseCase
from jaap.domain.models import ApplicationId, JobPosting, ProfileId, new_job_posting_id
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.connectors.greenhouse_connector import GreenhouseConnector
from jaap.infrastructure.database.base import Base
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
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
)
from jaap.presentation.cli.main import main

_GREENHOUSE_STYLE_FORM_HTML = """
<html><body>
  <form>
    <input type="text" name="first_name">
    <input type="text" name="last_name">
    <input type="text" name="email">
  </form>
</body></html>
"""


class _FakeAIProvider:
    """Matches GenerateCoverLetterUseCase's own test suite -- no real
    API call anywhere in this test."""

    def generate_text(self, prompt: str, *, system_prompt: str | None = None) -> str:
        return "Dear Acme, I am excited to apply for this role. Sincerely, Maulik."


@pytest.fixture
def http_server(tmp_path: Path):
    docroot = tmp_path / "docroot"
    docroot.mkdir()
    (docroot / "index.html").write_text(_GREENHOUSE_STYLE_FORM_HTML)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(docroot), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/index.html"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _extract_uuid(text: str) -> str:
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
    assert match is not None, f"no UUID found in: {text!r}"
    return match.group(0)


def test_full_application_flow_profile_resume_ai_cover_letter_connector_review_submit(
    tmp_path: Path, http_server: str, capsys
) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'jaap.db'}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    # --- Profile (real CLI) ---
    exit_code = main(
        ["profile", "create", "--name", "Maulik Patel", "--email", "m@example.com"], settings
    )
    assert exit_code == 0
    profile_id = _extract_uuid(capsys.readouterr().out)

    # --- Resume (real CLI) ---
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"pdf content")
    exit_code = main(
        ["resume", "add", "--profile-id", profile_id, "--label", "General",
         "--file-path", str(resume_file)],
        settings,
    )
    assert exit_code == 0
    resume_id = _extract_uuid(capsys.readouterr().out)

    # --- Job posting (seeded directly -- no CLI command for this yet) ---
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url=http_server
    )
    SqliteJobPostingRepository(session_factory).save(posting)

    # --- AI-generated cover letter (direct use case call, fake provider --
    # see module docstring for why this isn't routed through the CLI) ---
    cover_letter_use_case = GenerateCoverLetterUseCase(
        ai_provider=_FakeAIProvider(),
        profile_repository=SqliteProfileRepository(session_factory),
        job_posting_repository=SqliteJobPostingRepository(session_factory),
        cover_letter_template_repository=SqliteCoverLetterTemplateRepository(session_factory),
    )
    generated_cover_letter = cover_letter_use_case.execute(
        profile_id=ProfileId(uuid.UUID(profile_id)), job_posting_id=posting.id
    )
    assert "Acme" in generated_cover_letter

    # --- Application start + attach resume (real CLI) ---
    exit_code = main(
        ["application", "start", "--profile-id", profile_id,
         "--job-posting-id", str(posting.id)],
        settings,
    )
    assert exit_code == 0
    application_id = _extract_uuid(capsys.readouterr().out)

    exit_code = main(
        ["application", "attach-resume", "--application-id", application_id,
         "--resume-id", resume_id],
        settings,
    )
    assert exit_code == 0
    capsys.readouterr()

    # --- Connector-aware review (real CLI, real GreenhouseConnector) ---
    screenshot_path = tmp_path / "review.png"
    with patch(
        "jaap.presentation.cli.commands.application_commands.find_connector",
        return_value=GreenhouseConnector(),
    ):
        exit_code = main(
            ["application", "review", "--profile-id", profile_id,
             "--job-posting-id", str(posting.id),
             "--screenshot-path", str(screenshot_path)],
            settings,
        )
    review_output = capsys.readouterr().out
    assert exit_code == 0
    assert "Detected platform: greenhouse" in review_output
    assert "email = 'm@example.com'" in review_output
    assert screenshot_path.exists()

    # --- Submit, using the AI-generated cover letter as a one-off override (real CLI) ---
    exit_code = main(
        ["application", "submit", "--application-id", application_id,
         "--cover-letter-text-override", generated_cover_letter],
        settings,
    )
    submit_output = capsys.readouterr().out
    assert exit_code == 0
    assert "status: submitted" in submit_output

    # --- Verify the full chain actually landed correctly in the database ---
    application_repo = SqliteApplicationRepository(session_factory)
    final_application = application_repo.get(ApplicationId(uuid.UUID(application_id)))
    assert final_application is not None
    assert final_application.content_snapshot is not None
    assert final_application.content_snapshot.cover_letter_text == generated_cover_letter
    assert final_application.content_snapshot.resume_label == "General"
