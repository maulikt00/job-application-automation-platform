"""Tests for PlaywrightBrowserEngine.

These run against a REAL, actual headless Chromium instance -- not a
mock. This is possible because the sandbox/CI environment has Chromium
already provisioned; if your local environment doesn't, run once:
    python -m playwright install chromium
See requirements.txt's note on this. Real integration tests here are
worth the (small) extra runtime cost over mocking, since the actual
value of this milestone is "does a real browser actually launch,
navigate, and clean up correctly" -- a mock would only prove the code
calls playwright's API in the shape we expect, not that any of it works.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings

_TEST_PAGE = 'data:text/html,<html><body><h1 id="heading">Test Page</h1></body></html>'


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def test_context_manager_launches_navigates_and_closes(settings: Settings, tmp_path: Path) -> None:
    screenshot_path = tmp_path / "shot.png"

    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_TEST_PAGE)
        engine.screenshot(screenshot_path)

    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size > 0


def test_screenshot_creates_missing_parent_directories(settings: Settings, tmp_path: Path) -> None:
    nested_path = tmp_path / "nested" / "sub" / "shot.png"

    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_TEST_PAGE)
        engine.screenshot(nested_path)

    assert nested_path.exists()


def test_close_is_idempotent(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)
    engine.launch()

    engine.close()
    engine.close()  # must not raise


def test_navigate_before_launch_raises_runtime_error(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)

    with pytest.raises(RuntimeError, match="launch"):
        engine.navigate(_TEST_PAGE)


def test_screenshot_before_launch_raises_runtime_error(settings: Settings, tmp_path: Path) -> None:
    engine = PlaywrightBrowserEngine(settings)

    with pytest.raises(RuntimeError, match="launch"):
        engine.screenshot(tmp_path / "shot.png")


def test_operations_after_close_raise_runtime_error(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)
    engine.launch()
    engine.close()

    with pytest.raises(RuntimeError, match="launch"):
        engine.navigate(_TEST_PAGE)


def test_manual_launch_and_close_without_context_manager(settings: Settings, tmp_path: Path) -> None:
    engine = PlaywrightBrowserEngine(settings)
    engine.launch()
    try:
        engine.navigate(_TEST_PAGE)
        engine.screenshot(tmp_path / "shot.png")
    finally:
        engine.close()

    assert (tmp_path / "shot.png").exists()


def test_close_is_called_even_when_the_with_block_raises(settings: Settings) -> None:
    engine_ref: list[PlaywrightBrowserEngine] = []

    with pytest.raises(ValueError), PlaywrightBrowserEngine(settings) as engine:
        engine_ref.append(engine)
        engine.navigate(_TEST_PAGE)
        raise ValueError("simulated failure mid-automation")

    # If close() ran, a subsequent operation should raise the same
    # "must call launch()" error as any other closed/unlaunched engine --
    # proving __exit__ actually tore things down, not just that no
    # exception leaked from __exit__ itself.
    with pytest.raises(RuntimeError, match="launch"):
        engine_ref[0].navigate(_TEST_PAGE)
