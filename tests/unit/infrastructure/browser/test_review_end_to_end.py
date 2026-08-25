"""End-to-end test for `jaap application review`: real Chromium, a real
local HTTP server (run in a background thread within this test process,
so it reliably stays alive for the test's duration), and the real CLI
entry point (main()) -- not just the handler function in isolation.

A real HTTP server is required, not a `data:` URL: JobPosting.url is a
Pydantic HttpUrl, which only accepts http/https schemes.
"""

from __future__ import annotations

import re
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from jaap.domain.models import JobPosting, new_job_posting_id
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
)
from jaap.presentation.cli.main import main

_TEST_FORM_HTML = """
<html><body>
  <label for="full_name">Full Name</label>
  <input id="full_name" name="full_name" type="text">
  <input id="email_field" name="email" type="email">
  <input id="mystery" name="mystery" type="text">
</body></html>
"""


@pytest.fixture
def http_server(tmp_path: Path):
    """A real local HTTP server serving _TEST_FORM_HTML, run in a
    background thread for the duration of the test. Yields the base URL.
    """
    docroot = tmp_path / "docroot"
    docroot.mkdir()
    (docroot / "index.html").write_text(_TEST_FORM_HTML)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(docroot), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass  # silence request logging in test output

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/index.html"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_application_review_end_to_end(tmp_path: Path, http_server: str, capsys) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'jaap.db'}")

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer", url=http_server
    )
    SqliteJobPostingRepository(session_factory).save(posting)

    exit_code = main(
        ["profile", "create", "--name", "Maulik Patel", "--email", "m@example.com"], settings
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", output)
    assert match is not None
    profile_id = match.group(0)

    screenshot_path = tmp_path / "review.png"
    exit_code = main(
        [
            "application", "review",
            "--profile-id", profile_id,
            "--job-posting-id", str(posting.id),
            "--screenshot-path", str(screenshot_path),
        ],
        settings,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "full_name = 'Maulik Patel'" in output
    assert "email = 'm@example.com'" in output
    assert "mystery" in output  # reported as needing manual review
    assert "Nothing has been submitted" in output
    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0
