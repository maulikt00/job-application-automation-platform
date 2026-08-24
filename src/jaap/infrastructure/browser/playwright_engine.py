"""Playwright-backed BrowserAutomationEngine implementation.

Uses Playwright's SYNC API, not async: the rest of this codebase
(repositories, use cases, CLI) is entirely synchronous, and mixing sync
and async across the whole call stack (use case -> browser engine ->
Playwright) would be a real complexity increase for no current benefit.
If a future async consumer (e.g. Phase 5's FastAPI) needs this, sync
Playwright calls can be wrapped in a thread pool executor at that
boundary rather than rewriting this layer now.

Requires the actual browser binary, which is a SEPARATE download from
the `playwright` pip package: after `pip install playwright`, run once:
    python -m playwright install chromium
See requirements.txt's note on this.

Every operational method translates Playwright's own exceptions into
`jaap.domain.exceptions.BrowserAutomationError`, preserving the original
via exception chaining (`raise ... from exc`) -- see
docs/adr/0010-autofill-engine.md for why this was deferred until now.
The `RuntimeError` raised by `_require_page()` is a separate, ordinary
programmer-error guard (calling an operation before launch()/after
close()), not part of that translation -- it was never a Playwright
exception to begin with.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from playwright.sync_api import Browser, Page, Playwright, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from jaap.domain.exceptions import BrowserAutomationError
from jaap.infrastructure.config.settings import Settings


class PlaywrightBrowserEngine:
    """Satisfies application.interfaces.browser_engine.BrowserAutomationEngine.

    `headless` is read from Settings (see settings.py), not hardcoded --
    lets a developer flip JAAP_HEADLESS=false locally to watch the
    browser interactively while debugging form detection and autofill
    logic.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def launch(self) -> None:
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self._settings.headless)
            self._page = self._browser.new_page()
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to launch the browser: {exc}") from exc

    def navigate(self, url: str) -> None:
        try:
            self._require_page().goto(url)
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to navigate to {url!r}: {exc}") from exc

    def evaluate(self, script: str) -> Any:
        try:
            result = self._require_page().evaluate(script)
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to evaluate script: {exc}") from exc
        try:
            # allow_nan=False is deliberate: Python's json.dumps() permits
            # NaN/Infinity by default (non-standard JSON), which would
            # silently defeat this check for a script that evaluates to
            # NaN. Note that Playwright's own serialization already
            # converts genuinely non-serializable JS values (DOM nodes,
            # functions) into safe placeholders before this code ever
            # sees them -- this round-trip is a defensive backstop for
            # edge cases like NaN/Infinity, not the primary defense.
            json.dumps(result, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "evaluate() must only return JSON-compatible data (str, int, "
                "float, bool, None, list, or dict); the script's result "
                "failed to serialize."
            ) from exc
        return result

    def fill(self, selector: str, value: str) -> None:
        try:
            self._require_page().fill(selector, value)
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to fill {selector!r}: {exc}") from exc

    def check(self, selector: str, checked: bool) -> None:
        try:
            page = self._require_page()
            if checked:
                page.check(selector)
            else:
                page.uncheck(selector)
        except PlaywrightError as exc:
            raise BrowserAutomationError(
                f"Failed to set checked={checked} on {selector!r}: {exc}"
            ) from exc

    def select_option(self, selector: str, value: str) -> None:
        try:
            self._require_page().select_option(selector, value)
        except PlaywrightError as exc:
            raise BrowserAutomationError(
                f"Failed to select {value!r} on {selector!r}: {exc}"
            ) from exc

    def upload_file(self, selector: str, file_path: Path) -> None:
        if not file_path.exists():
            # Deliberately checked BEFORE calling into Playwright: a
            # missing file otherwise produces a slow (30+ second), actively
            # misleading failure ("waiting for locator", no mention that
            # the file doesn't exist) -- verified against a real browser
            # while designing this method. See ADR-0011.
            raise BrowserAutomationError(f"Resume file not found: {file_path}")
        try:
            self._require_page().set_input_files(selector, str(file_path))
        except PlaywrightError as exc:
            raise BrowserAutomationError(
                f"Failed to upload {file_path} to {selector!r}: {exc}"
            ) from exc

    def screenshot(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._require_page().screenshot(path=str(path))
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to take screenshot: {exc}") from exc

    def close(self) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
                self._browser = None
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
            self._page = None
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to close the browser: {exc}") from exc

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError(
                "PlaywrightBrowserEngine.launch() must be called before this operation."
            )
        return self._page

    def __enter__(self) -> Self:
        self.launch()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
