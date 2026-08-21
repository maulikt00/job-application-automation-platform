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
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Self

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from jaap.infrastructure.config.settings import Settings


class PlaywrightBrowserEngine:
    """Satisfies application.interfaces.browser_engine.BrowserAutomationEngine.

    `headless` is read from Settings (see settings.py), not hardcoded --
    lets a developer flip JAAP_HEADLESS=false locally to watch the
    browser interactively while debugging Milestone 9/10's form
    detection and autofill logic.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def launch(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._settings.headless)
        self._page = self._browser.new_page()

    def navigate(self, url: str) -> None:
        self._require_page().goto(url)

    def screenshot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._require_page().screenshot(path=str(path))

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
        self._page = None

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
