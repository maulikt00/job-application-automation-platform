"""Tests for AttachedBrowserEngine (ADR-0041) -- connects to a real,
already-running Chrome window over CDP instead of launching a fresh
one.

This sandbox has no real Chrome instance with remote debugging enabled,
so a genuine CDP connection cannot be tested here -- these tests use
mocks to verify the LOGIC: the correct URL is passed to
connect_over_cdp(), the correct page is selected, clear errors are
raised for the "nothing open" cases, and -- the single most important
property of this class -- close() never calls .close() on the
connected Browser object under any circumstances. Real CDP connection
behavior must be verified against an actual, running Chrome instance;
see ADR-0041's own note on this.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from jaap.domain.exceptions import BrowserAutomationError
from jaap.infrastructure.browser.playwright_engine import AttachedBrowserEngine


def _fake_playwright_chain(pages=None):
    """Builds a fake sync_playwright()...start() chain whose connected
    Browser has a single context containing `pages` (a single fake page
    by default)."""
    if pages is None:
        pages = [MagicMock(name="page")]

    fake_context = MagicMock(name="context")
    fake_context.pages = pages

    fake_browser = MagicMock(name="browser")
    fake_browser.contexts = [fake_context]

    fake_playwright_instance = MagicMock(name="playwright_instance")
    fake_playwright_instance.chromium.connect_over_cdp.return_value = fake_browser

    fake_playwright_factory = MagicMock(name="playwright_factory")
    fake_playwright_factory.start.return_value = fake_playwright_instance

    return fake_playwright_factory, fake_playwright_instance, fake_browser, fake_context


def test_launch_connects_with_the_given_cdp_url() -> None:
    factory, instance, _browser, _context = _fake_playwright_chain()

    with patch(
        "jaap.infrastructure.browser.playwright_engine.sync_playwright",
        return_value=factory,
    ):
        engine = AttachedBrowserEngine(cdp_url="http://localhost:9222")
        engine.launch()

    instance.chromium.connect_over_cdp.assert_called_once_with("http://localhost:9222")


def test_launch_selects_the_most_recently_opened_page() -> None:
    page1, page2 = MagicMock(name="page1"), MagicMock(name="page2")
    factory, _instance, _browser, _context = _fake_playwright_chain(pages=[page1, page2])

    with patch(
        "jaap.infrastructure.browser.playwright_engine.sync_playwright",
        return_value=factory,
    ):
        engine = AttachedBrowserEngine(cdp_url="http://localhost:9222")
        engine.launch()

    assert engine._page is page2  # the last one, not the first


def test_launch_raises_a_clear_error_when_no_contexts_exist() -> None:
    factory, _instance, browser, _context = _fake_playwright_chain()
    browser.contexts = []

    with patch(
        "jaap.infrastructure.browser.playwright_engine.sync_playwright",
        return_value=factory,
    ):
        engine = AttachedBrowserEngine(cdp_url="http://localhost:9222")
        with pytest.raises(BrowserAutomationError, match="no open browser context"):
            engine.launch()


def test_launch_raises_a_clear_error_when_no_pages_exist() -> None:
    factory, _instance, _browser, _context = _fake_playwright_chain(pages=[])

    with patch(
        "jaap.infrastructure.browser.playwright_engine.sync_playwright",
        return_value=factory,
    ):
        engine = AttachedBrowserEngine(cdp_url="http://localhost:9222")
        with pytest.raises(BrowserAutomationError, match="no open tabs"):
            engine.launch()


def test_close_never_calls_close_on_the_connected_browser() -> None:
    # The single most important safety property of this class -- see its
    # own docstring and ADR-0041 for the full, researched reasoning.
    factory, _instance, browser, _context = _fake_playwright_chain()

    with patch(
        "jaap.infrastructure.browser.playwright_engine.sync_playwright",
        return_value=factory,
    ):
        engine = AttachedBrowserEngine(cdp_url="http://localhost:9222")
        engine.launch()
        engine.close()

    browser.close.assert_not_called()


def test_close_stops_only_the_local_playwright_driver() -> None:
    factory, instance, _browser, _context = _fake_playwright_chain()

    with patch(
        "jaap.infrastructure.browser.playwright_engine.sync_playwright",
        return_value=factory,
    ):
        engine = AttachedBrowserEngine(cdp_url="http://localhost:9222")
        engine.launch()
        engine.close()

    instance.stop.assert_called_once()


def test_close_is_safe_to_call_when_launch_never_succeeded() -> None:
    # Matches the same "safe to call more than once / even without a
    # prior successful launch" guarantee BrowserAutomationEngine's own
    # interface docstring states for close().
    engine = AttachedBrowserEngine(cdp_url="http://localhost:9222")

    engine.close()  # must not raise
