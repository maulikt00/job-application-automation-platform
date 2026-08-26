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

from jaap.domain.exceptions import BrowserAutomationError
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


def test_evaluate_returns_simple_values(settings: Settings) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_TEST_PAGE)
        assert engine.evaluate("1 + 1") == 2
        assert engine.evaluate("document.getElementById('heading').textContent") == "Test Page"


def test_evaluate_returns_structured_json_compatible_values(settings: Settings) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_TEST_PAGE)
        result = engine.evaluate("({a: 1, b: [1, 2, 3], c: null})")
        assert result == {"a": 1, "b": [1, 2, 3], "c": None}


def test_evaluate_rejects_nan(settings: Settings) -> None:
    # Regression test: Python's json.dumps() allows NaN by default
    # (non-standard JSON), which would silently defeat this guard
    # without allow_nan=False -- see playwright_engine.py's evaluate().
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_TEST_PAGE)
        with pytest.raises(ValueError, match="JSON-compatible"):
            engine.evaluate("NaN")


def test_evaluate_before_launch_raises_runtime_error(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)

    with pytest.raises(RuntimeError, match="launch"):
        engine.evaluate("1 + 1")


_FORM_PAGE = (
    'data:text/html,<html><body>'
    '<input id="t" type="text">'
    '<input id="c" type="checkbox">'
    '<select id="s"><option value="a">A</option><option value="b">B</option></select>'
    '<button id="apply" onclick="document.getElementById(\'result\').textContent=\'clicked\'">Apply</button>'
    '<div id="result"></div>'
    '</body></html>'
)


def test_fill_sets_a_text_fields_value(settings: Settings) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        engine.fill("#t", "hello world")
        assert engine.evaluate("document.getElementById('t').value") == "hello world"


def test_check_sets_a_checkbox_checked(settings: Settings) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        engine.check("#c", True)
        assert engine.evaluate("document.getElementById('c').checked") is True


def test_check_false_unchecks_a_checkbox(settings: Settings) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        engine.check("#c", True)
        engine.check("#c", False)
        assert engine.evaluate("document.getElementById('c').checked") is False


def test_select_option_sets_the_selected_value(settings: Settings) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        engine.select_option("#s", "b")
        assert engine.evaluate("document.getElementById('s').value") == "b"


def test_fill_before_launch_raises_runtime_error(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)

    with pytest.raises(RuntimeError, match="launch"):
        engine.fill("#t", "x")


def test_check_before_launch_raises_runtime_error(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)

    with pytest.raises(RuntimeError, match="launch"):
        engine.check("#c", True)


def test_select_option_before_launch_raises_runtime_error(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)

    with pytest.raises(RuntimeError, match="launch"):
        engine.select_option("#s", "a")


def test_evaluate_with_invalid_javascript_raises_browser_automation_error(
    settings: Settings,
) -> None:
    # Fast, reliable trigger for a genuine Playwright error: invalid JS
    # syntax fails immediately, unlike a missing-selector wait (30s
    # default timeout) -- deliberately avoided here to keep this test fast.
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_TEST_PAGE)
        with pytest.raises(BrowserAutomationError) as exc_info:
            engine.evaluate("this is not valid javascript !!!")
        assert exc_info.value.__cause__ is not None


def test_check_on_a_non_checkable_element_raises_browser_automation_error(
    settings: Settings,
) -> None:
    # Fast, reliable trigger: check() on a text input is immediately
    # invalid (not a "waiting for element" timeout).
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        with pytest.raises(BrowserAutomationError) as exc_info:
            engine.check("#t", True)
        assert exc_info.value.__cause__ is not None


def test_select_option_on_a_non_select_element_raises_browser_automation_error(
    settings: Settings,
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        with pytest.raises(BrowserAutomationError) as exc_info:
            engine.select_option("#t", "a")
        assert exc_info.value.__cause__ is not None


_FILE_UPLOAD_PAGE = 'data:text/html,<html><body><input id="f" type="file"></body></html>'


def test_upload_file_attaches_a_real_file(settings: Settings, tmp_path: Path) -> None:
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 fake resume content")

    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FILE_UPLOAD_PAGE)
        engine.upload_file("#f", resume)
        uploaded_name = engine.evaluate("document.getElementById('f').files[0].name")

    assert uploaded_name == "resume.pdf"


def test_upload_file_with_missing_file_raises_fast_and_clearly(settings: Settings) -> None:
    missing = Path("/tmp/definitely_does_not_exist_12345.pdf")

    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FILE_UPLOAD_PAGE)
        with pytest.raises(BrowserAutomationError, match="not found"):
            engine.upload_file("#f", missing)


def test_upload_file_before_launch_raises_runtime_error(settings: Settings, tmp_path: Path) -> None:
    engine = PlaywrightBrowserEngine(settings)
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"content")

    with pytest.raises(RuntimeError, match="launch"):
        engine.upload_file("#f", resume)


def test_click_activates_the_clicked_elements_handler(settings: Settings) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        engine.click("#apply")
        assert engine.evaluate("document.getElementById('result').textContent") == "clicked"


def test_click_before_launch_raises_runtime_error(settings: Settings) -> None:
    engine = PlaywrightBrowserEngine(settings)

    with pytest.raises(RuntimeError, match="launch"):
        engine.click("#apply")


def test_click_with_a_malformed_selector_raises_browser_automation_error(
    settings: Settings,
) -> None:
    # A malformed CSS selector is the fastest reliable trigger found for
    # click() specifically: unlike check()/select_option(), click() has
    # no "wrong element type" fast-fail path (it can be called on nearly
    # any element), and a missing selector waits the full ~30s
    # actionability timeout. A syntactically invalid selector fails
    # during parsing, before any actionability wait begins -- still not
    # sub-second (~10s), but far better than the alternative, and a
    # genuine, real failure mode worth having a regression test for.
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(_FORM_PAGE)
        with pytest.raises(BrowserAutomationError) as exc_info:
            engine.click(":::invalid-selector:::")
        assert exc_info.value.__cause__ is not None
