"""Tests for `_check_generic_sign_in_wall()` (ADR-0040) -- the generic,
no-connector fallback path's own sign-in-wall detection, found
necessary via real-world validation against IBM's careers site
(`careers.ibm.com`), which redirects an unauthenticated session to
`login.ibm.com`.

Real Chromium is used for the actual detection behavior (matches the
exact real scenario: a delayed client-side redirect, and the
transient "execution context was destroyed" BrowserAutomationError
found while probing mid-redirect). A fake engine is used separately for
one precise, fast test of the exception-tolerance behavior specifically.
"""

from __future__ import annotations

import time

import pytest

from jaap.domain.exceptions import AuthenticationRequiredError, BrowserAutomationError
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.commands.application_commands import (
    _check_generic_sign_in_wall,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def test_detects_a_sign_in_wall_present_immediately(settings: Settings, tmp_path) -> None:
    form = tmp_path / "signin.html"
    form.write_text(
        '<html><body><h2>Sign In</h2><button>Log in</button></body></html>',
        encoding="utf-8",
    )
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")

        with pytest.raises(AuthenticationRequiredError, match="require signing in"):
            _check_generic_sign_in_wall(engine, poll_attempts=3, poll_delay_seconds=0.1)


def test_detects_a_delayed_redirect_to_a_sign_in_wall(settings: Settings, tmp_path) -> None:
    # Reproduces the exact real IBM scenario: the initial page has no
    # sign-in text at all, but a client-side redirect (here, 1 second
    # later) lands on one. An earlier version of this function returned
    # early the first time a check came back negative, which would have
    # missed this entirely -- this test exists specifically to guard
    # against that regression.
    posting = tmp_path / "posting.html"
    posting.write_text(
        """
        <html><body>
          <h1>Software Engineer</h1>
          <script>
            setTimeout(function () { window.location.href = 'signin.html'; }, 1000);
          </script>
        </body></html>
        """,
        encoding="utf-8",
    )
    signin = tmp_path / "signin.html"
    signin.write_text(
        '<html><body><h2>Sign In</h2><button>Log in</button></body></html>',
        encoding="utf-8",
    )
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{posting}")

        with pytest.raises(AuthenticationRequiredError, match="require signing in"):
            _check_generic_sign_in_wall(engine, poll_attempts=8, poll_delay_seconds=0.3)


def test_an_ordinary_page_with_no_redirect_proceeds_without_raising(
    settings: Settings, tmp_path
) -> None:
    form = tmp_path / "form.html"
    form.write_text(
        '<html><body><form><input type="text" name="first_name"></form></body></html>',
        encoding="utf-8",
    )
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")

        _check_generic_sign_in_wall(engine, poll_attempts=3, poll_delay_seconds=0.1)  # must not raise


def test_does_not_wait_the_full_window_once_a_sign_in_wall_is_found(
    settings: Settings, tmp_path
) -> None:
    # A sign-in wall present from the very first check should be
    # reported immediately, not after the full poll window elapses.
    form = tmp_path / "signin.html"
    form.write_text(
        '<html><body><h2>Sign In</h2></body></html>', encoding="utf-8"
    )
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")

        start = time.time()
        with pytest.raises(AuthenticationRequiredError):
            _check_generic_sign_in_wall(engine, poll_attempts=20, poll_delay_seconds=1.0)
        elapsed = time.time() - start

    assert elapsed < 2.0  # nowhere near the full 20-second window


class _FakeEngineRaisingThenClear:
    """A minimal fake used only to verify the exception-tolerance
    behavior precisely and quickly: `evaluate()` raises
    BrowserAutomationError on its first `fail_count` calls (simulating
    a mid-navigation "execution context was destroyed" error), then
    behaves as an ordinary, non-gated page thereafter."""

    def __init__(self, fail_count: int) -> None:
        self._fail_count = fail_count
        self.call_count = 0

    def evaluate(self, script: str) -> object:
        self.call_count += 1
        if self.call_count <= self._fail_count:
            raise BrowserAutomationError("Simulated: execution context was destroyed")
        return False  # no sign-in wall once "settled"


def test_a_transient_browser_automation_error_is_tolerated_not_a_hard_failure() -> None:
    # The full poll window is always consumed here (by design -- see
    # this function's own docstring on why it never exits early just
    # because one check came back negative): 2 simulated transient
    # failures, then 3 more clean "no sign-in wall" checks, for 5 total.
    engine = _FakeEngineRaisingThenClear(fail_count=2)

    _check_generic_sign_in_wall(engine, poll_attempts=5, poll_delay_seconds=0.01)  # must not raise

    assert engine.call_count == 5
