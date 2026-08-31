"""Playwright-backed BrowserAutomationEngine implementations.

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

Two concrete engines share the operational logic below
(`_PageOperationsMixin`) but differ entirely in how a page is obtained
and how cleanup works:

  - `PlaywrightBrowserEngine` launches a brand-new, isolated browser and
    closes it (killing the process) when done -- the engine every prior
    milestone in this project has used.
  - `AttachedBrowserEngine` (ADR-0041) instead connects to a real,
    already-running Chrome window the person launched and is already
    signed into themselves, via Chrome's remote-debugging (CDP)
    protocol, and interacts with whatever tab is already open there.
    Its `close()` NEVER calls `.close()` on the connected Browser object
    at all -- see ADR-0041 for why this was a deliberate, carefully
    researched safety decision, not an oversight.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError

from jaap.domain.exceptions import BrowserAutomationError
from jaap.infrastructure.config.settings import Settings


class _PageOperationsMixin:
    """Every BrowserAutomationEngine operation that only needs a live
    `self._page` -- identical regardless of whether that page came from
    launching a new browser or attaching to an existing one. Subclasses
    are responsible for setting `self._page` (in their own `launch()`)
    and for their own `close()`/cleanup semantics, which genuinely
    differ between the two (see this module's docstring).
    """

    _page: Page | None

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

    def click(self, selector: str) -> None:
        try:
            self._require_page().click(selector)
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to click {selector!r}: {exc}") from exc

    def screenshot(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._require_page().screenshot(path=str(path))
        except PlaywrightError as exc:
            raise BrowserAutomationError(f"Failed to take screenshot: {exc}") from exc

    def _require_page(self) -> Page:
        if self._page is None:
            raise RuntimeError(
                f"{type(self).__name__}.launch() must be called before this operation."
            )
        return self._page


class PlaywrightBrowserEngine(_PageOperationsMixin):
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


class AttachedBrowserEngine(_PageOperationsMixin):
    """Satisfies application.interfaces.browser_engine.BrowserAutomationEngine.

    Connects to a real, already-running Chrome window over Chrome's
    remote-debugging (CDP) protocol, instead of launching a fresh,
    isolated browser -- see ADR-0041 for the full design discussion.
    Requires Chrome to already be running with a debugging port open
    (e.g. `chrome.exe --remote-debugging-port=9222`), and interacts with
    whatever tab is currently open there -- the person is expected to
    already be signed into, and looking at, the application they want
    autofilled.

    Picks `context.pages[-1]` (the most recently opened tab) as the
    target page -- a deliberate, simple heuristic, not a guarantee of
    "the active tab" (CDP has no reliably documented way to determine
    focus). The person is expected to use a dedicated Chrome window with
    only the one relevant tab open, to keep this unambiguous -- stated
    explicitly in this class's own error message if no pages are found
    at all.

    `close()` NEVER calls `.close()` on the connected Browser object,
    under any circumstances -- researched directly against Playwright's
    own official documentation before writing this class: closing a
    browser obtained via `connect_over_cdp()` is documented to "clear
    all created contexts belonging to this browser and disconnect,"
    NOT terminate the real browser process -- but Playwright's own
    GitHub issue tracker shows even Playwright's own users find this
    exact wording confusing (a real, filed documentation-clarity bug,
    not resolved as of this writing). Given that live ambiguity, and
    given what's at stake (the person's own, real, already-logged-in
    browser, potentially with other unrelated tabs open), the safest
    possible design was chosen: never call anything that could
    plausibly affect the connected browser at all. Only
    `self._playwright.stop()` is called on cleanup -- shutting down
    JAAP's own local CDP client/driver process, never sending any
    command to the remote browser itself.
    """

    def __init__(self, cdp_url: str) -> None:
        self._cdp_url = cdp_url
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def launch(self) -> None:
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(self._cdp_url)
        except PlaywrightError as exc:
            raise BrowserAutomationError(
                f"Failed to connect to a running Chrome instance at {self._cdp_url!r}: "
                f"{exc}. Make sure Chrome is running with remote debugging enabled "
                "(e.g. `chrome.exe --remote-debugging-port=9222`) and that no other "
                "process is already using that port."
            ) from exc

        contexts = self._browser.contexts
        if not contexts:
            raise BrowserAutomationError(
                f"Connected to Chrome at {self._cdp_url!r}, but it has no open browser "
                "context at all -- open at least one tab in that Chrome window first."
            )
        self._context = contexts[0]

        pages = self._context.pages
        if not pages:
            raise BrowserAutomationError(
                f"Connected to Chrome at {self._cdp_url!r}, but it has no open tabs -- "
                "open the job application in a tab in that Chrome window first."
            )
        self._page = pages[-1]

    def close(self) -> None:
        # Deliberately does NOT call self._browser.close() -- see this
        # class's own docstring for the full, researched reasoning.
        # Only ever tears down JAAP's own local Playwright driver
        # process; the connected browser is never touched.
        try:
            if self._playwright is not None:
                self._playwright.stop()
                self._playwright = None
            self._browser = None
            self._context = None
            self._page = None
        except PlaywrightError as exc:
            raise BrowserAutomationError(
                f"Failed to disconnect from Chrome: {exc}"
            ) from exc

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
