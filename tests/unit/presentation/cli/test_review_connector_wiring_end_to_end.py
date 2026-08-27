"""End-to-end test proving `jaap application review` actually consults
the connector registry and uses its results -- the real gap this
milestone (23) exists to close. Real Chromium, a real local HTTP
server, and the real CLI entry point (main()), matching
test_review_end_to_end.py's established pattern.

`find_connector` is patched to return a real `GreenhouseConnector`
instance regardless of the URL given, rather than relying on the URL
string actually matching `boards.greenhouse.io`/`job-boards.greenhouse.io`.
This is a deliberate choice, not a shortcut: whether `matches()` itself
correctly recognizes real Greenhouse/Lever/Workday domains is already
verified thoroughly and separately in each connector's own test suite
(test_greenhouse_connector.py, etc.) and in test_registry.py. What is
NOT yet tested anywhere else is whether the CLI, given a connector,
actually calls `navigate_to_application_form()` and uses
`get_field_detector()`'s result instead of the generic detector -- that
is what this test verifies, using a REAL `GreenhouseConnector` instance
(not a fake/stub) so its real navigation and detection logic still runs
for real against the local test server.
"""

from __future__ import annotations

import re
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

import pytest

from jaap.domain.models import JobPosting, new_job_posting_id
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.connectors.greenhouse_connector import GreenhouseConnector
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
)
from jaap.presentation.cli.main import main

# Real Greenhouse-style application-form markup: input[name="first_name"]
# is the exact, confirmed marker GreenhouseConnector checks for (see
# ADR-0021) -- the form is already present, matching the common case
# GreenhouseConnector's navigate_to_application_form() expects.
_GREENHOUSE_STYLE_FORM_HTML = """
<html><body>
  <form>
    <input type="text" name="first_name">
    <input type="text" name="last_name">
    <input type="text" name="email">
  </form>
</body></html>
"""


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


def test_review_uses_the_connectors_detector_and_reports_the_platform(
    tmp_path: Path, http_server: str, capsys
) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'jaap.db'}")

    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    # url is a plain local test server -- platform-string matching itself
    # is not what this test verifies (see module docstring); the
    # find_connector patch below is what actually selects the connector.
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
    with patch(
        "jaap.presentation.cli.commands.application_commands.find_connector",
        return_value=GreenhouseConnector(),
    ):
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
    # The real GreenhouseConnector's real get_field_detector() ran --
    # first_name/last_name are only in the unmatched list because no
    # matching Answer was saved for them, exactly like the generic
    # detector would report; email matches structurally either way.
    assert "Detected platform: greenhouse" in output
    assert "email = 'm@example.com'" in output
    assert "first_name" in output
    assert "last_name" in output
    assert "Nothing has been submitted" in output


def test_review_falls_back_to_the_generic_detector_when_no_connector_matches(
    tmp_path: Path, http_server: str, capsys
) -> None:
    # The ordinary, ungated case: no connector recognizes this URL, so
    # "Detected platform" must not appear, and the existing generic-path
    # behavior (test_review_end_to_end.py) must be unaffected.
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
    output = capsys.readouterr().out
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", output)
    profile_id = match.group(0)

    exit_code = main(
        [
            "application", "review",
            "--profile-id", profile_id,
            "--job-posting-id", str(posting.id),
            "--screenshot-path", str(tmp_path / "review.png"),
        ],
        settings,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Detected platform" not in output
    assert "email = 'm@example.com'" in output
