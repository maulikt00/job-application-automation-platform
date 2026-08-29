"""Greenhouse-backed WebsiteConnector implementation.

Design grounded in Greenhouse's own published documentation and API
examples, not assumption -- verified directly before writing any code:

  - **URL patterns**: Greenhouse-hosted job boards live at
    `boards.greenhouse.io/{token}` (the long-standing domain) or
    `job-boards.greenhouse.io` (confirmed from Greenhouse's own embed
    JavaScript, which sets `targetDomain: 'https://job-boards.greenhouse.io'`).
    Both are checked in `matches()`.
  - **Form field structure**: Greenhouse's own Job Board API
    documentation shows the application form using plain, native HTML
    inputs with recognizable `name` attributes --
    `<input type="text" name="first_name">`, `name="last_name"`,
    `name="email"` -- not custom JS widgets. This is why
    `get_field_detector()` below can simply return the existing generic
    `PlaywrightFormFieldDetector` unchanged; there is nothing
    Greenhouse-specific to detect that the generic detector would miss.
  - **A real, confirmed marker for "is the application form present"**:
    `input[name="first_name"]` (Greenhouse's documented, older
    frontend) OR `input#first_name` (a newer, real frontend found via
    live-site validation, 2026-08 -- see ADR-0029: at least one real
    `job-boards.greenhouse.io` posting used `id="first_name"` with NO
    `name` attribute at all on any field -- a structurally different
    implementation from the one Greenhouse's own API docs describe,
    served under the same domain this connector already recognized).
    Both are checked; the generic detector still needs no
    Greenhouse-specific variant, since its own `selectorFor()` already
    checks `id` before `name` and handles either case correctly on its
    own.

**A real, honest scope limitation, stated here rather than glossed
over**: this connector only supports DIRECTLY-HOSTED Greenhouse job
boards (`boards.greenhouse.io`/`job-boards.greenhouse.io`). Greenhouse
also supports an embedded integration (a company embeds their job board
and application form inside an `<iframe>` on their own domain --
confirmed by inspecting Greenhouse's own embed JavaScript, which
constructs a `grnhse_iframe` element). Content inside an iframe is not
part of the top-level page's DOM, so `BrowserAutomationEngine.evaluate()`
(which runs against the main frame only) cannot see it, and neither can
the generic `PlaywrightFormFieldDetector`. Supporting the embedded case
would require genuine cross-frame interaction capability
(`BrowserAutomationEngine` has none), which is a real, separate feature
this milestone does not build. `matches()` returns False for a
third-party domain hosting an embedded iframe, by design -- this
connector will correctly decline to handle that case rather than
silently fail partway through it.
"""

from __future__ import annotations

import time

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import FormFieldDetector
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector

# Taken directly from Greenhouse's own Job Board API documentation's
# example application form HTML -- not invented. Extended to also check
# `id="first_name"` after live-site validation found a real posting
# using only `id`, never `name`, on any field (see this module's
# docstring and ADR-0029).
_FIRST_NAME_FIELD_SELECTOR = 'input[name="first_name"], input#first_name'

# Found via real-world validation against a live Greenhouse posting
# (2026-08): the application form is present on the same page from the
# start (matching this connector's original assumption), but does not
# necessarily finish rendering by the time engine.navigate()'s "load"
# wait condition is satisfied -- a timing issue, not a structural one.
# Polling briefly for the form to appear, rather than checking exactly
# once immediately after navigation, accounts for this without assuming
# a specific render delay.
_FORM_POLL_ATTEMPTS = 10
_FORM_POLL_DELAY_SECONDS = 0.5


class GreenhouseConnector:
    """Satisfies application.interfaces.website_connector.WebsiteConnector."""

    @property
    def platform_name(self) -> str:
        return JobPlatform.GREENHOUSE

    def matches(self, url: str) -> bool:
        return "boards.greenhouse.io" in url or "job-boards.greenhouse.io" in url

    def navigate_to_application_form(self, engine: BrowserAutomationEngine) -> None:
        """Greenhouse-hosted job post URLs typically serve the job
        description and the application form on the same page -- so the
        common case is a no-op, once the form has actually finished
        rendering (which a real live posting confirmed can genuinely lag
        behind the page's own "load" event -- see this module's
        docstring). As a defensive fallback (some configurations may
        show the description first, requiring an explicit step), this
        clicks a visible "Apply" control via Playwright's own
        text-matching selector syntax (`text=Apply`, not a hand-rolled
        JS text search) and polls again afterward, raising a clear error
        if the form still isn't present rather than silently continuing.
        """
        if self._wait_for_form(engine):
            return
        engine.click("text=Apply")
        if not self._wait_for_form(engine):
            raise ValueError(
                "Clicked an 'Apply' element, but no Greenhouse application "
                f"form ({_FIRST_NAME_FIELD_SELECTOR}) was found afterward -- "
                "this page's structure may not match GreenhouseConnector's "
                "assumptions."
            )

    def get_field_detector(self, engine: BrowserAutomationEngine) -> FormFieldDetector:
        # Greenhouse uses plain, native HTML form elements (confirmed
        # from Greenhouse's own API docs) -- nothing platform-specific
        # to detect, so the generic detector is used unchanged.
        return PlaywrightFormFieldDetector(engine)

    def _wait_for_form(self, engine: BrowserAutomationEngine) -> bool:
        for _ in range(_FORM_POLL_ATTEMPTS):
            if self._form_is_present(engine):
                return True
            time.sleep(_FORM_POLL_DELAY_SECONDS)
        return False

    def _form_is_present(self, engine: BrowserAutomationEngine) -> bool:
        return bool(
            engine.evaluate(f"document.querySelector('{_FIRST_NAME_FIELD_SELECTOR}') !== null")
        )
