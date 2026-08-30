"""Tests for `jaap application review --interactive` (ADR-0034) -- the
generic pause-and-retry mechanism for a connector reporting
AuthenticationRequiredError.

Two different testing strategies, deliberately:

  - The pre-flight guard (`--interactive` + headless=True must fail
    fast, before any browser launches) is tested through the real CLI
    entry point (`main()`) -- this needs no real browser at all, since
    it must fail before one is ever constructed.
  - The actual pause/retry LOOP logic (`_wait_for_manual_sign_in()`) is
    tested directly, as an isolated unit, with a minimal fake engine and
    fake connector -- NOT through the full CLI with a real browser.
    This sandbox has no X server, so a genuinely headed (non-headless)
    Playwright browser cannot launch here at all (confirmed directly:
    it fails with "Missing X server or $DISPLAY" even under `xvfb-run`'s
    virtual display, which does work, but would impose a new, unwanted
    system dependency on the whole test suite just for this one
    mechanism). The retry loop's own logic -- call
    navigate_to_application_form() again, handle 'q', loop on repeated
    AuthenticationRequiredError -- does not need a real browser to
    verify correctly; it needs a connector that behaves in a controlled
    way, which a fake provides directly. This mirrors the same targeted
    fake used for WorkdayConnector's own click-exception-handling test
    (ADR-0032).
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from jaap.domain.exceptions import AuthenticationRequiredError
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
from jaap.presentation.cli.commands.application_commands import _wait_for_manual_sign_in
from jaap.presentation.cli.main import main


def _extract_uuid(text: str) -> str:
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
    assert match is not None, f"no UUID found in: {text!r}"
    return match.group(0)


# --- Pre-flight guard: real CLI entry point, no real browser needed ---
# (must fail before one is ever launched).


def test_interactive_requires_headless_false(tmp_path, capsys) -> None:
    settings = Settings(
        _env_file=None, database_url=f"sqlite:///{tmp_path / 'jaap.db'}", headless=True
    )
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Engineer",
        url="https://example.com/job/1",
    )
    SqliteJobPostingRepository(session_factory).save(posting)

    main(["profile", "create", "--name", "A", "--email", "a@example.com"], settings)
    profile_id = _extract_uuid(capsys.readouterr().out)

    exit_code = main(
        [
            "application", "review", "--profile-id", profile_id,
            "--job-posting-id", str(posting.id), "--interactive",
        ],
        settings,
    )
    err = capsys.readouterr().err

    assert exit_code == 1
    assert "requires a visible browser window" in err


# --- Retry-loop logic: tested directly with fakes, no real browser ---


class _FakeEngine:
    """The retry loop only ever calls navigate_to_application_form() on
    the connector it's given -- it never touches the engine directly
    itself. An empty object is sufficient; included for type clarity
    and in case a future version of the loop does need it."""


class _FakeConnectorRaisingNTimes:
    def __init__(self, fail_count: int) -> None:
        self._fail_count = fail_count
        self.call_count = 0

    def navigate_to_application_form(self, engine) -> None:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise AuthenticationRequiredError(f"Sign-in required (attempt {self.call_count}).")


def test_wait_for_manual_sign_in_succeeds_after_one_retry() -> None:
    connector = _FakeConnectorRaisingNTimes(fail_count=1)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with patch("builtins.input", return_value=""):
        _wait_for_manual_sign_in(_FakeEngine(), connector, original_error)

    assert connector.call_count == 2  # fails once, succeeds on the second attempt


def test_wait_for_manual_sign_in_loops_across_multiple_failed_attempts() -> None:
    connector = _FakeConnectorRaisingNTimes(fail_count=2)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with patch("builtins.input", side_effect=["", "", ""]):
        _wait_for_manual_sign_in(_FakeEngine(), connector, original_error)

    assert connector.call_count == 3  # fails twice, succeeds on the third attempt


def test_wait_for_manual_sign_in_gives_up_when_user_types_q() -> None:
    connector = _FakeConnectorRaisingNTimes(fail_count=99)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with (
        patch("builtins.input", return_value="q"),
        pytest.raises(AuthenticationRequiredError, match="attempt 1"),
    ):
        _wait_for_manual_sign_in(_FakeEngine(), connector, original_error)

    assert connector.call_count == 0  # gave up before ever retrying


def test_wait_for_manual_sign_in_give_up_is_case_insensitive_and_trims_whitespace() -> None:
    connector = _FakeConnectorRaisingNTimes(fail_count=99)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with (
        patch("builtins.input", return_value="  Q  "),
        pytest.raises(AuthenticationRequiredError),
    ):
        _wait_for_manual_sign_in(_FakeEngine(), connector, original_error)
