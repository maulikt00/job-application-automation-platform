"""Tests for `jaap application review --interactive` (ADR-0034/0040) --
the generic pause-and-retry mechanism for a connector, or the generic
no-connector fallback path, reporting AuthenticationRequiredError.

Two different testing strategies, deliberately:

  - The pre-flight guard (`--interactive` + headless=True must fail
    fast, before any browser launches) is tested through the real CLI
    entry point (`main()`) -- this needs no real browser at all, since
    it must fail before one is ever constructed.
  - The actual pause/retry LOOP logic (`_wait_for_manual_sign_in()`) is
    tested directly, as an isolated unit, with a plain retry callable --
    NOT through the full CLI with a real browser. This sandbox has no
    X server, so a genuinely headed (non-headless) Playwright browser
    cannot launch here at all (confirmed directly: it fails with
    "Missing X server or $DISPLAY" even under `xvfb-run`'s virtual
    display, which does work, but would impose a new, unwanted system
    dependency on the whole test suite just for this one mechanism).
    The retry loop's own logic -- call `retry()` again, handle 'q', loop
    on repeated AuthenticationRequiredError -- does not need a real
    browser to verify correctly; a plain callable that behaves in a
    controlled way is sufficient. `_wait_for_manual_sign_in()` no longer
    takes a `WebsiteConnector` directly (ADR-0040): it takes a bare
    `retry: Callable[[], None]`, since it now serves both a connector's
    own `navigate_to_application_form()` and the generic fallback
    path's own sign-in check.
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


# --- Retry-loop logic: tested directly with a plain retry callable ---


class _FakeConnectorRaisingNTimes:
    """A minimal stand-in for whatever `retry()` actually calls (a real
    connector's navigate_to_application_form, or the generic sign-in
    check) -- these tests are about the loop's own logic, not any real
    connector, so a plain call-counting fake is all that's needed."""

    def __init__(self, fail_count: int) -> None:
        self._fail_count = fail_count
        self.call_count = 0

    def retry(self) -> None:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise AuthenticationRequiredError(f"Sign-in required (attempt {self.call_count}).")


class _FakeConnectorTransientThenSuccess:
    """Reproduces the exact real scenario found in ADR-0036: right after
    signing in, a real retry hit a generic ValueError (page in a brief
    transitional state), not another AuthenticationRequiredError -- a
    second, completely separate CLI invocation then succeeded. This
    fake raises a ValueError on its first call (not
    AuthenticationRequiredError), then succeeds on the second."""

    def __init__(self) -> None:
        self.call_count = 0

    def retry(self) -> None:
        self.call_count += 1
        if self.call_count == 1:
            raise ValueError(
                "Clicked through Workday's Apply flow, but no field with a "
                "data-automation-id attribute was found afterward."
            )


def test_wait_for_manual_sign_in_succeeds_after_one_retry() -> None:
    fake = _FakeConnectorRaisingNTimes(fail_count=1)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with patch("builtins.input", return_value=""):
        _wait_for_manual_sign_in(fake.retry, original_error)

    assert fake.call_count == 2  # fails once, succeeds on the second attempt


def test_wait_for_manual_sign_in_retries_past_a_transient_value_error() -> None:
    # ADR-0036: a generic ValueError right after signing in (the page
    # briefly in a transitional state) must not kill the whole loop --
    # the human should be able to press Enter again and succeed.
    fake = _FakeConnectorTransientThenSuccess()

    with patch("builtins.input", return_value=""):
        _wait_for_manual_sign_in(fake.retry, AuthenticationRequiredError("Sign-in required."))

    assert fake.call_count == 2


def test_wait_for_manual_sign_in_gives_up_with_the_latest_error_after_a_transient_failure() -> None:
    fake = _FakeConnectorTransientThenSuccess()

    with (
        patch("builtins.input", side_effect=["", "q"]),
        pytest.raises(AuthenticationRequiredError, match="data-automation-id"),
    ):
        # Force a second failure by making call_count never reach the
        # success branch: reuse the same fake but call it enough times
        # that it would have succeeded, then give up before that.
        _wait_for_manual_sign_in(fake.retry, AuthenticationRequiredError("Sign-in required."))


def test_wait_for_manual_sign_in_loops_across_multiple_failed_attempts() -> None:
    fake = _FakeConnectorRaisingNTimes(fail_count=2)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with patch("builtins.input", side_effect=["", "", ""]):
        _wait_for_manual_sign_in(fake.retry, original_error)

    assert fake.call_count == 3  # fails twice, succeeds on the third attempt


def test_wait_for_manual_sign_in_gives_up_when_user_types_q() -> None:
    fake = _FakeConnectorRaisingNTimes(fail_count=99)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with (
        patch("builtins.input", return_value="q"),
        pytest.raises(AuthenticationRequiredError, match="attempt 1"),
    ):
        _wait_for_manual_sign_in(fake.retry, original_error)

    assert fake.call_count == 0  # gave up before ever retrying


def test_wait_for_manual_sign_in_give_up_is_case_insensitive_and_trims_whitespace() -> None:
    fake = _FakeConnectorRaisingNTimes(fail_count=99)
    original_error = AuthenticationRequiredError("Sign-in required (attempt 1).")

    with (
        patch("builtins.input", return_value="  Q  "),
        pytest.raises(AuthenticationRequiredError),
    ):
        _wait_for_manual_sign_in(fake.retry, original_error)
